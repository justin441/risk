# -*- coding: utf-8 -*-
{
    'name': "project_risk",

    'summary': """
       Project Risk Management""",

    'description': """
        This module adds risk management to project
    """,

    'author': "Noubru Holding",
    'website': "http://noubruholding.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/11.0/odoo/addons/base/module/module_data.xml
    # for the full list
     'category': 'Risk management',
    'version': '11.0.0.1',

    # any module necessary for this one to work correctly
    'depends': ['risk_management'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/views.xml',
        'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'auto_install': True,
}