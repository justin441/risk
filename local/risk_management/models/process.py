# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, exceptions

_logger = logging.getLogger(__name__)


class BaseProcess(models.AbstractModel):
    _name = 'risk_management.base_process'
    _inherit = ['mail.thread']
    _order = 'sequence asc, name, id'

    name = fields.Char(required=True, index=True, translate=True, copy=False, track_visibility=True)
    process_type = fields.Selection(selection=[('O', 'Operation'), ('M', 'Management'), ('S', 'Support')], default='O',
                                    required=True, string='Process type', track_visibility='onchange')
    description = fields.Html(translate=True, string="Description", track_visibility='onchange', index=True)
    responsible_id = fields.Many2one('res.users', ondelete='set null', string='Responsible',
                                     default=lambda self: self.env.user, index=True, track_visibility='onchange')
    method_count = fields.Integer(compute='_compute_method_count', string="Methods")
    sequence = fields.Integer(compute="_compute_sequence", default=10, string='Rank', store=True, compute_sudo=True)
    is_core = fields.Boolean(compute='_compute_is_core', string='Is core process', search='_search_is_core',
                             help='Is this a core process')

    @api.constrains('input_data_ids', 'id')
    def _check_output_not_in_input(self):
        for process in self:
            for data in process.output_data_ids:
                if data in process.input_data_ids:
                    raise exceptions.ValidationError("A process cannot consume its own output")

    @api.multi
    def get_input_int_providers(self):
        self.ensure_one()
        int_data = self.input_data_ids.filtered('int_provider_id')  # filter out data of external origin
        return int_data.mapped('int_provider_id')

    @api.multi
    def get_input_ext_provider_cats(self):
        self.ensure_one()
        ext_data = self.input_data_ids.filtered('ext_provider_cat_id')  # filter out data of internal origin
        return ext_data.mapped('ext_provider_cat_id')

    @api.multi
    def get_output_users(self):
        self.ensure_one()
        c = self.env[self._name]
        for data in self.output_data_ids:
            c |= data.consumer_ids
        return c

    @api.depends('input_data_ids')
    def _compute_is_core(self):
        for rec in self:
            if rec.input_data_ids.filtered('is_customer_voice').exists():
                rec.is_core = True
            else:
                rec.is_core = False

    def _search_is_core(self, operator, value):
        def is_core(rec):
            if rec.input_data_ids.filtered('is_customer_voice').exists():
                return True
            return False

        if operator not in ('=', "!=") or value not in (0, 1):
            recs = self
        elif operator == '=':
            if value:
                recs = self.filtered(is_core)
            else:
                recs = self - self.filtered(is_core)
        else:
            if value:
                recs = self - self.filtered(is_core)
            else:
                recs = self.filtered(is_core)
        return [('id', 'in', [rec.id for rec in recs])]


class BaseProcessData(models.AbstractModel):
    _name = 'risk_management.base_process_data'
    _sql_constraints = [
        (
            'data_name_unique',
            'UNIQUE(name, int_provider_id, ext_provider_cat_id)',
            'The process data name must be unique within the same process.'
        ),
        ('check_only_one_provider',
         'CHECK((ext_provider_cat_id IS NOT NULL AND int_provider_id IS NULL) OR'
         '(ext_provider_cat_id IS NULL and int_provider_id IS NOT NULL))',
         'A process can only have one provider.'
         )
    ]
    name = fields.Char(required=True, index=True, translate=True, copy=False)
    is_customer_voice = fields.Boolean('Consumer Voice?', default=False,
                                       help="Does this data relay the customer voice?")
    ext_provider_cat_id = fields.Many2one('res.partner.category', string='External proviser', ondelete='cascade',
                                          domain=lambda self: [('id', 'child_of',
                                                                self.env.ref('risk_management.process_partner').id)],
                                          help='Must be a child of `Process partner` category')

    @api.constrains('consumer_ids', 'int_provider_id')
    def _check_provider_not_in_consumers(self):
        """Data provider should not be a consumer of said data"""
        for data in self:
            if data.int_provider_id and data.int_provider_id in data.consumer_ids:
                raise exceptions.ValidationError("A data's provider cannot be a consumer of that data")


class BaseProcessMethod(models.AbstractModel):
    _name = 'risk_management.base_process_method'
    _sql_constraints = [
        (
            'method_name_unique',
            'UNIQUE(name, process_id)',
            'A procedure with the same name already exist on this process'
        )
    ]

    name = fields.Char(translate=True, string='Title', required=True, copy=False, index=True)
    content = fields.Html(translate=True)


class BusinessProcess(models.Model):
    _name = 'risk_management.business_process'
    _description = 'A Business process'
    _inherit = ['risk_management.base_process']
    _sql_constraints = [
        ('process_name_unique_for_company',
         'UNIQUE(name, business_id)',
         'The process name must be unique.')
    ]

    business_id = fields.Many2one('res.company', ondelete='cascade', string='Business Unit', required=True,
                                  default=lambda self: self.env.user.company_id,
                                  readonly=True, copy=False)
    task_ids = fields.One2many('risk_management.business_process.task', inverse_name='process_id', string='Tasks')
    output_data_ids = fields.One2many('risk_management.business_process_data', inverse_name='int_provider_id',
                                      string='Output data')
    input_data_ids = fields.Many2many(comodel_name='risk_management.business_process_data',
                                      relation='risk_management_input_ids_consumers_ids_rel',
                                      column1='input_data_ids', column2='consumer_ids', string="Input data",
                                      domain="[('id', 'not in', output_data_ids),"
                                             "('int_provider_id.business_id', '=', business_id)]")
    method_ids = fields.One2many('risk_management.business_process.method',
                                 inverse_name='process_id', string='Methods')
    task_count = fields.Integer(compute="_compute_task_count", string='Tasks')
    risk_ids = fields.One2many('risk_management.business_risk', inverse_name='process_id', string='Identified risks')
    risk_count = fields.Integer(compute='_compute_risk_count', string='Risks')
    module = fields.Many2one('ir.module.module', ondelete='set null', string='Odoo Module', copy=False,
                             domain=[('state', '=', 'installed')], track_visibility='always')

    @api.depends('task_ids')
    def _compute_task_count(self):
        for rec in self:
            rec.task_count = len(rec.task_ids)

    @api.depends('method_ids')
    def _compute_method_count(self):
        for rec in self:
            rec.method_count = len(rec.method_ids)

    @api.depends('risk_ids')
    def _compute_risk_count(self):
        for rec in self:
            rec.risk_count = len(rec.risk_ids)

    @api.depends("process_type", 'input_data_ids')
    def _compute_sequence(self):
        """
        The sequence of a process depends on its type: operations come first and are order according to their proximity
        to external clients; then management processes and finally support processes.
        :return: int
        """

        for rec in self:
            operational_processes = rec.env[
                'risk_management.business_process'].search(['|', '&',
                                                            ('business_id', '=', rec.business_id.id),
                                                            ('process_type', '=', 'O'),
                                                            '&',
                                                            ('business_id', '=', rec.business_id.id),
                                                            ('is_core', '=', 1)
                                                            ])
            management_processes = rec.env[
                'risk_management.business_process'].search(['&', '&',
                                                            ('business_id', '=', rec.business_id.id),
                                                            ('process_type', '=', 'M'),
                                                            ('is_core', '=', 0)
                                                            ])
            default_seq = 10
            if rec.process_type == "O" or rec.is_core:
                if rec.get_input_ext_provider_cats().exists():
                    rec.sequence = default_seq
                else:
                    if rec.get_input_int_providers().exists():
                        operational_providers = rec.get_input_int_providers().filtered(
                            lambda record: record.process_type == 'O' or record.is_core)
                        rec.sequence = default_seq + sum([record.sequence for record in operational_providers])
                    else:
                        rec.sequence = default_seq
            elif rec.process_type == "M" and not rec.is_core:
                default = default_seq
                if operational_processes.exists():
                    default += max([record.sequence for record in operational_processes])
                if rec.get_input_int_providers().exists():
                    mgt_providers = rec.get_input_int_providers().filtered(
                        lambda record: record.process_type == 'M' and not record.is_core
                    )
                    rec.sequence = default + sum(
                        [record.sequence for record in mgt_providers])
                else:
                    rec.sequence = default
            elif rec.process_type == "S" and not rec.is_core:
                default = default_seq
                if management_processes.exists():
                    default += max([record.sequence for record in management_processes])
                if rec.get_input_int_providers().exists():
                    support_providers = rec.get_input_int_providers().filtered(
                        lambda record: record.process_type == 'S' and not record.is_core
                    )
                    rec.sequence = default + sum(
                        [record.sequence for record in support_providers])
                else:
                    rec.sequence = default

    @api.multi
    def _notification_recipients(self, message, groups):
        groups = super(BusinessProcess, self)._notification_recipients(message, groups)

        for group_name, group_method, group_data in groups:
            group_data['has_button_access'] = True

        return groups

    @api.multi
    def message_subscribe(self, partner_ids=None, channel_ids=None, subtype_ids=None, force=True):
        """ Subscribe to all existing risks on the process when subscribing to a business process """
        res = super(BusinessProcess, self).message_subscribe(partner_ids=partner_ids, channel_ids=channel_ids,
                                                             subtype_ids=subtype_ids, force=force)
        if not subtype_ids or any(subtype.parent_id.res_model == 'business_management.business_risk' for subtype in
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


class BusinessProcessData(models.Model):
    _name = 'risk_management.business_process_data'
    _description = 'Business Process input or output'
    _inherit = ['risk_management.base_process_data']

    int_provider_id = fields.Many2one('risk_management.business_process', string='Origin (internal)',
                                      ondelete='cascade')
    consumer_ids = fields.Many2many(comodel_name='risk_management.business_process',
                                    relation='risk_management_input_ids_consumers_ids_rel',
                                    column1='consumer_ids', column2='input_data_ids',
                                    domain="[('id', '!=', int_provider_id),"
                                           "('business_id', '=', int_provider_id.business_id)]",
                                    string="Users")


class BusinessProcessTask(models.Model):
    _name = 'risk_management.business_process.task'
    _description = 'An activity in a process'
    _order = 'sequence, name'
    _sql_constraints = [
        (
            'task_name_unique',
            'UNIQUE(name, process_id)',
            'A task with the same name already exists in this process.'
        )
    ]

    name = fields.Char(required=True, translate=True, index=True)
    description = fields.Text(translate=True, index=True)
    owner_id = fields.Many2one('res.users', ondelete="set null")
    sequence = fields.Integer(default=10)
    process_id = fields.Many2one('risk_management.business_process', ondelete='cascade', string="Process", index=True)
    manager_id = fields.Many2one('res.users', related='process_id.responsible_id', readonly=True,
                                 related_sudo=False, string='Process Manager')


class BusinessProcessMethod(models.Model):
    _name = "risk_management.business_process.method"
    _description = "Rules and policies for the business process"
    _inherit = ['risk_management.base_process_method']
    process_id = fields.Many2one(comodel_name='risk_management.business_process', string='User process')
    output_ref_id = fields.Many2one(comodel_name='risk_management.business_process_data', string='Output ref.',
                                    domain="[('int_provider_id.project_id', '=', process_id.project_id),"
                                           "('int_provider_id.process_type', '=', 'M')]",
                                    help='Output data reference')
    author_name = fields.Char('From process', related='output_ref_id.int_provider_id.name', readonly=True)


class ProjectProcessData(models.Model):
    _name = 'risk_management.project_process_data'
    _description = 'A project process input or output'
    _inherit = ['risk_management.base_process_data']

    int_provider_id = fields.Many2one('risk_management.project_process', string='Origin (internal)',
                                      ondelete='cascade')
    consumer_ids = fields.Many2many(comodel_name='risk_management.project_process',
                                    relation='risk_management_project_input_ids_consumers_ids_rel',
                                    column1='consumer_ids', column2='input_data_ids',
                                    domain="[('id', '!=', int_provider_id),"
                                           "('project_id', '=', int_provider_id.project_id)]",
                                    string="Users")


class ProjectProcess(models.Model):
    _name = 'risk_management.project_process'
    _description = 'A project process'
    _inherit = ['risk_management.base_process']
    _sql_constraints = [
        ('process_name_unique_for_project',
         'UNIQUE(name, project_id)',
         'The process name must be unique.')
    ]

    project_id = fields.Many2one('project.project', string='Project', ondelete='cascade',
                                 default=lambda self: self.env.context.get('default_project_id', False),
                                 index=True, track_visibility='onchange')
    task_ids = fields.One2many('project.task', string='Tasks', inverse_name='process_id',
                               domain=lambda self: [('project_id', '=', self.project_id.id), '|',
                                                    ('stage_id.fold', '=', False), ('stage_id', '=', False)])
    method_ids = fields.One2many('risk_management.project_process.method', string='Methods', inverse_name='process_id')
    output_data_ids = fields.One2many('risk_management.project_process_data', inverse_name='int_provider_id',
                                      string='Output data')
    input_data_ids = fields.Many2many('risk_management.project_process_data',
                                      relation='risk_management_project_input_ids_consumers_ids_rel',
                                      column1='input_data_ids', column2='consumer_ids', string='Input Data',
                                      domain="[('id', 'not in', output_data_ids),"
                                             "('int_provider_id.project_id', '=', project_id)]"
                                      )
    task_count = fields.Integer(string='Tasks', compute="_compute_task_count")
    method_count = fields.Integer(string='Method', compute="_compute_method_count")
    risk_ids = fields.One2many('risk_management.project_risk', inverse_name='process_id', string='Identified risks')
    risk_count = fields.Integer(compute='_compute_risk_count', string='Risks')

    @api.depends('task_ids')
    def _compute_task_count(self):
        for rec in self:
            rec.task_count = len(rec.task_ids)

    @api.depends('method_ids')
    def _compute_method_count(self):
        for rec in self:
            rec.method_count = len(rec.method_ids)

    @api.depends('risk_ids')
    def _compute_risk_count(self):
        for rec in self:
            rec.risk_count = len(rec.risk_ids)

    @api.depends("process_type", 'input_data_ids', 'output_data_ids')
    def _compute_sequence(self):
        """
        The sequence of a process depends on its type: operations come first and are order according to their proximity
        to external clients; then management processes and finally support processes
        :return: int
        """

        for rec in self:
            operational_processes = rec.env[
                'risk_management.project_process'].search(['|', '&',
                                                           ('project_id', '=', rec.project_id.id),
                                                           ('process_type', '=', 'O'),
                                                           '&',
                                                           ('project_id', '=', rec.project_id.id),
                                                           ('is_core', '=', 1)
                                                           ])
            management_processes = rec.env[
                'risk_management.project_process'].search(['&', '&',
                                                           ('project_id', '=', rec.project_id.id),
                                                           ('process_type', '=', 'M'),
                                                           ('is_core', '=', 0)
                                                           ])
            default_seq = 10
            if rec.process_type == "O" or rec.is_core:
                if rec.get_input_ext_provider_cats().exists():
                    rec.sequence = default_seq
                else:
                    if rec.get_input_int_providers().exists():
                        operational_providers = rec.get_input_int_providers().filtered(
                            lambda record: record.process_type == 'O' or record.is_core)
                        rec.sequence = default_seq + sum([record.sequence for record in operational_providers])
                    else:
                        rec.sequence = default_seq
            elif rec.process_type == "M" and not rec.is_core:
                default = default_seq
                if operational_processes.exists():
                    default += max([record.sequence for record in operational_processes])
                if rec.get_input_int_providers().exists():
                    mgt_providers = rec.get_input_int_providers().filtered(
                        lambda record: record.process_type == 'M' and not record.is_core
                    )
                    rec.sequence = default + sum(
                        [record.sequence for record in mgt_providers])
                else:
                    rec.sequence = default
            elif rec.process_type == "S" and not rec.is_core:
                default = default_seq
                if management_processes.exists():
                    default += max([record.sequence for record in management_processes])
                if rec.get_input_int_providers().exists():
                    support_providers = rec.get_input_int_providers().filtered(
                        lambda record: record.process_type == 'S' and not record.is_core
                    )
                    rec.sequence = default + sum(
                        [record.sequence for record in support_providers])
                else:
                    rec.sequence = default

    @api.multi
    def _notification_recipients(self, message, groups):
        groups = super(ProjectProcess, self)._notification_recipients(message, groups)

        for group_name, group_method, group_data in groups:
            group_data['has_button_access'] = True

        return groups

    @api.multi
    def message_subscribe(self, partner_ids=None, channel_ids=None, subtype_ids=None, force=True):
        """ Subscribe to all existing risks on the process when subscribing to a project process """
        res = super(ProjectProcess, self).message_subscribe(partner_ids=partner_ids, channel_ids=channel_ids,
                                                            subtype_ids=subtype_ids, force=force)
        if not subtype_ids or any(subtype.parent_id.res_model == 'business_management.business_risk' for subtype in
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


class ProjectMethod(models.Model):
    _name = "risk_management.project_process.method"
    _description = "Rules and policies for the project process"
    _inherit = ['risk_management.base_process_method']
    process_id = fields.Many2one(comodel_name='risk_management.project_process', string='User process')
    output_ref_id = fields.Many2one(comodel_name='risk_management.project_process_data', string='Output ref.',
                                    domain="[('int_provider_id.process_type', '=', 'M')]",
                                    help='Output data reference')
    author_name = fields.Char('From process', related='output_ref_id.int_provider_id.name', readonly=True)
