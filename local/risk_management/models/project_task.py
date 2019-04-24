from odoo import models, fields


class Task(models.Model):
    _inherit = 'project.task'

    process_id = fields.Many2one('risk_management.project_process', ondelete='cascade', string='Process',
                                 domain="[('project_id', '=', project_id)]")
