# -*- coding: utf-8 -*-
{
    'name': 'KPI Target & Actual Tracker',
    'version': '18.0.2.0.0',
    'category': 'Human Resources',
    'summary': 'Track employee KPI targets and actuals with OWL dashboard',
    'description': """
        Employee KPI Target & Actual Tracker
        =====================================
        * Track KPI targets by period (monthly/quarterly/yearly)
        * Record actual achievements
        * Calculate achievement percentages
        * Interactive OWL dashboard for data entry and visualization
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': ['base', 'hr', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/kpi_target_views.xml',
        'views/kpi_target_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'kpi_target/static/src/components/kpi_dashboard/**/*',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
