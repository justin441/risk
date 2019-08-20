from odoo import api, models
import logging


_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _name = 'risk_management.settings'
    _inherit = 'res.config.settings'

    @api.model
    def set_subtask_project(self):
        _logger.warning("> Settings sign-up parameters")
        settings = self.env['res.config.settings'].create({
            'group_subtask_project': True,
        })
        settings.execute()
        _logger.warning("> ... done.")
