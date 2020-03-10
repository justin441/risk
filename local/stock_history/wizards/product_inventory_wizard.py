from odoo import models, fields


class ProductStockWizard(models.TransientModel):
    _name = 'product.stock.wizard'

    stock_date = fields.Datetime(default=fields.Datetime.now, string='Inventory Date', required=True)
    warehouse_ids = fields.One2many('stock.warehouse', string='Warehouses')

