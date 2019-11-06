import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class RiskProfileWizard(models.TransientModel):
    _name = 'risk_management.risk_profile.wizard'

    company_id = fields.Many2one('res.company', string='Company',  default=lambda self: self.env.user.company_id,
                                 required=True)
    ref_asset_id = fields.Reference(selection='_ref_models', string='Asset')

    @api.model
    def _ref_models(self):
        m = self.env['res.request.link'].search([('object', '!=', 'risk_management.business_risk')])
        return [(x.object, x.name) for x in m]

    @api.multi
    def get_report(self):

        data = {
            'ids': self.ids,
            'model': self._name,
            'form': {
                'company_id': self.company_id.id,
                'asset_id': self.ref_asset_id.id if self.ref_asset_id else False,
                'asset_type': self.ref_asset_id._name if self.ref_asset_id else False
            },
        }
        return self.env.ref('risk_management.action_risk_profile_report').report_action(self, data=data)


class RiskProfileReport(models.AbstractModel):
    _name = 'report.risk_management.risk_profile_report'

    @api.model
    def get_report_values(self, docids, data=None):
        company_id = data['form']['company_id']
        asset_id = data['form']['asset_id']
        asset_type = data['form']['asset_type']
        risks = self.env['risk_management.business_risk'].search([('company_id', '=', company_id)])
        if asset_id:
            asset_repr = asset_type + ',' + str(asset_id)  # asset representation in risk model
            risks = risks.search([('asset', '=', asset_repr)])
        return {
            'doc_ids': data['ids'],
            'doc_model': data['model'],
            'docs': risks,
            'user_lang': self.env.user.lang
        }




