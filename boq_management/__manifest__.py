# -*- coding: utf-8 -*-
{
    'name': 'BOQ Management — Bill of Quantities',
    'version': '18.0.1.0.0',
    'summary': 'Manage Bill of Quantities linked to Customers with dynamic category tabs',
    'description': """
        BOQ Management Module
        =====================
        - Create BOQ records linked to Customers
        - Dynamic notebook tabs per work category (Electrical, Civil, Lighting, Plumbing, …)
        - Tab visibility controlled by selected categories
        - Product order lines with quantity and type per category
    """,
    'author': 'Senior Odoo Developer',
    'category': 'Construction / Project',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'product', 'contacts'],
    'data': [
        'security/ir.model.access.csv',
        'data/boq_category_data.xml',
        'views/boq_category_views.xml',
        'views/boq_order_line_views.xml',
        'views/boq_boq_views.xml',
        'views/res_partner_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'boq_management/static/src/css/boq_styles.css',
            'boq_management/static/src/js/boq_form.js',
        ],
    },
    'images': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}
