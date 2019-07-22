from odoo import models, fields, api


class Project(models.Model):
    _inherit = 'project.project'

    risk_count = fields.Integer(compute='_compute_risk_count', string='Risks')

    @api.multi
    def _compute_risk_count(self):
        for rec in self:
            if rec.process_ids:
                rec.risk_count = sum([process.risk_count for process in rec.process_ids])
            else:
                rec.risk_count = 0

    @api.multi
    def message_subscribe(self, partner_ids=None, channel_ids=None, subtype_ids=None, force=True):
        """ Subscribe to all existing process when subscribing to a project"""
        res = super(Project, self).message_subscribe(partner_ids=partner_ids, channel_ids=channel_ids,
                                                     subtype_ids=subtype_ids, force=force)
        if not subtype_ids or any(subtype.parent_id.res_model == 'business_management.project_process' for subtype in
                                  self.env['mail.message.subtype'].browse(subtype_ids)):
            for partner_id in partner_ids or []:
                self.mapped('process_ids').filtered(
                    lambda process: partner_id not in process.message_partner_ids.ids
                ).message_subscribe(partner_ids=[partner_id], channel_ids=None, subtype_ids=None, force=False)
            for channel_id in channel_ids or []:
                self.mapped('process_ids').filtered(
                    lambda process: channel_id not in process.message_channel_ids.ids
                ).message_subscribe(
                    partner_ids=None, channel_ids=[channel_id], subtype_ids=None, force=False)
        return res


class Task(models.Model):
    _inherit = 'project.task'

    def _get_default_project_risk(self):
        default_risk_id = self.env.context.get('default_risk_id')
        risk_model = self.env.context.get('risk_model')
        if default_risk_id and risk_model == 'risk_management.project_risk':
            risk = self.env[risk_model].browse(default_risk_id)
            if risk:
                return risk.exists()

    def _get_default_business_risk(self):
        default_risk_id = self.env.context.get('default_risk_id')
        risk_model = self.env.context.get('risk_model')
        if default_risk_id and risk_model == 'risk_management.business_risk':
            risk = self.env[risk_model].browse(default_risk_id)
            if risk:
                return risk.exists()
        elif self.project_id:
            return self.project_id.risk_id

    project_risk_id = fields.Many2one(comodel_name='risk_management.project_risk', string='Project Risk',
                                      default=_get_default_project_risk)
    business_risk_id = fields.Many2one(comodel_name='risk_management.business_risk', string='Business Risk',
                                       default=_get_default_business_risk)
    target_criterium = fields.Selection(selection=[('D', 'Detectability'), ('O', 'Occurrence'), ('S', 'Severity')],
                                        string='Target Criterium')
