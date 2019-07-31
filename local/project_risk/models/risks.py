# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


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
    treatment_task_id = fields.Many2one('project.task', compute='_compute_treatment_task_id', store=True,
                                        string='Treatment Task')
    treatment_task_count = fields.Integer(related='treatment_task_id.subtask_count', string='Risk Treatment Tasks',
                                          store=True)

    @api.depends('state', 'mgt_stage')
    def _compute_treatment_task_id(self):
        """Adds a Task to treat the risk as soon as the risk level becomes unacceptable """
        for rec in self:
            if rec.mgt_stage >= '4' and rec.state == 'N':
                if not rec.treatment_task_id:
                    rec.treatment_task_id = self.env['project.task'].sudo().create({
                        'name': 'Treatment for %s' % rec.name,
                        'description': """
                        <p>
                            The purpose of this task is to select and implement measures to modify 
                            the %s. These measures can include avoiding, optimizing, transferring or retaining risk.
                        </p>
                                """ % rec.name,
                        'project_id': rec.project_id.id,
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
                'default_business_risk_id': self.id,
                'default_project_id': self.project_id.id,
                'default_target_criterium': 'O'
            }
        }

    @api.multi
    def _track_subtype(self, init_values):
        self.ensure_one()
        if 'active' in init_values and self.active:
            return 'project_risk.mt_project_risk_new'
        elif 'report_date' in init_values and self.report_date == fields.Date.today():
            return 'project_risk.mt_project_risk_new'
        elif 'state' in init_values:
            return 'project_risk.mt_project_risk_status'
        elif 'mgt_stage' in init_values:
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
             ('business_process_id', '=', vals.get('business_process_id', False)),
             ('risk_type', '=', vals.get('risk_type', False))])
        if existing:
            existing.exists()[0].update_report()
            return existing.exists()[0].id
        else:
            if vals.get('project_id') and not context.get('default_project_id'):
                context['default_project_id'] = vals.get('project_id')
        risk = super(ProjectRisk, self).create(vals)
        return risk


class ProjectRiskEvaluation(models.Model):
    _inherit = ['risk_management.risk_evaluation.mixin']
    _name = 'project_risk.evaluation'
    _description = 'Project Risk Evaluation'

    project_risk_id = fields.Many2one('project_risk.project_risk', string='Risk', required=True)
    risk_type = fields.Selection(related='risk_id.risk_type', readonly=True)
    threshold_value = fields.Integer(related='risk_id.threshold_value', store=True, readonly=True)
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
