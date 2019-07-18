# -*- coding: utf-8 -*-

import logging
import math
from odoo import models, fields, api, exceptions

_logger = logging.getLogger(__name__)


class BaseProcess(models.AbstractModel):
    _name = 'risk_management.base_process'
    _inherit = ['mail.thread']
    _order = 'sequence asc, name, id'

    name = fields.Char(required=True, index=True, translate=True, copy=False, track_visibility=True)
    process_type = fields.Selection(selection=[('O', 'Operations'), ('M', 'Management'), ('S', 'Support')], default='O',
                                    required=True, string='Process type', track_visibility='onchange')
    description = fields.Html(translate=True, string="Description", track_visibility='onchange', index=True)
    responsible_id = fields.Many2one('res.users', ondelete='set null', string='Responsible',
                                     default=lambda self: self.env.user, index=True, track_visibility='onchange')
    method_count = fields.Integer(compute='_compute_method_count', string="Methods")
    sequence = fields.Integer(compute="_compute_sequence", default=10, string='Rank', store=True, compute_sudo=True)


class BaseProcessData(models.AbstractModel):
    _name = 'risk_management.base_process_data'
    _sql_constraints = [
        (
            'data_name_unique',
            'UNIQUE(name, business_process_id, partner_id)',
            'The process data name must be unique within the same process.'
        ),
        ('check_only_one_source',
         'CHECK((partner_id IS NOT NULL AND business_process_id IS NULL) OR'
         '(partner_id IS NULL and business_process_id IS NOT NULL))',
         'A process can only have one source.'
         )
    ]
    name = fields.Char(required=True, index=True, translate=True, copy=False)
    is_customer_voice = fields.Boolean('Consumer Voice?', compute='_compute_is_costumer_voice',
                                       help="Does this data relay the customer voice?",
                                       search='_search_is_customer_voice')
    partner_id = fields.Many2one('res.partner.category', string='External Source', ondelete='cascade',
                                 domain=lambda self: [('id', 'child_of',
                                                       self.env.ref('risk_management.process_partner').id)],
                                 help='Must be a child of `Process partner` category')
    default_partner_cat_parent_id = fields.Many2one('res.partner.category', default=lambda self: self.env.ref(
        'risk_management.process_partner'), readonly=True)

    @api.constrains('user_process_ids', 'business_process_id')
    def _check_provider_not_in_consumers(self):
        """Data source should not be a user of said data"""
        for data in self:
            if data.business_process_id and data.business_process_id in data.user_process_ids:
                raise exceptions.ValidationError("The data source cannot be a user of the data")


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
    output_data_ids = fields.One2many('risk_management.business_process_data', inverse_name='business_process_id',
                                      string='Output data')
    input_data_ids = fields.Many2many(comodel_name='risk_management.business_process_data',
                                      relation='risk_management_input_ids_user_ids_rel',
                                      column1='input_data_ids', column2='user_process_ids', string="Input data",
                                      domain=lambda self: [('id', 'not in', self.output_data_ids.ids),
                                                           ('business_process_id.business_id', '=',
                                                            self.business_id.id)])
    method_ids = fields.One2many('risk_management.business_process.method',
                                 inverse_name='process_id', string='Methods')
    task_count = fields.Integer(compute="_compute_task_count", string='Tasks')
    risk_ids = fields.One2many('risk_management.business_risk', inverse_name='process_id', string='Identified risks')
    risk_count = fields.Integer(compute='_compute_risk_count', string='Risks')
    module = fields.Many2one('ir.module.module', ondelete='set null', string='Odoo Module', copy=False,
                             domain=[('state', '=', 'installed')], track_visibility='always')
    is_core = fields.Boolean(compute='_compute_is_core')

    @api.constrains('input_data_ids', 'id')
    def _check_output_not_in_input(self):
        """This is further enforced by the `input_data_ids` field domain"""
        for process in self:
            for data in process.output_data_ids:
                if data in process.input_data_ids:
                    raise exceptions.ValidationError("A process cannot consume its own output")

    @api.returns('self')
    def get_provider_processes(self):
        """Returns the users of self's output data that are 'customer voice', if any"""
        self.ensure_one()
        proc = self.env[self._name]
        for data in self.output_data_ids.filtered('is_customer_voice'):
            proc |= data.user_process_ids
        return proc

    @api.multi
    def get_customers(self):
        """Returns sources of self's input data that are `customer voice`, if any"""
        self.ensure_one()
        src = {
            'external': self.env['res.partner.category'],
            'internal': self.env[self._name]
        }
        for data in self.input_data_ids.filtered('is_customer_voice'):
            if data.partner_id:
                src['external'] |= data.partner_id
            elif data.business_process_id:
                src['internal'] |= data.business_process_id
        return src

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

    @api.depends('output_data_ids')
    def _compute_is_core(self):
        for rec in self:
            if rec.output_data_ids.filtered('is_customer_voice').mapped('user_process_ids'):
                rec.is_core = True
            else:
                rec.is_core = False

    @api.depends("process_type", 'input_data_ids')
    def _compute_sequence(self):
        """
        The sequence of a process depends on its type: operations come first and are ordered according to their proximity
        to external clients; then management processes and finally support processes.
        :return: int
        """
        proc = self.env['risk_management.business_process']
        op = proc.search(['|', ('process_type', '=', 'O'), ('is_core', '=', True)])
        mp = proc.search([('process_type', '=', 'M'), ('is_core', '=', False)])
        for rec in self:
            if rec.process_type == 'O' or rec.is_core:
                default = 10
                if rec.get_customers()['external']:
                    rec.sequence = default
                elif rec.get_customers()['internal']:
                    rec.sequence = 1 + min([proc.sequence for proc in rec.get_customers()['internal']])
                else:
                    rec.sequence = 100
            elif rec.process_type == 'M':
                default = max([rec.sequence for rec in op]) if op else 20
                if rec.output_data_ids:
                    rec.sequence = default + math.floor(default * (1/len(rec.output_data_ids)))
                else:
                    rec.sequence = default + 100
            else:
                default = max([rec.sequence for rec in mp]) if mp else 30
                if rec.output_data_ids:
                    rec.sequence = default + math.floor(default * (1 / len(rec.output_data_ids)))
                else:
                    rec.sequence = default + 100

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

    business_process_id = fields.Many2one('risk_management.business_process', string='Internal source',
                                          ondelete='cascade')
    ref_response_ids = fields.One2many('risk_management.business_process_data', inverse_name='ref_request_id',
                                       domain=lambda self: [('is_customer_voice', '=', False)],
                                       string='Response Ref.')
    ref_request_id = fields.Many2one('risk_management.business_process_data', 'Request Ref.',
                                     domain=lambda self: [('id', 'in', self.business_process_id.input_data_ids.ids)])
    user_process_ids = fields.Many2many(comodel_name='risk_management.business_process',
                                        relation='risk_management_input_ids_user_ids_rel',
                                        column1='user_process_ids', column2='input_data_ids',
                                        string="User processes")

    @api.depends('partner_id', 'ref_request_id')
    def _compute_is_customer_voice(self):
        """a data is customer voice if it was input by an Customer or if it relays one."""
        customers = self.env[
            'res.partner.category'
        ].search([('id', 'child_of', self.env.ref('risk_management.process_external_customer').id)])
        for rec in self:
            if (
                    rec.partner_id and rec.partner.id in customers.ids
            ) or rec.ref_request_id.is_customer_voice:
                rec.is_customer_voice = True
            else:
                rec.is_customer_voice = False

    def _search_is_customer_voice(self, operator, value):
        customers = self.env[
            'res.partner.category'
        ].search([('id', 'child_of', self.env.ref('risk_management.process_external_customer').id)])

        if operator not in ('=', '!=') or value not in (0, 1):
            recs = self
        if operator == '=':
            if value:
                recs = self.filtered(lambda rec: rec.partner_id and rec.partner_id.id in customers.ids)
            else:
                recs = self.filtered(
                    lambda rec: not rec.partner_id.id or rec.partner_id.id not in customers.ids)
        else:
            if value:
                recs = self.filtered(
                    lambda rec: not rec.ext_provider_id.id or rec.ext_provider_id.id not in customers.ids)
            else:
                recs = self.filtered(lambda rec: rec.partner_id and rec.partner_id.id in customers.ids)
        return [('id', 'in', [rec.id for rec in recs])]

    @api.onchange('is_customer_voice')
    def _onchange_is_customer_voice(self):
        customer_proc = self.business_process_id.get_customers()['internal']
        if self.is_customer_voice:
            return {'domain': {
                'user_process_ids': [('id', '!=', self.business_process_id.id),
                                     ('id', 'not in', customer_proc.ids),
                                     ('business_id', '=', self.business_process_id.business_id.id)]
            }}
        else:
            return {'domain': {
                'user_process_ids': [('id', '!=', self.business_process_id.id),
                                     ('business_id', '=', self.business_process_id.business_id.id)]
            }}


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
                                    domain=lambda self: [
                                        ('business_process_id.business_id', '=', self.process_id.business_id.id),
                                        ('business_process_id.process_type', '=', 'M')
                                    ],
                                    help='Output data reference')
    author_name = fields.Char('From process', related='output_ref_id.business_process_id.name', readonly=True)


class ProjectProcessData(models.Model):
    _name = 'risk_management.project_process_data'
    _description = 'A project process input or output'
    _inherit = ['risk_management.base_process_data']

    int_provider_id = fields.Many2one('risk_management.project_process', string='Origin (internal)',
                                      ondelete='cascade')
    user_process_ids = fields.Many2many(comodel_name='risk_management.project_process',
                                        relation='risk_management_project_input_ids_user_ids_rel',
                                        column1='user_process_ids', column2='input_data_ids',
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
                                      relation='risk_management_project_input_ids_user_ids_rel',
                                      column1='input_data_ids', column2='user_process_ids', string='Input Data',
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
                if rec.get_input_partner_cats().exists():
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
                                    domain=lambda self: [
                                        ('int_provider_id.project_id', '=', self.process_id.project_id.id),
                                        ('int_provider_id.process_type', '=', 'M')
                                    ],
                                    help='Output data reference')
    author_name = fields.Char('From process', related='output_ref_id.int_provider_id.name', readonly=True)
