# -*- coding: utf-8 -*-
from odoo import http

# class StockInventory(http.Controller):
#     @http.route('/stock_inventory/stock_inventory/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/stock_inventory/stock_inventory/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('stock_inventory.listing', {
#             'root': '/stock_inventory/stock_inventory',
#             'objects': http.request.env['stock_inventory.stock_inventory'].search([]),
#         })

#     @http.route('/stock_inventory/stock_inventory/objects/<model("stock_inventory.stock_inventory"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('stock_inventory.object', {
#             'object': obj
#         })