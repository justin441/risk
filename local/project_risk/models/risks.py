# -*- coding: utf-8 -*-

import datetime
from odoo import models, fields, api, _, exceptions


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
    task_ids = fields.Many2many('project.task', relation='project_risk_task_ids_risk_ids_rel',
                                column1='project_risk_id', column2='task_id',
                                domain="[('project_id', '=', project_id)]", string='Impacted tasks')
    evaluation_ids = fields.One2many('project_risk.evaluation', inverse_name='project_risk_id', string='Evaluations')
    treatment_task_ids = fields.One2many('project.task', inverse_name='project_risk_id')

    def _inverse_treatment(self):
        for rec in self:
            if rec.treatment_task_ids:
                task = self.env['project.task'].browse(rec.treatment_task_ids[0].id)
                task.project_risk_id = False
            if rec.treatment_task_id:
                rec.treatment_task_id.project_risk_id = rec

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
        elif 'stage' in init_values:
            return 'project_risk.mt_project_risk_stage'
        return super(ProjectRisk, self)._track_subtype(init_values)

    @api.model
    def create(self, vals):
        # context: no_log, because subtype already handle this
        context = dict(self.env.context, mail_create_nolog=True)
        act_deadline_date = datetime.date.today() + datetime.timedelta(days=RISK_ACT_DELAY)
        act_deadline = fields.Date.to_string(act_deadline_date)
        ir_model = self.env['ir.model']
        act_type = self.env.ref('risk_management.risk_activity_todo')
        existing = self.env[self._name].search(
            [('risk_info_id', '=', vals.get('risk_info_id', False)),
             ('project_id', '=', vals.get('project_id', False)),
             ('risk_type', '=', vals.get('risk_type', False))])
        if existing:
            existing = existing.exists()[0]
            if not existing.active:
                existing.write(vals)
                self.env['mail.activity'].create({
                    'res_id': existing.id,
                    'res_model_id': ir_model._get_id(self._name),
                    'activity_type_id': act_type.id,
                    'summary': 'Next step in Risk Management: Confirm',
                    'note': '<p>Check and confirm the existence of the risk.</p>',
                    'date_deadline': act_deadline
                })
                return existing.id
            else:
                raise exceptions.UserError((_("This risk has already been reported. ")))
        else:
            if vals.get('project_id') and not context.get('default_project_id'):
                context['default_project_id'] = vals.get('project_id')
        risk = super(ProjectRisk, self).create(vals)
        # Next activity
        self.env['mail.activity'].create({
            'res_id': risk,
            'res_model_id': ir_model._get_id(self._name),
            'activity_type_id': act_type.id,
            'summary': 'Next step in Risk Management: Confirm',
            'note': '<p>Check and confirm the existence of the risk.</p>',
            'date_deadline': act_deadline
        })
        return risk


class ProjectRiskEvaluation(models.Model):
    _inherit = ['risk_management.risk_evaluation.mixin']
    _name = 'project_risk.evaluation'
    _description = 'Project Risk Evaluation'

    project_risk_id = fields.Many2one('project_risk.project_risk', string='Risk', required=True,
                                      ondelete='cascade')
    risk_type = fields.Selection(related='project_risk_id.risk_type', readonly=True)
    threshold_value = fields.Integer(related='project_risk_id.threshold_value', store=True, readonly=True)
    value = fields.Integer('Risk Level', compute='_compute_eval_value', store=True)

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

    @api.model
    def create(self, vals):
        same_day_eval = self.env['project_risk.evaluation'].search([
            ('eval_date', '=', fields.Date.context_today(self))
        ])
        # if another estimation was created the same day, just update it
        if same_day_eval.exists():
            vals.update({'is_valid': False})
            if len(same_day_eval.exists()) > 1:
                # Hardly necessary, but you never know, there may be more than one record in `same_day_eval`
                same_day_eval.exists()[1:].unlink()
            same_day_eval = same_day_eval.exists()
            same_day_eval.write(vals)
            evaluation = same_day_eval.id

        else:
            evaluation = super(ProjectRiskEvaluation, self).create(vals)
            act_deadline_date = datetime.date.today() + datetime.timedelta(days=RISK_ACT_DELAY)
            # add an activity to validate the risk evaluation.
            self.env['mail.activity'].create({
                'res_id': vals.get('project_risk_id'),
                'res_model_id': self.env['ir.model']._get_id('project_risk.project_risk'),
                'activity_type_id': self.env.ref('risk_management.risk_activity_todo').id,
                'summary': 'Next step in Risk Management: Validate',
                'note': '<p>Validate the risk assessment.</p>',
                'date_deadline': fields.Date.to_string(act_deadline_date)
            })
        return evaluation

    @api.multi
    def write(self, vals):
        res = super(ProjectRiskEvaluation, self).write(vals)
        if res and vals.get('is_valid', False):
            res_model_id = self.env['ir.model']._get_id('project_risk.project_risk')
            act_deadline_date = datetime.date.today() + datetime.timedelta(days=RISK_ACT_DELAY)
            for rec in self:
                # mark previous activities as done
                self.env['mail.activity'].search(['&', '&', ('res_id', '=', rec.project_risk_id.id),
                                                  ('res_model_id', '=', res_model_id),
                                                  '|',
                                                  ('note', 'ilike', 'Validate the risk assessment'),
                                                  ('note', 'ilike',
                                                   'Assess the probability of risk occurring and its possible impact,'
                                                   'as well as the company\'s ability to detect it should it occur.')
                                                  ]).action_done()
                if rec.value > rec.threshold_value:
                    # add an activity to treat the risk
                    self.env['mail.activity'].create({
                        'res_id': rec.project_risk_id.id,
                        'res_model_id': res_model_id,
                        'activity_type_id': self.env.ref('risk_management.risk_activity_todo').id,
                        'summary': 'Next step in Risk Management: Treat risk',
                        'note': '<p>Select and implement measures to modify risk.</p>',
                        'date_deadline': fields.Date.to_string(act_deadline_date)
                    })

                    if not rec.project_risk_id.treatment_task_id:
                        # create a risk treatment task for the risk being evaluated
                        self.env['project.task'].create({
                            'name': 'Treatment for %s' % rec.project_risk_id.name,
                            'description': """
                                <p>
                                    Select and implement options for modifying %s, and/or improve risk control for
                                    this risk.
                                </p>
                            """ % rec.project_risk_id.name,
                            'priority': '1',
                            'project_id': self.env.ref('risk_management.risk_treatment_project').id,
                            'project_risk_id': rec.project_risk_id.id
                        })
        return res
