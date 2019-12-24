import datetime
from odoo import models, fields, api
from .risk_utils import add_risk_activity

RISK_ACT_DELAY = 15


class Project(models.Model):
    _inherit = 'project.project'

    risk_ids = fields.One2many('risk_management.business_risk', compute='_compute_risk')
    risk_count = fields.Integer('Active risks', compute='_compute_risk_count')

    @api.multi
    def _compute_risk(self):
        for project in self:
            project.risk_ids = self.env['risk_management.business_risk'].search([
                ('asset', '=', self._name + ',' + str(project.id))
            ])

    @api.multi
    def _compute_risk_count(self):
        for project in self:
            project.risk_count = len(project.risk_ids)

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

    @api.multi
    def write(self, vals):
        res = super(Project, self).write(vals) if vals else True
        if 'active' in vals and not vals.get('active'):
            # unarchiving a project does it on its risks, too
            self.sudo().mapped('risk_ids').write({'active': vals['active']})
        return res


class Task(models.Model):
    _inherit = 'project.task'

    business_risk_id = fields.Many2one(comodel_name='risk_management.business_risk', string='Business Risk')
    target_criterium = fields.Selection(selection=[('D', 'Detectability'), ('O', 'Occurrence'), ('S', 'Severity')],
                                        string='Target Criterium')

    @api.multi
    def write(self, vals):
        res = super(Task, self).write(vals)
        if res and vals.get('active', False):
            # task has been reactivated
            act_deadline_date = datetime.date.today() + datetime.timedelta(days=RISK_ACT_DELAY)
            deadline = fields.Date.to_string(act_deadline_date)
            note = "Select and implement measures to modify risk."
            for rec in self:
                if rec.business_risk_id:
                    # If it's a risk treatment task: this means the status of the risk changed to `Not acceptable`
                    add_risk_activity(self.env, rec.business_risk_id, note, deadline)

        return res
