from odoo import models, fields


class ProjectRiskThresholdWizard(models.TransientModel):
    _name = 'project_risk.set_threshold_wizard'
    _inherit = ['risk_management.base_eval_wizard']

    risk_id = fields.Many2one('project_risk.project_risk', string='Project Risk', required=True,
                              ondelete='cascade')
    threshold_value = fields.Integer('Current Threshold', related='risk_id.threshold_value')
    latest_level = fields.Integer('Current Level', related='risk_id.latest_level_value')
    comment = fields.Html(string='Comments', related='risk_id.comment')


class ProjectRiskEvalWizard(models.TransientModel):
    _name = 'project_risk.eval_wizard'
    _inherit = ['risk_management.base_risk_level_wizard']

    risk_id = fields.Many2one('project_risk.project_risk', string='Project Risk', required=True,
                              ondelete='cascade')
    latest_eval = fields.Many2one('project_risk.evaluation', compute='_compute_latest_eval')
    threshold_value = fields.Integer('Current Threshold', related='risk_id.threshold_value')
    latest_level = fields.Integer('Current Level', related='risk_id.latest_level_value')
    risk_eval_model = fields.Char('Evaluation Model', default='risk_management.project_risk.evaluation', readonly=True)
    latest_level_date = fields.Date('Last evaluated on', related='risk_id.last_evaluate_date', readonly=True)
    comment = fields.Html(string='Comments', related='latest_eval.comment')

