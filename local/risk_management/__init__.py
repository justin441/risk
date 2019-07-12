# -*- coding: utf-8 -*-

from . import controllers
from . import models

from odoo import api


def _create_process_zero(cr, registry):
    env = api.Environment(cr, api.SUPERUSER_ID, {})

    companies = env['res.company'].search([])
    projects = env['project.project'].search([])
    business_process = env['risk_management.business_process']
    project_process = env['risk_management.project_process']

    business_process_data = {
        'name': 'Business Process Zero',
        'description': """
        <p>This process represents the overall process of the company's business, to be used for activities, 
        methods or risks in the absence of more specific processes.</p>
        """,
        'business_id': None
    }
    project_process_data = {
        'name': 'Process Zero',
        'description': """
        <p>This process represents the overall process of the project, to be used for activities, 
        methods or risks in the absence of more specific processes.</p>
        """,
        'project_id': None
    }
    for company in companies:
        business_process.create(business_process_data.update({'business_id': company.id}))

    for project in projects:
        project_process.create(project_process_data.update({'project_id': project.id}))
