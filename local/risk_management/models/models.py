# -*- coding: utf-8 -*-

from odoo import models, fields, api, exceptions


class BaseProcess(models.AbstractModel):
    _name = 'risk_management.base_process'

    name = fields.Char(required=True, index=True, translate=True)
    process_type = fields.Selection(selection=[('O', 'Operation'), ('M', 'Management'), ('S', 'Support')], default='O',
                                    required=True)
    description = fields.Html(required=True, translate=True, string="Description")
    responsible_id = fields.Many2one('res.users', ondelete='set null', string='Responsible',
                                     default=lambda self: self.env.user, index=True)

    @api.constrains('input_data_ids', 'id')
    def _check_output_not_in_input(self):
        for process in self:
            for data in process.output_data_ids:
                if data in process.input_data_ids:
                    raise exceptions.ValidationError("A process cannot consume its own output")

    @api.multi
    def get_input_int_providers(self):
        self.ensure_one()
        return self.input_data_ids.mapped('int_provider_id')

    @api.multi
    def get_input_ext_provider_cats(self):
        self.ensure_one()
        return self.input_data_ids.mapped('ext_provider_cat_id')

    @api.multi
    def get_output_clients(self):
        self.ensure_one()
        c = self.env[self._name]
        for data in self.output_data_ids:
            c |= data.consumer_ids
        return c


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
                                  default=lambda self: self.env['res.company']._company_default_get('risk_management'),
                                  readonly=True)
    task_ids = fields.One2many('risk_management.business_process.task', inverse_name='process_id', string='Tasks')
    output_data_ids = fields.One2many('risk_management.business_process_data', inverse_name='int_provider_id',
                                      string='Output data')
    input_data_ids = fields.Many2many(comodel_name='risk_management.business_process_data',
                                      relation='risk_management_input_ids_consumers_ids_rel',
                                      column1='input_data_ids', column2='consumer_ids', string="Input data",
                                      domain="[('id', 'not in', output_data_ids)]")


class BaseProcessdata(models.AbstractModel):
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
    ext_provider_cat_id = fields.Many2one('res.partner.category', string='Origin (external)', ondelete='cascade',
                                          domain=[('parent_id.name', '=', 'Process partner')],
                                          help='If new, must be a child of `Process partner` category')

    @api.constrains('consumer_ids', 'int_provider_id')
    def _check_provider_not_in_consumers(self):
        """Data provider should not be a consumer of said data"""
        for data in self:
            if data.int_provider_id and data.int_provider_id in data.consumer_ids:
                raise exceptions.ValidationError("A data's provider cannot be a consumer of that data")


class BusinessProcessData(models.Model):
    _name = 'risk_management.business_process_data'
    _description = 'Business Process input or output'
    _inherit = ['risk_management.base_process_data']

    int_provider_id = fields.Many2one('risk_management.business_process', string='Origin (internal)',
                                      ondelete='cascade')
    consumer_ids = fields.Many2many(comodel_name='risk_management.business_process',
                                    relation='risk_management_input_ids_consumers_ids_rel',
                                    column1='consumer_ids', column2='input_data_ids',
                                    domain="[('id', '!=', int_provider_id)]", string="Consumers")


class BusinessProcessTask(models.Model):
    _name = 'risk_management.business_process.task'
    _description = 'An activity in a process'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    description = fields.Text(translate=True)
    owner = fields.Many2one('res.users', ondelete="set null")
    sequence = fields.Integer(default=10)
    process_id = fields.Many2one('risk_management.business_process', ondelete='cascade', string="Process", index=True)

