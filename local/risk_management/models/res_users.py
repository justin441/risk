from odoo import models, fields


class Users(models.Model):
    _inherit = 'res.users'

    business_process_ids = fields.Many2many('risk_management.business_process', 'risk_management_users_process_rel',
                                            'user_id', 'process_id', string='Processes')