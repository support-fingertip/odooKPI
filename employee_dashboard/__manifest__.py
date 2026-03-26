{
    "name": "Employee Dashboard",
    "version": "1.0",
    "summary": "Client action with employee selector and tabs (Details/Contracts/Timesheets)",
    "category": "Human Resources",
    "author": "Generated",
    "license": "LGPL-3",
    "depends": ["hr", "hr_timesheet", "beat_module", "sale_management", "account"],
    "data": [
    'security/security.xml',
    'data/visit_sequence.xml',
    'security/ir.model.access.csv',

    'views/hr_employee.xml',
    'views/hr_attendance.xml',
    'views/visit_views.xml',
    'views/pjp_model_views.xml',

    # ACTIONS FIRST
    "views/employee_client_action_views.xml",
    "views/executive_beat_report_views.xml",
    "views/dashboard_reports.xml",
    "views/dashboard_report_view.xml",

    # MENUS LAST
    "views/main_menu.xml",

    'views/sale_order.xml',
    'views/visit_stock_views.xml',
    'views/visit_collection_views.xml',
    'views/visit_ticket_views.xml',
    'views/visit_competitor_views.xml',
    'views/visit_checklist_views.xml',
    'views/visit_geofence_views.xml',
    'views/asset_management_views.xml',
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
