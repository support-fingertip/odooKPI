{
    "name": "Employee Dashboard",
    "version": "1.0",
    "summary": "Client action with employee selector and tabs (Details / Contracts / Timesheets)",
    "category": "Human Resources",
    "author": "Generated",
    "license": "LGPL-3",
    "depends": ["hr", "hr_timesheet"],
    "data": [
        'security/security.xml',
        'data/visit_sequence.xml',
        'security/ir.model.access.csv',
        'views/hr_employee.xml',
        'views/visit_views.xml',
        'views/pjp_model_views.xml',
        'views/sale_order.xml',
        "views/employee_client_action_views.xml",
        "views/executive_bid_report_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "employee_dashboard/static/lib/chart.min.js",
            "employee_dashboard/static/lib/fullcalendar/**",
            "employee_dashboard/static/lib/leaflet/leaflet.css",
            "employee_dashboard/static/lib/leaflet/leaflet.js",
            "employee_dashboard/static/src/css/style.css",
            "employee_dashboard/static/src/component/js/**",
            "employee_dashboard/static/src/component/xml/**",
        ]
    },
    "installable": True,
    "application": False,
}