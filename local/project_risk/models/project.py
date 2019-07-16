from odoo import models, fields, api


class Project(models.Model):
    _inherit = 'project.project'

    risk_ids = fields.One2many('project_risk.risk', inverse_name='project_id', string='Risks')
    risk_count = fields.Integer('Active risks', compute='_compute_active_risks')

    @api.multi
    def _compute_active_risks(self):
        for rec in self:
            rec.risk_count = len(rec.risk_ids.filtered('active'))

    @api.multi
    def message_subscribe(self, partner_ids=None, channel_ids=None, subtype_ids=None, force=True):
        """ Subscribe to all existing risks when subscribing to a project"""
        res = super(Project, self).message_subscribe(partner_ids=partner_ids, channel_ids=channel_ids,
                                                     subtype_ids=subtype_ids, force=force)
        if not subtype_ids or any(subtype.parent_id.res_model == 'project_risk.risk' for subtype in
                                  self.env['mail.message.subtype'].browse(subtype_ids)):
            for partner_id in partner_ids or []:
                self.mapped('risk_ids').filtered(
                    lambda risk: partner_id not in risk.message_partner_ids.ids
                ).message_subscribe(partner_ids=[partner_id], channel_ids=None, subtype_ids=None, force=False)
            for channel_id in channel_ids or []:
                self.mapped('risk_ids').filtered(
                    lambda risk: channel_id not in risk.message_channel_ids.ids
                ).message_subscribe(
                    partner_ids=None, channel_ids=[channel_id], subtype_ids=None, force=False)
        return res


class Task(models.Model):
    _inherit = 'project.task'

    project_risk_ids = fields.Many2many('project_risk.risk', relation='project_risk_task_ids_risk_ids_rel',
                                        column1='project_risk_ids', column2='task_ids', string='Risks')