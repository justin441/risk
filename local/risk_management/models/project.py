import datetime
from odoo import models, fields, api

RISK_ACT_DELAY = 15


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

    @api.multi
    def write(self, vals):
        res = super(Task, self).write(vals)
        if res and 'active' in vals and not vals['active']:
            activity = self.env['mail.activity']
            res_model_id = self.env['ir.model']._get_id('risk_management.business_risk')
            act_deadline_date = datetime.date.today() + datetime.timedelta(days=RISK_ACT_DELAY)
            for rec in self:
                if rec.business_risk_id and not rec.parent_id:
                    # close preceding activities
                    activity.search([
                        ('res_id', '=', rec.business_risk_id.id),
                        ('res_model_id', '=', res_model_id),
                        ('summary', 'like', 'Select and implement measures to modify risk')
                    ]).action_done()

                    # Next activity
                    activity.create({
                        'res_id': rec.business_risk_id.id,
                        'res_model_id': res_model_id,
                        'activity_type_id': self.env.ref('risk_management.risk_activity_todo').id,
                        'summary': 'Reassess the  risk to make sure that risk treatment has been effective',
                        'date_deadline': fields.Date.to_string(act_deadline_date)
                    })
        return res



