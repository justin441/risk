# -*- coding: utf-8 -*-
from odoo import http

# class RiskManagement(http.Controller):
#     @http.route('/risk_management/risk_management/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/risk_management/risk_management/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('risk_management.listing', {
#             'root': '/risk_management/risk_management',
#             'objects': http.request.env['risk_management.risk_management'].search([]),
#         })

#     @http.route('/risk_management/risk_management/objects/<model("risk_management.risk_management"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('risk_management.object', {
#             'object': obj
#         })