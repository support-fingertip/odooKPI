# -*- coding: utf-8 -*-
{
    'name': 'BOQ Management — Bill of Quantities (Odoo 19)',
    'version': '19.0.1.2.0',
    'summary': 'BOQ, Vendor Rating (post-payment), Vendor Ratings Dashboard',
    'description': """
        BOQ Management
        ==============
        ✅ BOQ records linked directly to Customers
        ✅ Dynamic notebook tabs per work category (show/hide by selection)
        ✅ Electrical | Civil | Lighting | Plumbing | HVAC | Finishing tabs
        ✅ Product order lines with quantity, type and pricing per tab
        ✅ Per-category subtotals + grand total with currency support
        ✅ Customer smart button with BOQ count
        ✅ Kanban / List / Dashboard views
        ✅ Full chatter (log, activity, followers)
        ✅ Enterprise UI: gradient cards, animated tabs, responsive grid

        Vendor Rating (Task 1 & 2 & 3)
        ================================
        ✅ Task 1 — Rating collected ONLY after PO payment is released (all invoices paid)
        ✅ Task 1 — Rating editable by BOQ Manager group only (not developer/admin)
        ✅ Task 2 — Overall vendor avg rating = average of all rated POs (auto-recalculate)
        ✅ Task 2 — Each PO gets its own individual 1–5 star rating
        ✅ Task 3 — Rating visible on Vendor profile (smart button + panel)
        ✅ Task 3 — Rating visible on individual Purchase Order record
        ✅ Task 3 — Rating visible on BOQ Dashboard vendor cards + Ratings tab

        Vendor Ratings Section (replaces Tradeways)
        ============================================
        ✅ "Vendor Ratings > Vendors" — lists all suppliers with avg rating & stars
        ✅ "Vendor Ratings > PO Ratings" — lists all rated POs (manager only)
        ✅ Uses standard res.partner (vendors) + purchase.order — no custom models
    """,
    'author': 'Senior Odoo Developer',
    'category': 'Industries/Construction',
    'license': 'OPL-1',
    'depends': [
        'base',
        'mail',
        'product',
        'contacts',
        'web',
        'uom',
        'purchase',
        'account',
        'project',
    ],
    'data': [
        'security/boq_groups.xml',
        'security/ir.model.access.csv',
        'data/boq_sequence_data.xml',
        'data/boq_category_data.xml',
        'views/boq_dashboard_views.xml',
        'views/boq_boq_views.xml',
        'views/boq_category_views.xml',
        'views/boq_order_line_views.xml',
        'views/res_partner_views.xml',
        'views/purchase_order_views.xml',
        'views/tradeways_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # BOQ Dashboard
            'boq_management_v19/static/src/css/boq_enterprise.css',
            'boq_management_v19/static/src/css/boq_dashboard.css',
            'boq_management_v19/static/src/js/boq_dashboard.js',
            'boq_management_v19/static/src/xml/boq_dashboard.xml',
            # Tradeways Dashboard (kept for backward compat; no menu items point here)
            'boq_management_v19/static/src/css/tradeways_dashboard.css',
            'boq_management_v19/static/src/js/tradeways_dashboard.js',
            'boq_management_v19/static/src/xml/tradeways_dashboard.xml',
        ],
    },
    'images': ['static/src/img/boq_icon.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
}
