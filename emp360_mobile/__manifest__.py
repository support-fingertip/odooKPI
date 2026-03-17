{
    "name": "Employee 360 Mobile",
    "version": "18.0.1.0.3",
    "summary": "PWA-ready Mobile App for Field Users & Managers — Android / iOS web app",
    "description": """
Employee 360 Mobile Application
================================
A full-featured, native-app-like mobile web application for Odoo 18.

Built with OWL 3 and designed with Material Design 3 + iOS HIG inspiration.
Works as a Progressive Web App (PWA) — add to Home Screen on Android or iOS.

Features
--------
**Field User:**
- Home dashboard with real-time KPIs (visits, beats, orders, sales, collections, achievement %)
- Full workday workflow: check-in → beat → visits → check-out
- Visit workflow: store photo → quick order → stock update → payment collection → checklist → ticket
- Beat switch with reason recording and GPS geofencing
- Visit history, sales orders, attendance log, KPI targets, support tickets

**Manager:**
- Live team dashboard (who is active, beats, visits, sales)
- Per-employee drilldown with month stats and today's visit timeline
- All-team visits, orders, and analytics

UI Highlights
-------------
- Bottom navigation bar (native app feel)
- Bottom sheet modals with smooth slide-up animation
- Gradient hero headers, KPI cards, progress rings
- Touch-optimized (48 px tap targets, no hover states)
- Skeleton loaders, pulse animations, safe-area support
    """,
    "category": "Human Resources",
    "author": "Employee 360",
    "license": "LGPL-3",
    "depends": [
        "employee_dashboard",   # provides all data models
        "kpi_target",           # KPI target/period models
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/mobile_action.xml",
    ],
    "assets": {
        "web.assets_backend": [
            # ── Mobile Design System ───────────────────────────────
            "emp360_mobile/static/src/css/mobile_app.css",

            # ── OWL Components (load order matters) ───────────────
            "emp360_mobile/static/src/js/mobile_home.js",
            "emp360_mobile/static/src/js/mobile_today.js",
            "emp360_mobile/static/src/js/mobile_visits.js",
            "emp360_mobile/static/src/js/mobile_orders.js",
            "emp360_mobile/static/src/js/mobile_manager.js",
            "emp360_mobile/static/src/js/mobile_profile.js",
            "emp360_mobile/static/src/js/mobile_app.js",   # main — imports the above

            # ── OWL Templates ─────────────────────────────────────
            "emp360_mobile/static/src/xml/mobile_home.xml",
            "emp360_mobile/static/src/xml/mobile_today.xml",
            "emp360_mobile/static/src/xml/mobile_visits.xml",
            "emp360_mobile/static/src/xml/mobile_orders.xml",
            "emp360_mobile/static/src/xml/mobile_manager.xml",
            "emp360_mobile/static/src/xml/mobile_profile.xml",
            "emp360_mobile/static/src/xml/mobile_app.xml",
        ]
    },
    "installable": True,
    "application": True,
    "auto_install": False,
}
