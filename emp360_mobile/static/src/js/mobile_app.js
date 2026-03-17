/** @odoo-module **/
/**
 * EMPLOYEE 360 — MOBILE APPLICATION  v2.0
 * Odoo 18 | PWA-ready Mobile App for Field Users & Managers
 *
 * FIXES v2.0:
 *  - Badge load uses emp360.mobile (not hr.attendance directly)
 *  - GPS permission requested eagerly so user sees the browser prompt
 *  - Manager starts on "home" (dashboard), field user on "home"
 *  - nav items + screen titles updated
 */

import { registry }         from "@web/core/registry";
import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { useService }       from "@web/core/utils/hooks";
import { MobileHome }           from "./mobile_home";
import { MobileToday }          from "./mobile_today";
import { MobileVisits }         from "./mobile_visits";
import { MobileOrders }         from "./mobile_orders";
import { MobileManager }        from "./mobile_manager";
import { MobileProfile }        from "./mobile_profile";
import { ScreenErrorBoundary }  from "./error_boundary";

// ── Navigation items ─────────────────────────────────────────────
const USER_NAV = [
    { id: "home",    label: "Home",    icon: "fa-home",          gradient: "linear-gradient(135deg,#4361ee,#3a0ca3)" },
    { id: "today",   label: "Workday", icon: "fa-briefcase",     gradient: "linear-gradient(135deg,#06d6a0,#019b72)" },
    { id: "visits",  label: "Visits",  icon: "fa-map-marker",    gradient: "linear-gradient(135deg,#4cc9f0,#0077b6)" },
    { id: "orders",  label: "Orders",  icon: "fa-shopping-cart", gradient: "linear-gradient(135deg,#f72585,#b5179e)" },
    { id: "profile", label: "More",    icon: "fa-ellipsis-h",    gradient: "linear-gradient(135deg,#7209b7,#3a0ca3)" },
];

const MANAGER_NAV = [
    { id: "home",    label: "Dashboard", icon: "fa-tachometer",   gradient: "linear-gradient(135deg,#4361ee,#3a0ca3)" },
    { id: "team",    label: "Team",      icon: "fa-users",         gradient: "linear-gradient(135deg,#06d6a0,#019b72)" },
    { id: "visits",  label: "Visits",    icon: "fa-map-marker",    gradient: "linear-gradient(135deg,#4cc9f0,#0077b6)" },
    { id: "orders",  label: "Orders",    icon: "fa-shopping-cart", gradient: "linear-gradient(135deg,#f72585,#b5179e)" },
    { id: "profile", label: "More",      icon: "fa-ellipsis-h",    gradient: "linear-gradient(135deg,#7209b7,#3a0ca3)" },
];

const SCREEN_TITLES = {
    home:    "Employee 360",
    today:   "My Workday",
    visits:  "Visit History",
    orders:  "Sales Orders",
    team:    "My Team",
    profile: "More",
};

const SCREEN_GRADIENTS = {
    home:    "linear-gradient(135deg,#0b0c1e 0%,#161732 60%,#0f3460 100%)",
    today:   "linear-gradient(135deg,#06d6a0,#019b72)",
    visits:  "linear-gradient(135deg,#4cc9f0,#0077b6)",
    orders:  "linear-gradient(135deg,#f72585,#b5179e)",
    team:    "linear-gradient(135deg,#4361ee,#3a0ca3)",
    profile: "linear-gradient(135deg,#7209b7,#3a0ca3)",
};

// ── Main Mobile App Component ─────────────────────────────────────
export class MobileApp extends Component {
    static template = "employee_mobile.MobileApp";
    static components = { MobileHome, MobileToday, MobileVisits, MobileOrders, MobileManager, MobileProfile, ScreenErrorBoundary };

    setup() {
        this.orm          = useService("orm");
        this.notification = useService("notification");
        this.action       = useService("action");

        this.state = useState({
            isManager:        false,
            employeeId:       null,
            userId:           null,
            employeeName:     "",
            employeeDept:     "",
            employeeJob:      "",
            activeScreen:     "home",
            navHistory:       [],
            loading:          true,
            initError:        false,
            pendingVisits:    0,
            todayCheckedIn:   false,
            employees:        [],
            selectedEmpId:    null,
        });

        onWillStart(async () => { await this._init(); });
        onMounted(() => { this._setupViewport(); });
    }

    async _init() {
        try {
            // 1. Get access info
            const info = await this.orm.call("emp360.mobile", "get_user_access_info", []);
            this.state.isManager  = info.is_manager;
            this.state.employeeId = info.employee_id;
            this.state.userId     = info.user_id;

            // 2. Employee details
            if (this.state.employeeId) {
                const rows = await this.orm.searchRead("hr.employee",
                    [["id", "=", this.state.employeeId]],
                    ["name", "department_id", "job_id"]);
                if (rows.length) {
                    this.state.employeeName = rows[0].name || "";
                    this.state.employeeDept = rows[0].department_id?.[1] || "";
                    this.state.employeeJob  = rows[0].job_id?.[1] || "";
                }
            }

            // 3. Manager: load team list
            if (this.state.isManager) {
                this.state.employees = await this.orm.call("emp360.mobile", "get_accessible_employees", []);
                this.state.selectedEmpId = this.state.employeeId;
            }

            // 4. Badge counts (uses emp360.mobile helper — fixes the original bug)
            await this._loadBadges();
            this.state.loading = false;

        } catch (e) {
            console.error("[MobileApp] init error:", e);
            this.state.initError = true;
            this.state.loading   = false;
        }
    }

    async _loadBadges() {
        if (!this.state.employeeId) return;
        try {
            const today = new Date().toISOString().slice(0, 10);

            // Pending visits today
            const pending = await this.orm.searchRead("visit.model",
                [
                    ["employee_id", "=", this.state.employeeId],
                    ["status", "in", ["planned", "in_progress"]],
                    ["planned_start_time", ">=", today + " 00:00:00"],
                    ["planned_start_time", "<=", today + " 23:59:59"],
                ],
                ["id"], { limit: 20 });
            this.state.pendingVisits = pending.length;

            // Today attendance — FIX: use emp360.mobile, not hr.attendance directly
            const att = await this.orm.call("emp360.mobile", "get_today_attendance", [this.state.employeeId]);
            this.state.todayCheckedIn = !!(att && att.check_in && !att.check_out);

        } catch (e) {
            console.warn("[MobileApp] badge error:", e);
        }
    }

    _setupViewport() {
        // Mobile viewport meta
        let meta = document.querySelector('meta[name="viewport"]');
        if (!meta) {
            meta = document.createElement("meta");
            meta.name = "viewport";
            document.head.appendChild(meta);
        }
        meta.content = "width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover";

        // Theme color
        let theme = document.querySelector('meta[name="theme-color"]');
        if (!theme) {
            theme = document.createElement("meta");
            theme.name = "theme-color";
            document.head.appendChild(theme);
        }
        theme.content = "#0b0c1e";
    }

    // ── Navigation ────────────────────────────────────────────────
    navigate(screenId) {
        if (screenId === this.state.activeScreen) return;
        if (!this.state.isManager && screenId === "team") return;
        this.state.navHistory.push(this.state.activeScreen);
        this.state.activeScreen = screenId;
        window.scrollTo(0, 0);
        this._loadBadges();
    }

    goBack() {
        if (this.state.navHistory.length > 0) {
            this.state.activeScreen = this.state.navHistory.pop();
        }
    }

    onNavigate(screenId) { this.navigate(screenId); }

    async onRefresh() {
        await this._loadBadges();
        this.notification.add("Refreshed", { type: "info" });
    }

    // ── Computed ──────────────────────────────────────────────────
    get navItems() { return this.state.isManager ? MANAGER_NAV : USER_NAV; }

    currentTitle() { return SCREEN_TITLES[this.state.activeScreen] || "Employee 360"; }

    topbarGradient() { return SCREEN_GRADIENTS[this.state.activeScreen] || SCREEN_GRADIENTS.home; }

    get canGoBack() { return this.state.navHistory.length > 0; }

    get todayDate() {
        return new Date().toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });
    }

    get employeeInitials() {
        return this.state.employeeName.split(" ").slice(0, 2).map(w => w[0] || "").join("").toUpperCase() || "U";
    }

    getBadge(navId) {
        if (navId === "visits" && this.state.pendingVisits > 0) return this.state.pendingVisits;
        if (navId === "today" && this.state.todayCheckedIn) return null;
        return null;
    }
}

registry.category("actions").add("employee_mobile_app", MobileApp);
