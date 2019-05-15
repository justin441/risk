# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api, exceptions

_logger = logging.getLogger(__name__)


class BaseProcess(models.AbstractModel):
    _name = 'risk_management.base_process'

    name = fields.Char(required=True, index=True, translate=True)
    process_type = fields.Selection(selection=[('O', 'Operation'), ('M', 'Management'), ('S', 'Support')], default='O',
                                    required=True, string='Process type')
    description = fields.Html(translate=True, string="Description")
    responsible_id = fields.Many2one('res.users', ondelete='set null', string='Responsible',
                                     default=lambda self: self.env.user, index=True)
    method_count = fields.Integer(compute='_compute_method_count', string="Methods")

    @api.constrains('input_data_ids', 'id')
    def _check_output_not_in_input(self):
        for process in self:
            for data in process.output_data_ids:
                if data in process.input_data_ids:
                    raise exceptions.ValidationError("A process cannot consume its own output")

    @api.multi
    def get_input_int_providers(self):
        self.ensure_one()
        int_data = self.input_data_ids.filter('int_provider_id')  # filter out data of external origin
        return int_data.mapped('int_provider_id')

    @api.multi
    def get_input_ext_provider_cats(self):
        self.ensure_one()
        ext_data = self.input_data_ids.filter('ext_provider_cat_id')  # filter out data of internal origin
        return ext_data.mapped('ext_provider_cat_id')

    @api.multi
    def get_output_users(self):
        self.ensure_one()
        c = self.env[self._name]
        for data in self.output_data_ids:
            c |= data.consumer_ids
        return c


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
    name = fields.Char(required=True, index=True, translate=True)
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

    name = fields.Char(translate=True, string='Title', required=True)
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
                                  default=lambda self: self.env['res.company']._company_default_get(
                                      'risk_management.business_process'),
                                  readonly=True)
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

    @api.depends('task_ids')
    def _compute_task_count(self):
        for rec in self:
            rec.task_count = len(rec.task_ids)

    @api.depends('method_ids')
    def _compute_method_count(self):
        for rec in self:
            rec.method_count = len(rec.method_ids)


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
                                           "('business_id','=', int_provider_id.business_id)]",
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

    name = fields.Char(required=True, translate=True)
    description = fields.Text(translate=True)
    owner_id = fields.Many2one('res.users', ondelete="set null")
    sequence = fields.Integer(default=10)
    process_id = fields.Many2one('risk_management.business_process', ondelete='cascade', string="Process", index=True)


class BusinessProcessMethod(models.Model):
    _name = "risk_management.business_process.method"
    _description = "Rules and policies for the business process"
    _inherit = ['risk_management.base_process_method']
    output_ref_id = fields.Many2one(comodel_name='risk_management.business_process_data', string='Output ref.',
                                    domain=[('int_provider_id.process_type', '=', 'M')],
                                    help='Output data reference')
    process_id = fields.Many2one(comodel_name='risk_management.business_process', string='User process')
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

    @api.depends('task_ids')
    def _compute_task_count(self):
        for rec in self:
            rec.task_count = len(rec.task_ids)

    @api.depends('method_ids')
    def _compute_method_count(self):
        for rec in self:
            rec.method_count = len(rec.method_ids)

    project_id = fields.Many2one('project.project', string='Project', ondelete='cascade',
                                 default=lambda self: self.env.context.get('default_project_id'),
                                 index=True)
    task_ids = fields.One2many('project.task', string='Tasks', inverse_name='process_id',
                               domain="[('project_id', '=', project_id), '|', "
                                      "('stage_id.fold', '=', False), "
                                      "('stage_id', '=', False)]")
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


class ProjectMethod(models.Model):
    _name = "risk_management.project_process.method"
    _description = "Rules and policies for the project process"
    _inherit = ['risk_management.base_process_method']
    output_ref_id = fields.Many2one(comodel_name='risk_management.project_process_data', string='Output ref.',
                                    domain=[('int_provider_id.process_type', '=', 'M')], help='Output data reference')
    process_id = fields.Many2one(comodel_name='risk_management.project_process', string='User process')
    author_name = fields.Char('From process', related='output_ref_id.int_provider_id.name', readonly=True)
