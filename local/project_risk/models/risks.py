# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProjectRisk(models.Model):
    _inherit = 'risk_management.base_identification'
    _name = 'project_risk.risk'
    _description = 'Project Risk'

    project_id = fields.Many2one('project.project', string='Project')
    task_ids = fields.Many2many('project.task', relation='project_risk_task_ids_risk_ids_rel', column1='task_ids',
                                column2='project_risk_ids', domain="[('project_id', '=', project_id)]",
                                string='Impacted tasks')


class ProjectRiskEvaluation(models.Model):
    _inherit = ['risk_management.base_evaluation']
    _name = 'project_risk.evaluation'
    _description = 'Project Risk Evaluation'

    risk_id = fields.Many2one('project_risk.risk', string='Risk', required=True)
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
