from odoo import models, fields, api


class Project(models.Model):
    _inherit = 'project.project'

    @api.depends('process_ids')
    def _compute_count_process(self):
        for rec in self:
            rec.process_count = len(rec.process_ids)

    process_ids = fields.One2many('risk_management.project_process', string="Process", inverse_name='project_id')
    process_count = fields.Integer(compute="_compute_count_process")

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


class Task(models.Model):
    _inherit = 'project.task'

    def _get_default_risk(self):
        default_risk_id = self.env.context.get('default_risk_id', False)
        if default_risk_id:
            return default_risk_id.exists()

    def get_target_selection(self):
        if not self.process_id:
            return []
        else:
            return [('D', 'Detectability'), ('O', 'Occurrence'), ('S', 'Severity')]

    risk_id = fields.Many2one(comodel_name='risk_management.project_risk', string='Risk', default=_get_default_risk,
                              domain="[('process_id.project_id', '=', project_id)]")

    process_id = fields.Many2one('risk_management.project_process', ondelete='cascade', string='Process',
                                 domain="[('project_id', '=', project_id)]")
    target_criterium = fields.Selection(selection=get_target_selection, string='Target Criterium')
