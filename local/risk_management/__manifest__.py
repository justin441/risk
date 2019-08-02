# -*- coding: utf-8 -*-
{
    'name': "Risk Management",

    'summary': """
    Risk management, Activity, Process
    """,

    'description': """ """,

    'author': "Noubru Holding",
    'website': "http://noubruholding.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/11.0/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Risk management',
    'version': '11.0.0.1',
    # any module necessary for this one to work correctly
    'depends': ['base', 'project', 'mail'],

    # always loaded
    'data': [
        'data/process_partner_categories_data.xml',
        'data/risk_categories_data.xml',
        'data/risk_data.xml',
        'data/process_data.xml',
        'security/risk_security.xml',
        'wizard/risks_wizard_views.xml',
        'views/risk_views.xml',
        'views/risk_templates.xml',
        'security/ir.model.access.csv',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'application': True,
    'installable': True,
    'auto_install': False,
}