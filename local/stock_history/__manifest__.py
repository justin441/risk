# -*- coding: utf-8 -*-
{
    'name': "stock_inventory",

    'summary': """
        Stock, Inventory, PDF, Excel""",

    'description': """
        This module makes it possible to export to Excel as well as to print PDF of the inventory status of a location on a given date in ODOO 11. 
        The generated reports include the quantities according to the type of "unit of measure" (sale or purchase) as well as the valuation of stocks.
    """,

    'author': "NH-ITC",
    'website': "https://its-nh.com/",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/11.0/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Inventory',
    'version': '11.0.1',

    # any module necessary for this one to work correctly
    'depends': ['stock'],

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
}