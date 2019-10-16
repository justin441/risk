import logging
from odoo import models, api

_logger = logging.getLogger(__name__)


class RiskSummaryReport(models.AbstractModel):
    _name = 'report.risk_management.risk_summary_report'

    @api.model
    def get_report_values(self, docids, data=None):
        risks_report = self.env['ir.actions.report']._get_report_from_name('risk_management.risk_summary_report')
        risks = self.env['risk_management.business_risk'].browse(docids)
        _logger.warning(docids)
        return {
            'doc_ids': docids,
            'docs': risks,
            'docmodel': risks_report,
            'my_name': 'Fotue justin'
        }
