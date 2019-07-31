from odoo import models, fields


class ProjectRiskThresholdWizard(models.TransientModel):
    _name = 'project_risk.set_threshold_wizard'
    _inherit = ['risk_management.base_eval_wizard']

    def default_criteria(self):
        # return a dict of the risk criteria
        risk_id = self.env.context.get('default_project_risk_id', False)
        if risk_id:
            risk = self.env[self._name].browse(risk_id)
            if risk.exists():
                return {'detectability': risk.detectability,
                        'occurrence': risk.occurrence,
                        'severity': risk.severity}
        return {}

    risk_id = fields.Many2one('project_risk.project_risk', string='Project Risk', required=True,
                              ondelete='cascade')
    threshold_value = fields.Integer('Current Threshold', related='risk_id.threshold_value')
    latest_level = fields.Integer('Current Level', related='risk_id.latest_level_value')
    comment = fields.Html(string='Comments', related='risk_id.comment')


class ProjectRiskEvalWizard(models.TransientModel):
    _name = 'project_risk.eval_wizard'
    _inherit = ['risk_management.base_risk_level_wizard']

    def _get_default_criteria(self):
        # returns a dict of the risk latest evaluation's criteria
        risk_id = self.env.context.get('default_project_risk_id', False)

        if risk_id:
            risk = self.env[self._name].browse(risk_id)
            if risk.exists() and risk.evaluation_ids.exists():
                latest_evaluation = risk.evaluation_ids.sorted()[0]
                return {
                    'detectability': latest_evaluation.detectability,
                    'occurrence': latest_evaluation.occurrence,
                    'severity': latest_evaluation.severity,
                }
        return {}

    risk_id = fields.Many2one('project_risk.project_risk', string='Project Risk', required=True,
                              ondelete='cascade')
    latest_eval = fields.Many2one('project_risk.evaluation', compute='_compute_latest_eval')
    threshold_value = fields.Integer('Current Threshold', related='risk_id.threshold_value')
    latest_level = fields.Integer('Current Level', related='risk_id.latest_level_value')
    risk_eval_model = fields.Char('Evaluation Model', default='risk_management.project_risk.evaluation', readonly=True)
    latest_level_date = fields.Date('Last evaluated on', related='risk_id.last_evaluate_date', readonly=True)
    comment = fields.Html(string='Comments', related='latest_eval.comment')

