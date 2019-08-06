from odoo import models, fields


class Task(models.Model):
    _inherit = 'project.task'

    def _get_default_business_risk(self):
        default_risk_id = self.env.context.get('default_business_risk_id')
        if default_risk_id:
            risk = self.env['risk_management.business_risk'].browse(default_risk_id)
            if risk:
                return risk.exists()

    business_risk_id = fields.Many2one(comodel_name='risk_management.business_risk', string='Business Risk',
                                       default=_get_default_business_risk)
    target_criterium = fields.Selection(selection=[('D', 'Detectability'), ('O', 'Occurrence'), ('S', 'Severity')],
                                        string='Target Criterium')
