# -*- coding: utf-8 -*-

import datetime
from odoo import models, fields, api, _


RISK_ACT_DELAY = 15
RISK_REPORT_DEFAULT_MAX_AGE = 90


class RiskInfo(models.Model):
    _inherit = 'risk_management.risk.info'

    project_risk_ids = fields.One2many('project_risk.project_risk', inverse_name='risk_info_id',
                                       string='Occurrences(Project)')
    project_occurrences = fields.Integer(string="Occurrences in Projects", compute="_compute_project_occurrences")

    @api.multi
    def _compute_project_occurrences(self):
        for rec in self:
            rec.project_occurrences = len(rec.project_risk_ids.filtered('active'))


class ProjectRisk(models.Model):
    _inherit = 'risk_management.risk_identification.mixin'
    _name = 'project_risk.project_risk'
    _description = 'Project Risk'

    project_id = fields.Many2one('project.project', string='Project')
    subtask_project_id = fields.Many2one('project.project', related='project_id.subtask_project_id', readonly=True)
    task_ids = fields.Many2many('project.task', relation='project_risk_task_ids_risk_ids_rel',
                                column1='project_risk_id', column2='task_id',
                                domain="[('project_id', '=', project_id)]", string='Impacted tasks')
    evaluation_ids = fields.One2many('project_risk.evaluation', inverse_name='project_risk_id', string='Evaluations')
    treatment_task_id = fields.Many2one('project.task', store=True,
                                        string='Treatment Task')
    treatment_task_count = fields.Integer(related='treatment_task_id.subtask_count', string='Risk Treatment Tasks',
                                          store=True)

    @api.depends('active', 'is_confirmed', 'treatment_task_id', 'treatment_task_count', 'evaluation_ids')
    def _compute_stage(self):
        for risk in self:
            if risk.evaluation_ids:
                up_to_date_evals = risk.evaluation_ids.filtered(
                    lambda ev: not ev.is_obsolete)
            else:
                up_to_date_evals = False
            if up_to_date_evals:
                valid_evals = up_to_date_evals.filtered('is_valid')
            else:
                valid_evals = False
            if not risk.active:
                risk.state = False
            elif not risk.is_confirmed:
                # risk has been reported but not confirmed
                risk.state = '1'  # still in identification stage

            elif not up_to_date_evals:
                # risk has been confirmed but has not yet been evaluated
                risk.state = '2'  # risk identification completed

            elif not valid_evals:
                # there are evaluations of the risk but no valid one yet
                risk.state = '3'  # still in evaluation stage

            elif not risk.treatment_task_id:
                # there is at least one valid risk evaluation
                risk.state = '4'  # Risk evaluation completed

            elif risk.treatment_task_count:
                # there is at least one ongoing risk treatment task
                risk.state = '5'  # ongoing risk treatment

            elif risk.treatment_task_id.child_ids and not risk.treatment_task_count:
                # risk treatment done
                risk.state = '6'

    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.project_id:
            if not self.project_id.subtask_project_id:
                self.project_id.subtask_project_id = self.project_id

    @api.onchange('active')
    def _onchange_active(self):
        if self.active:
            if self.treatment_task_id and not self.treatment_task_id.active:
                self.sudo().treatment_task_id.active = True
            self.update_report()
        else:
            if self.treatment_task_id and self.treatment_task_id.active:
                self.sudo().treatment_task_id.active = False
            self.write({
                'review_date': fields.Date.context_today(self),
                'is_confirmed': False,
                'owner': False
            })

    @api.multi
    def get_treatments_view(self):
        """returns the treatment tasks view.
        """
        self.ensure_one()
        return {
            'name': _('Treatment Tasks'),
            'type': 'ir.actions.act_window',
            'res_model': 'project.task',
            'views': [
                [False, "kanban"], [False, "form"], [False, "tree"],
                [False, "calendar"], [False, "pivot"], [False, "graph"]
            ],
            'context': {
                'search_default_parent_id': self.treatment_task_id.id,
                'default_parent_id': self.treatment_task_id.id,
                'default_project_risk_id': self.id,
                'default_project_id': self.project_id.id,
                'default_target_criterium': 'O'
            }
        }

    @api.multi
    def _track_subtype(self, init_values):
        self.ensure_one()
        if 'active' in init_values and self.active:
            return 'project_risk.mt_project_risk_new'
        elif 'active' in init_values and not self.active:
            return 'project_risk.mt_project_risk_obsolete'
        elif 'report_date' in init_values and self.report_date == fields.Date.today():
            return 'project_risk.mt_project_risk_new'
        elif 'status' in init_values:
            return 'project_risk.mt_project_risk_status'
        elif 'state' in init_values:
            return 'project_risk.mt_project_risk_stage'
        return super(ProjectRisk, self)._track_subtype(init_values)

    @api.multi
    def _notification_recipients(self, message, groups):
        groups = super(ProjectRisk, self)._notification_recipients(message, groups)

        for group_name, group_method, group_data in groups:
            group_data['has_button_access'] = True

        return groups

    @api.model
    def _message_get_auto_subscribe_fields(self, updated_fields, auto_follow_fields=None):
        user_field_lst = super(ProjectRisk, self)._message_get_auto_subscribe_fields(updated_fields,
                                                                                     auto_follow_fields=None)
        user_field_lst.append('owner')
        return user_field_lst

    @api.model
    def create(self, vals):
        # context: no_log, because subtype already handle this
        context = dict(self.env.context, mail_create_nolog=True)
        existing = self.env['project_risk.project_risk'].search(
            [('active', '=', True), ('risk_info_id', '=', vals.get('risk_info_id', False)),
             ('project_id', '=', vals.get('project_id', False)),
             ('risk_type', '=', vals.get('risk_type', False))])
        if existing:
            existing.exists()[0].update_report()
            return existing.exists()[0].id
        else:
            if vals.get('project_id') and not context.get('default_project_id'):
                context['default_project_id'] = vals.get('project_id')
        risk = super(ProjectRisk, self).create(vals)

        act_deadline_date = datetime.date.today() + datetime.timedelta(days=RISK_ACT_DELAY)
        act_deadline = fields.Date.to_string(act_deadline_date)
        ir_model = self.env['ir.model']
        act_type = self.env.ref('risk_management.risk_activity_todo')
        # Next activity
        self.env['mail.activity'].create({
            'res_id': risk,
            'res_model_id': ir_model._get_id(self._name),
            'activity_type_id': act_type.id,
            'summary': 'Check and confirm the existence of the risk',
            'date_deadline': act_deadline
        })
        return risk

    @api.multi
    def write(self, vals):
        if 'active' in vals:
            if vals['active']:
                # The risk is being activated
                new_report_date = fields.Date.context_today(self)
                review_date = fields.Date.from_string(new_report_date) + datetime.timedelta(
                    days=RISK_REPORT_DEFAULT_MAX_AGE)
                vals.update({'review_date': fields.Date.to_string(review_date),
                             'report_date': new_report_date,
                             'reported_by': self.env.user.id,
                             'is_confirmed': False})
            else:
                vals.update({
                    'review_date': fields.Date.context_today(self),
                    'is_confirmed': False,
                    'owner': False
                })
            self.with_context(active_test=False).mapped('treatment_task_id').write({'active': vals['active']})
        res = super(ProjectRisk).write(vals)
        if 'status' in vals and vals['status'] == 'N':
            vals.pop('status')
            for rec in res:
                if not rec.treatment_task_id:
                    rec.write({
                        'treatment_task_id': [(0, 0, {
                            'name': 'Treatment for %s' % rec.name,
                            'description': """
                        <p>
                            The purpose of this task is to select and implement measures to modify 
                            the risk. These measures can include avoiding, optimizing, transferring or retaining risk.
                        </p>
                                """,
                            'project_id': rec.project_id,
                            'priority': '1',
                        })]
                    })
        return res


class ProjectRiskEvaluation(models.Model):
    _inherit = ['risk_management.risk_evaluation.mixin']
    _name = 'project_risk.evaluation'
    _description = 'Project Risk Evaluation'

    project_risk_id = fields.Many2one('project_risk.project_risk', string='Risk', required=True)
    risk_type = fields.Selection(related='project_risk_id.risk_type', readonly=True)
    threshold_value = fields.Integer(related='project_risk_id.threshold_value', store=True, readonly=True)
    value = fields.Integer('Risk Level', compute='_compute_eval_value', store=True)

    @api.model
    def create(self, vals):
        same_day = self.env['project_risk.evaluation'].search([
            ('eval_date', '=', fields.Date.context_today(self))
        ])
        # if another estimation was created the same day, just update it
        if same_day:
            if len(same_day) > 1:
                same_day[1:].unlink()
            same_day.exists().write(vals)
        else:
            return super(ProjectRiskEvaluation, self).create(vals)

    @api.depends('project_risk_id',
                 'detectability',
                 'occurrence',
                 'severity')
    def _compute_eval_value(self):
        for rec in self:
            if rec.risk_type == 'T':
                rec.value = rec.value_threat
            elif rec.risk_type == 'O':
                rec.value = rec.value_opportunity
