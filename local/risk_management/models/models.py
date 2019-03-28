# -*- coding: utf-8 -*-

from odoo import models, fields, api, exceptions


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
    responsible_id = fields.Many2one('res.users', ondelete='set null',  string='Responsible')
    output_data_ids = fields.One2many('risk_management.process_data', inverse_name='int_provider_id',
                                      string='Output data')
    input_data_ids = fields.Many2many(comodel_name='risk_management.process_data',
                                      relation='risk_management_input_ids_consumers_ids_rel',
                                      column1='input_data_ids', column2='consumer_ids', string="Input data",
                                      domain="[('int_provider_id', '!=', 'id')]")


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
                                      )
    consumer_ids = fields.Many2many(comodel_name='risk_management.process',
                                    relation='risk_management_input_ids_consumers_ids_rel',
                                    column1='consumer_ids', column2='input_data_ids',
                                    domain="[('id', '!=', 'int_provider_id')]")

    @api.constrains('ext_provider_id', 'int_provider_id')
    def _only_one_provider(self):
        """Process data is provided by either an external partner or an internal process"""
        for data in self:
            if data.ext_provider_id and data.int_provider_id:
                raise exceptions.ValidationError("A process data cannot have 2 provider")
            elif not data.int_provider_id and not data.ext_provider_id:
                raise exceptions.ValidationError("A process has to have one provider")
