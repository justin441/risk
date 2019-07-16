# -*- coding: utf-8 -*-
from odoo import http

# class ProjectRisk(http.Controller):
#     @http.route('/project_risk/project_risk/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/project_risk/project_risk/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('project_risk.listing', {
#             'root': '/project_risk/project_risk',
#             'objects': http.request.env['project_risk.project_risk'].search([]),
#         })

#     @http.route('/project_risk/project_risk/objects/<model("project_risk.project_risk"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('project_risk.object', {
#             'object': obj
#         })