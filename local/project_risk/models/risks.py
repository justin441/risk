# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ProjectRisk(models.Model):
    _inherit = 'risk_management.risk_identification.mixin'
    _name = 'project_risk.risk'
    _description = 'Project Risk'

    project_id = fields.Many2one('project.project', string='Project')
    subtask_project_id = fields.Many2one('project.project', related='project_id.subtask_project_id', readonly=True)
    task_ids = fields.Many2many('project.task', relation='project_risk_task_ids_risk_ids_rel', column1='task_ids',
                                column2='project_risk_ids', domain="[('project_id', '=', project_id)]",
                                string='Impacted tasks')
    evaluation_ids = fields.One2many('project_risk.evaluation', inverse_name='project_risk_id', string='Evaluations')
    treatment_task_ids = fields.One2many('project.task', inverse_name='project_risk_id', string='Risk Treatment')

    @api.depends('latest_level_value', 'treatment_task_ids')
    def _compute_stage(self):
        for rec in self:
            if rec.active and not rec.latest_level_value:
                rec.mgt_stage = '1'
            elif rec.latest_level_value and not rec.treatment_task_ids:
                rec.mgt_stage = '2'
            elif rec.treatment_task_ids:
                rec.mgt_stage = '3'
            else:
                rec.mgt_stage = False

    @api.depends('treatment_tasks_ids')
    def _compute_treatment_count(self):
        for rec in self:
            rec.treatment_task_count = len(rec.treatment_task_ids)

    @api.multi
    def add_risk_treatment_task(self):
        self.ensure_one()
        if not self.subtask_project_id:
            self.sudo().project_id.subtask_project_id = self.project_id
        treatment_task = self.project_id.get_risk_treatment_task()
        return {
            'name': _('Risk Treatment'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'project.task',
            'type': 'ir.action.act_window',
            'context': {
                'default_parent_id': treatment_task.id,
                'default_project_id': self.subtask_project_id.id or self.project_id.id,
                'default_project_risk_id': self.id
            }
        }

    @api.multi
    def _track_subtype(self, init_values):
        self.ensure_one()
        # if 'active' in init_values and self.active:
        #     return 'risk_management.mt_project_risk_new'
        # elif 'owner' in init_values and self.owner:
        #     return 'risk_management.mt_project_risk_new'
        # elif 'state' in init_values:
        #     return 'risk_management.mt_project_risk_status'
        # TODO create subtypes
        return super(ProjectRisk, self)._track_subtype(init_values)

    @api.multi
    def _notification_recipients(self, message, groups):
        groups = super(ProjectRisk, self)._notification_recipients(message, groups)

        for group_name, group_method, group_data in groups:
            group_data['has_button_access'] = True

        return groups


class ProjectRiskEvaluation(models.Model):
    _inherit = ['risk_management.risk_evaluation.mixin']
    _name = 'project_risk.evaluation'
    _description = 'Project Risk Evaluation'

    project_risk_id = fields.Many2one('project_risk.risk', string='Risk', required=True)
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
