from odoo import models, fields, api


class Project(models.Model):
    _inherit = 'project.project'

    @api.depends('process_ids')
    def _compute_count_process(self):
        for rec in self:
            rec.process_count = len(rec.process_ids)

    process_ids = fields.One2many('risk_management.project_process', string="Process", inverse_name='project_id')
    process_count = fields.Integer(compute="_compute_count_process")
    risk_count = fields.Integer(compute='_compute_risk_count', string='Risks')

    @api.multi
    def _compute_risk_count(self):
        for rec in self:
            if rec.process_ids:
                rec.risk_count = sum([process.risk_count for process in rec.process_ids])
            else:
                rec.risk_count = 0

    @api.multi
    def get_or_add_risk_treatment_proc(self):
        """get or create a process a process named `Risk Treatment`"""
        project_process = self.env['risk_management.project_process']
        responsible = self.env.user
        for rec in self:
            # look for a project process with `risk management` in their name
            risk_treatment_process = project_process.sudo().search([
                '&',
                ('project_id', '=', rec.id),
                ('name', 'ilike', 'risk treatment')
            ])
            if not risk_treatment_process.exists():
                # it's assumed there is no risk management process in the current project
                risk_treatment_process = project_process.sudo().create({
                    'name': 'Risk Treatment',
                    'process_type': 'M',
                    'description': """
                    <p>The purpose of this process is to select and implement measures to modify the risks. 
                    These measures can include avoiding, optimizing, transferring or retaining risk.</p>
                    """,
                    'responsible_id': responsible.id,
                    'project_id': rec.id
                })

            return risk_treatment_process.exists()[0]

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

    @api.model
    def create(self, vals):
        project = super(Project, self).create(vals)
        project_process = self.env['risk_management.project_process']
        project_process.create(
            {
                'name': 'Process Zero',
                'description': """
                    <p>This process represent the overall process of project, to be used for activities, 
                    methods or risks in the absence of more specific processes.</p>
                    """,
                'project_id': project.id
            }
        )
        return project


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

    process_id = fields.Many2one('risk_management.project_process', ondelete='cascade', string='Process',
                                 domain="[('project_id', '=', project_id)]")
    process_name = fields.Char(related='process_id.name')
    target_criterium = fields.Selection(selection=[('D', 'Detectability'), ('O', 'Occurrence'), ('S', 'Severity')],
                                        string='Target Criterium')

    @api.onchange('process_id')
    def _onchange_process_name(self):
        if self.process_name != 'Risk Treatment':
            self.project_risk_id = False
            self.business_risk_id = False
