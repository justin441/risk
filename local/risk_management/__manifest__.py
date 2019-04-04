# -*- coding: utf-8 -*-
{
    'name': "Risk management",

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
    'depends': ['base', 'project'],

    # always loaded
    'data': [
        'security/groups.xml',
        'views/views.xml',
        'views/templates.xml',
        'security/ir.model.access.csv'
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'application': True,
    'installable': True,
    'auto_install': False,
    
}