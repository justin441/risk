# -*- coding: utf-8 -*-

import logging
import math
from odoo import models, fields, api, exceptions, _

_logger = logging.getLogger(__name__)


class BaseProcess(models.AbstractModel):
    _name = 'risk_management.base_process'
    _inherit = ['mail.thread']
    _order = 'sequence asc, name, id'

    process_type = fields.Selection(selection=[('O', 'Operations'), ('M', 'Management'), ('S', 'Support'),
                                               ('PM', 'Project Management')], default='O',
                                    required=True, string='Process type', track_visibility='onchange')
    description = fields.Html(translate=True, string="Description", track_visibility='onchange', index=True)
    method_count = fields.Integer(compute='_compute_method_count', string="Methods")
    sequence = fields.Integer(compute="_compute_sequence", default=10, string='Rank', store=True)
    color = fields.Integer(string='Color Index', compute='_compute_color', inverse='_inverse_color', store=True)


class BusinessProcess(models.Model):
    _name = 'risk_management.business_process'
    _description = 'Business process'
    _inherit = ['risk_management.base_process']
    _inherits = {'account.analytic.account': "analytic_account_id"}

    task_ids = fields.One2many('risk_management.business_process.task', inverse_name='business_process_id',
                               string='Tasks')
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic',
                                          help="Link this Process to an analytic account if you need financial "
                                               "management on projects. It enables you to connect processes with "
                                               "budgets, planning, cost and revenue analysis.",
                                          ondelete="restrict", required=True, auto_join=True)
    output_data_ids = fields.One2many('risk_management.business_process.input_output',
                                      inverse_name='business_process_id',
                                      string='Output data')
    input_data_ids = fields.Many2many(comodel_name='risk_management.business_process.input_output',
                                      relation='risk_management_input_ids_user_ids_rel',
                                      column1='business_process_id', column2='input_id', string="Input data",
                                      domain=lambda self: [('id', 'not in', self.output_data_ids.ids),
                                                           ('business_process_id.company_id', '=',
                                                            self.company_id.id)])
    method_ids = fields.One2many('risk_management.business_process.method',
                                 inverse_name='business_process_id', string='Methods')
    task_count = fields.Integer(compute="_compute_task_count", string='Tasks')
    risk_ids = fields.Many2many('risk_management.business_risk', relation='risk_management_process_risk_rel',
                                column1='process_id', column2='risk_id', )
    risk_count = fields.Integer(compute='_compute_risk_count', string='Risks')
    module = fields.Many2one('ir.module.module', ondelete='set null', string='Odoo Module', copy=False,
                              track_visibility='always',
                             help='This provides a hook for developing a solution to measure the performance of the '
                                  'process.')
    is_core = fields.Boolean(compute='_compute_is_core', store=True, string='Core Business Process?',
                             help='Is this a core business process? It is if it processes customer data.')

    responsible_id = fields.Many2one('res.users', ondelete='set null', string='Responsible',
                                     default=lambda self: self.env.user, index=True, track_visibility='onchange',
                                     domain=lambda self: [('id', 'in', self.company_id.user_ids.ids)])
    user_ids = fields.Many2many('res.users', 'risk_management_users_process_rel', 'business_process_id', 'user_id',
                                string='Staff', _compute='_compute_staff', track_visilibity='always',
                                store=True)

    @api.multi
    def add_partner_input(self):
        self.ensure_one()
        form = self.env.ref('risk_management.process_data_form')
        ctx = {
            'default_source_part_cat_id': self.env.ref('risk_management.process_partner_cat_customer').id,
            'default_user_process_ids': [(4, self.id)]

        }
        return {
            'name': _('New Input from partner'),
            'type': 'ir.actions.act_window',
            'res_model': 'risk_management.business_process.input_output',
            'view_type': 'form',
            'view_mode': 'form',
            'views': [(form.id, 'form')],
            'view_id': form.id,
            'target': 'new',
            'context': ctx
        }

    @api.depends('task_ids.owner_id')
    def _compute_staff(self):
        for rec in self:
            rec.user_ids = rec.task_ids.mapped('owner_id')

    @api.constrains('input_data_ids')
    def _check_output_not_in_input(self):
        """This is further enforced by the `input_data_ids` field domain"""
        for process in self:
            for data in process.input_data_ids:
                if data in process.output_data_ids:
                    raise exceptions.ValidationError(_("A process cannot consume its own output"))

    @api.returns('self')
    def get_provider_processes(self):
        """Returns the users of self's output  that are 'customer voice', if any"""
        self.ensure_one()
        proc = self.env[self._name]
        for data in self.output_data_ids.filtered('is_customer_voice'):
            proc |= data.user_process_ids.filtered('is_core')
        return proc

    @api.multi
    def get_customers(self):
        """Returns sources of self's input data that are `customer voice`, if any
        :return type: dict with keys: - `external`: children of customer partner category, external customers
                                      - `internal`: business processes, internal customers
        """
        self.ensure_one()
        src = {
            'external': self.env['res.partner.category'],
            'internal': self.env[self._name]
        }
        for data in self.input_data_ids.filtered('is_customer_voice'):
            if data.source_part_cat_id:
                src['external'] |= data.source_part_cat_id
            elif self.is_core and data.business_process_id and data.business_process_id.is_core:
                src['internal'] |= data.business_process_id
        return src

    @api.depends('process_type')
    def _compute_color(self):
        for rec in self:
            if rec.process_type == 'O' or rec.is_core:
                rec.color = 1
            elif rec.process_type == 'M':
                rec.color = 5
            elif rec.process_type == 'S':
                rec.color = 2
            elif rec.process_type == 'PM':
                rec.color = 8

    def _inverse_color(self):
        pass

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
            if rec.risk_ids:
                # only take into account risk that have been evaluated
                rec.risk_count = len(rec.risk_ids.filtered('latest_level_value'))

    @api.depends('output_data_ids.is_customer_voice', 'input_data_ids.dest_partner_ids')
    def _compute_is_core(self):
        """
        A core process is one that outputs or relays data that are 'customer voice' to other processes or if self has an
        input that is a 'customer voice' and directly output to the customer partner category;
                - False otherwise
        """
        for rec in self:
            if rec.output_data_ids.filtered('is_customer_voice').mapped('user_process_ids') or (
                    rec.input_data_ids.filtered('is_customer_voice') and
                    rec.output_data_ids.mapped('dest_partner_ids'
                                               ) >= self.env.ref('risk_management.process_partner_cat_customer')):
                rec.is_core = True
            else:
                rec.is_core = False

    @api.depends("process_type", 'is_core', 'output_data_ids')
    def _compute_sequence(self):
        """
        The sequence of a process depends on its type: operations come first and are ordered according to their proximity
        to external clients; then management processes and finally support processes.
        :return: int
        """
        proc = self.env['risk_management.business_process']
        op = proc.search(['|', ('process_type', '=', 'O'), ('is_core', '=', True)])
        mp = proc.search([('process_type', '=', 'M'), ('is_core', '=', False)])
        sp = proc.search([('process_type', '=', 'S'), ('is_core', '=', False)])
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
                default = max([rec.sequence for rec in op]) if op else 30
                if rec.output_data_ids:
                    rec.sequence = default + math.floor(default * (1 / len(rec.output_data_ids)))
                else:
                    rec.sequence = default + 150
            elif rec.process_type == 'S':
                default = max([rec.sequence for rec in mp]) if mp else 50
                if rec.output_data_ids:
                    rec.sequence = default + math.floor(default * (1 / len(rec.output_data_ids)))
                else:
                    rec.sequence = default + 300
            else:
                default = max([rec.sequence for rec in sp]) if sp else 70
                if rec.output_data_ids:
                    rec.sequence = default + math.floor(default * (1 / len(rec.output_data_ids)))
                else:
                    rec.sequence = default + 600

    @api.model
    def _message_get_auto_subscribe_fields(self, updated_fields, auto_follow_fields=None):
        user_field_lst = super(BusinessProcess, self)._message_get_auto_subscribe_fields(updated_fields,
                                                                                         auto_follow_fields=None)
        user_field_lst.extend(['user_ids', 'responsible_id'])
        return user_field_lst

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

    def message_unsubscribe(self, partner_ids=None, channel_ids=None):
        """ Unsubscribe from all existing risks when unsubscribing from a business process """
        self.mapped('risk_ids').message_unsubscribe(partner_ids=partner_ids, channel_ids=channel_ids)
        return super(BusinessProcess, self).message_unsubscribe(partner_ids=partner_ids, channel_ids=channel_ids)

    @api.multi
    def write(self, vals):
        # all the processes with the same process_type have the same color
        if 'color' in vals:
            proc = to_change = self.env[self._name]
            color = vals.pop('color')
            existing = proc.search([('color', '=', color)])
            if existing:
                # there is already a group of process with this color
                import random
                colors = list(range(1, 11))
                colors.remove(color)
                existing.write({'color': random.choice(colors)})  # assign a random color to it
            for rec in self:
                recs = proc.search([('process_type', '=', rec.process_type)]) - rec
                if recs:
                    to_change |= recs
            to_change |= self
            super(BusinessProcess, to_change).write({'color': color})

        res = super(BusinessProcess, self).write(vals)

        return res

    @api.model
    def create(self, vals):
        same_type = self.env['risk_management.business_process'].search(
            [('process_type', '=', vals.get('process_type', 'O'))])

        if same_type:
            vals.update({'color': same_type.exists()[0].color})

        return super(BusinessProcess, self).create(vals)


class BusinessProcessIO(models.Model):
    _name = 'risk_management.business_process.input_output'
    _description = 'Business Process input or output'
    _order = "name, id"
    _sql_constraints = [
        (
            'data_name_unique',
            'UNIQUE(name, business_process_id, source_part_cat_id)',
            'The process data name must be unique within the same process.'
        ),
        ('check_only_one_source',
         'CHECK((source_part_cat_id IS NOT NULL AND business_process_id IS NULL) OR'
         '(source_part_cat_id IS NULL and business_process_id IS NOT NULL))',
         'A input or output can only have one source, either internal or external.'
         )
    ]
    name = fields.Char(required=True, index=True, translate=True, copy=False)
    description = fields.Html('Description', translate=True)
    is_customer_voice = fields.Boolean('Customer Voice?', compute='_compute_is_customer_voice',
                                       help="Does this data relay the customer voice?",
                                       search='_search_is_customer_voice')
    business_process_id = fields.Many2one(comodel_name='risk_management.business_process', string='Internal source',
                                          ondelete='cascade',
                                          default=lambda self: self.env.context.get('default_business_process_id'))
    company_id = fields.Many2one('res.company', related='business_process_id.company_id', string='Company')
    source_part_cat_id = fields.Many2one('res.partner.category', string='External Source', ondelete='cascade',
                                         domain=lambda self: [('id', 'child_of',
                                                               self.env.ref('risk_management.process_partner_cat').id)],
                                         help='Must be a child of `Process partner` category')
    origin_id = fields.Reference(selection=[('res.partner.category', 'Partner Category'),
                                            ('risk_management.business_process', 'Business Process')],
                                 str='Source', compute='_compute_origin', store=True)

    ref_input_ids = fields.Many2many('risk_management.business_process.input_output',
                                     relation='risk_management_data_ref_rel', column1='input_id',
                                     column2='output_id', string="Input Ref.",
                                     domain=lambda self: [('id', 'in', self.business_process_id.input_data_ids.ids)])
    ref_output_ids = fields.Many2many('risk_management.business_process.input_output', 'risk_management_data_ref_rel',
                                      column1='output_id', column2='input_id', string='Referenced By')
    dest_partner_ids = fields.Many2many('res.partner.category', string='External Recipients',
                                        relation='risk_management_data_partner_cat_rel', column1='data_id',
                                        column2='partner_category_id',
                                        domain=lambda self: [('id', 'child_of',
                                                              self.env.ref('risk_management.process_partner_cat').id)],
                                        help='Must be a child of `Process partner` category', )
    user_process_ids = fields.Many2many(comodel_name='risk_management.business_process',
                                        relation='risk_management_input_ids_user_ids_rel',
                                        column1='input_id', column2='business_process_id',
                                        string="Internal Recipients")
    channel_ids = fields.Many2many('risk_management.business_process.channel', string='Authorized Channels',
                                   relation='risk_management_data_channel_rel', column1='data_id',
                                   column2='channel_id')
    default_partner_cat_parent_id = fields.Many2one('res.partner.category', default=lambda self: self.env.ref(
        'risk_management.process_partner_cat'), readonly=True)
    attachment_ids = fields.One2many('ir.attachment', string='Attached Documents', compute='_compute_attachments')
    doc_count = fields.Integer(compute='_compute_attached_docs_count', string="Attachments")

    @api.depends('source_part_cat_id', 'business_process_id')
    def _compute_origin(self):
        for rec in self:
            if rec.id:
                if rec.business_process_id:
                    rec.origin_id = 'risk_management.business_process' + ',' + str(
                        rec.business_process_id.id)
                elif rec.source_part_cat_id:
                    rec.origin_id = 'res.partner.category' + ',' + str(rec.source_part_cat_id.id)
            else:
                rec.origin_id = False

    @api.depends('source_part_cat_id', 'ref_input_ids.is_customer_voice')
    def _compute_is_customer_voice(self):
        """a data is customer voice if it was input by an Customer or if it relays one."""
        customers = self.env[
            'res.partner.category'
        ].search([('id', 'child_of', self.env.ref('risk_management.process_partner_cat_customer').id)])

        for rec in self:
            if (rec.source_part_cat_id and rec.source_part_cat_id.id in customers.ids) \
                    or rec.ref_input_ids.filtered('is_customer_voice'):
                rec.is_customer_voice = True
            else:
                rec.is_customer_voice = False

    def _search_is_customer_voice(self, operator, value):
        customers = self.env[
            'res.partner.category'
        ].search([('id', 'child_of', self.env.ref('risk_management.process_partner_cat_customer').id)])

        def customer_voice(rec):
            return (rec.source_part_cat_id and rec.source_part_cat_id.id in customers.ids) or (
                    rec.ref_input_ids and rec.ref_input_ids.filtered(customer_voice)
            )

        if operator not in ('=', '!=') or value not in (0, 1):
            recs = self
        elif operator == '=':
            if value:
                recs = self.filtered(customer_voice)
            else:
                recs = self.filtered(lambda rec: not customer_voice(rec))
        else:
            if value:
                recs = self.filtered(lambda rec: not customer_voice(rec))
            else:
                recs = self.filtered(customer_voice)
        return [('id', 'in', [rec.id for rec in recs])]

    @api.onchange('is_customer_voice')
    def _onchange_is_customer_voice(self):
        if self.business_process_id:
            customers = self.business_process_id.get_customers()['internal']
            if self.is_customer_voice:
                return {'domain': {
                    'user_process_ids': [('id', '!=', self.business_process_id.id),
                                         ('id', 'not in', customers.ids),
                                         ('company_id', '=', self.business_process_id.company_id.id)]
                }}
            else:
                return {'domain': {
                    'user_process_ids': [
                        ('id', '!=', self.business_process_id.id),
                        ('company_id', '=', self.business_process_id.company_id.id)]
                }}

    def _compute_attachments(self):
        attachment = self.env['ir.attachment']
        for io in self:
            self.attachment_ids = attachment.search([
                    ('res_model', '=', 'risk_management.business_process.input_output'), ('res_id', '=', io.id)
                ])

    def _compute_attached_docs_count(self):
        for io in self:
            io.doc_count = len(io.attachment_ids)

    @api.multi
    def attachment_tree_view(self):
        self.ensure_one()
        domain = [
            ('res_model', '=', 'risk_management.business_process.input_output'), ('res_id', '=', self.id)
        ]
        return {
            'name': _('Attachments'),
            'domain': domain,
            'res_model': 'ir.attachment',
            'type': 'ir.actions.act_window',
            'view_id': False,
            'view_mode': 'kanban,tree,form',
            'view_type': 'form',
            'help': _('''
            <p class="oe_view_nocontent_create">
                Attach Documents to your processes input/output.
            </p>'''),
            'limit': 80,
            'context': "{'default_res_model': '%s','default_res_id': %d}" % (self._name, self.id)
        }

    @api.constrains('user_process_ids', 'business_process_id')
    def _check_provider_not_in_consumers(self):
        """Data source should not be a user of said data"""
        for data in self:
            if (data.business_process_id and data.business_process_id in data.user_process_ids) or (
                    data.source_part_cat_id and data.source_part_cat_id in data.dest_partner_ids
            ):
                raise exceptions.ValidationError(_("The data source cannot be a recipient of the data"))

    @api.constrains('source_part_cat_id', 'ref_input_ids')
    def _check_ext_input_no_ref(self):
        if self.source_part_cat_id and self.ref_input_ids:
            raise exceptions.ValidationError(_("Input from partner can't have input references"))

    @api.constrains('source_part_cat_id', 'dest_partner_ids')
    def _check_ext_input_no_ext_recip(self):
        if self.source_part_cat_id and self.dest_partner_ids:
            raise exceptions.ValidationError(_("Input from partner can't have other partners as recipients"))

    @api.constrains('user_process_ids')
    def _check_customer_voice_dont_u_turn(self):
        """
        The customer-supplier relationship is not reciprocal between the business processes, hence customer's voice
        goes through the company in one direction only
        """
        if self.is_customer_voice and self.business_process_id:
            if self.business_process_id.get_customers()['internal'] & self.user_process_ids:
                intersect = self.business_process_id.get_customers()['internal'] & self.user_process_ids
                processes = ', '.join([rec.name for rec in intersect])
                raise exceptions.ValidationError(
                    _('This document cannot have among its recipients the following process(es): %s') % processes
                )


class ProcessDataChannel(models.Model):
    _name = 'risk_management.business_process.channel'
    _description = 'Interprocess communication channel'
    _order = 'name'

    _sql_constraints = [
        ('name_uniq', 'unique (name)', "Channel name already exists !"),
    ]

    name = fields.Char(required=True, index=True, Translate=True)
    data_ids = fields.Many2many('risk_management.business_process.input_output',
                                relation='risk_management_data_channel_rel', column1='channel_id',
                                column2='data_id', string='Process Data')


class BusinessProcessTask(models.Model):
    _name = 'risk_management.business_process.task'
    _description = 'An activity in a process'
    _order = 'sequence, name'
    _sql_constraints = [
        (
            'task_name_unique',
            'UNIQUE(name, business_process_id)',
            'A task with the same name already exists in this process.'
        )
    ]

    name = fields.Char(required=True, translate=True, index=True)
    description = fields.Text(translate=True, index=True)
    owner_id = fields.Many2one('res.users', ondelete="set null", string='Assigned To')
    sequence = fields.Integer(default=10, index=True, string='Sequence')
    business_process_id = fields.Many2one(comodel_name='risk_management.business_process', ondelete='cascade',
                                          string="Process",
                                          index=True, required=True,
                                          default=lambda self: self.env.context.get('default_business_process_id'))
    company_id = fields.Many2one('res.company', related='business_process_id.company_id', string='Company')
    manager_id = fields.Many2one('res.users', related='business_process_id.responsible_id', readonly=True,
                                 related_sudo=False, string='Process Manager')
    frequency = fields.Selection(selection=[('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly'),
                                            ('quarterly', 'Quarterly'), ('annually', 'Annually')], string='Frequency',
                                 default='daily')

    def action_assign_to_me(self):
        self.write({'owner_id': self.env.user.id})


class BusinessProcessMethod(models.Model):
    _name = "risk_management.business_process.method"
    _description = "Rules and policies for the business process"
    _sql_constraints = [
        (
            'method_name_unique',
            'UNIQUE(name, business_process_id)',
            'A procedure with the same name already exist on this process'
        )
    ]

    name = fields.Char(translate=True, string='Title', required=True, copy=False, index=True)
    content = fields.Html(translate=True)  # todo: Add version control
    business_process_id = fields.Many2one(comodel_name='risk_management.business_process', string='User process',
                                          required=True)
    company_id = fields.Many2one('res.company', related='business_process_id.company_id', string='Company')
    output_ref_id = fields.Many2one(comodel_name='risk_management.business_process.input_output', string='Output ref.',
                                    domain=lambda self: [
                                        ('business_process_id.company_id', '=', self.business_process_id.company_id.id),
                                        ('business_process_id.process_type', '=', 'M')
                                    ],
                                    help='Output Reference', required=True)
    author_name = fields.Char('From process', related='output_ref_id.business_process_id.name', readonly=True)
    attachment_ids = fields.One2many('ir.attachment', string='Attached documents',
                                     related='output_ref_id.attachment_ids')
    doc_count = fields.Integer(compute='_compute_attached_docs_count', string="Number of documents attached")

    def _compute_attached_docs_count(self):
        for method in self:
            method.doc_count = len(method.attachment_ids)

    @api.multi
    def attachment_tree_view(self):
        self.ensure_one()
        return self.output_ref_id.attachment_tree_view()

