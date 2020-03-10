# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProductStockHistory(models.Model):
    _name = 'product.stock.history'
    _auto = False

    product_id = fields.Many2one('product.product', 'Product', readonly=True)
    product_code = fields.Char(string='Reference', related='product_id.code')
    product_uom_po_id = fields.Many2one('product.uom', 'Purchase Unit of Measure', related='product_id.uom_po_id')
    product_uom_id = fields.Many2one('product.uom', 'Default Unit of Measure', related='product_id.uom_id')
    product_categ_id = fields.Many2one('product.category', 'Product category', related='product_id.categ_id')
    location_id = fields.Many2one('stock.location', 'Location', readonly=True)
    warehouse_id = fields.Many2one('stock.warehouse', compute='_compute_warehouse', string='Warehouse')
    location_usage = fields.Selection([
        ('supplier', 'Vendor Location'),
        ('view', 'View'),
        ('internal', 'Internal Location'),
        ('customer', 'Customer Location'),
        ('inventory', 'Inventory Loss'),
        ('procurement', 'Procurement'),
        ('production', 'Production'),
        ('transit', 'Transit Location')], string='Location Type', related='location_id.usage')
    lot_id = fields.Many2one('stock.production.lot', 'Lot', readonly=True)

    @api.depends('location_id')
    def _compute_warehouse(self):
        for rec in self:
            rec.warehouse_id = rec.location_id.get_warehouse()


