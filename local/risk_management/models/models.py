# -*- coding: utf-8 -*-

from odoo import models, fields, api


class Process(models.Model):
    _name = 'risk_management.process'
    _description = 'A business process'
    _sql_constraints = [
        ('process_name_unique',
         'UNIQUE(name)',
         'The process name must be unique.')
    ]
    name = fields.Char(required=True, index=True, translate=True, size=255)
    process_type = fields.Selection(selection=[('O', 'Operation'), ('M', 'Management'), ('S', 'Support')], default='O',
                                    required=True)
    description = fields.Text(required=True, translate=True)
    responsible_id = fields.Many2one('res.user', ondelete='set null', delegate=True, string='Responsible')
    output_data_ids = fields.One2many('risk_management.process_data', inverse_name='int_provider_id',
                                      string='Output data')
    input_data_ids = fields.Many2many(comodel_name='risk_management.process_data',
                                      relation='risk_management_input_ids_consumers_ids_rel',
                                      column1='input_data_ids', column2='consumer_ids', string="Input data",
                                      domain="[('int_provider_id.name', '!=', 'name')]")


class ProcessData(models.Model):
    _name = 'risk_management.process_data'
    _description = 'Process input or output'
    _sql_constraints = [
        (
            'data_name_unique',
            'UNIQUE(name)',
            'The process data name must be unique'
        )
    ]

    name = fields.Char(required=True, index=True, translate=True, size=255)
    ext_provider_id = fields.Many2one('res.partner', string='External provider', ondelete='cascade')
    int_provider_id = fields.Many2one('risk_management.process', string='Internal provider', ondelete='cascade',
                                      delegate=True)
    consumer_ids = fields.Many2many(comodel_name='risk_management.process',
                                    relation='risk_management_input_ids_consumers_ids_rel',
                                    column1='consumer_ids', column2='input_data_ids',
                                    domain="[('name', '!=', 'int_provider_id.name')]")
