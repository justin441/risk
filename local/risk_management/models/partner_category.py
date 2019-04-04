from odoo import models, fields


class PartnerCategory(models.Model):
    """Add output data to partner category"""
    _inherit = 'res.partner.category'

    output_data_ids = fields.One2many('risk_management.process_data', inverse_name='ext_provider_cat_id',
                                      string="Output data")