/** @odoo-module **/
/**
 * EMPLOYEE 360 — MOBILE HOME / DASHBOARD  v2.0
 * KPI cards, beat progress, quick actions, active visit banner
 * Manager: live team overview + top performers
 */

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class MobileHome extends Component {
    static template = "employee_mobile.MobileHome";
    static props = {
        employeeId:   { type: [Number, { value: false }], optional: true },
        employeeName: { type: [String, { value: "" }],    optional: true },
        isManager:    { type: Boolean,                    optional: true },
        employees:    { type: Array,                      optional: true },
        onNavigate:   { type: Function,                   optional: true },
    };

    setup() {
        this.orm          = useService("orm");
        this.notification = useService("notification");
        this.navigateTo   = this.navigateTo.bind(this);

        this.state = useState({
            loading: true,
            kpi: {
                visits_today:    0,
                visits_month:    0,
                orders_month:    0,
                sales_month:     0,
                collections:     0,
                achievement:     0,
                beats_today:     0,
                beats_completed: 0,
            },
            attendance: {
                checkedIn: false, checkIn: null, checkOut: null, workedHours: null,
                checkinCity: null, lat: null, lng: null,
            },
            activeVisit:  null,
            currentBeat:  null,
            recentVisits: [],
            // Location
            locationInfo: { lat: null, lng: null, accuracy: null, loading: false, error: null, address: null },
            // Manager
            teamStats: { total: 0, active: 0, visits_today: 0, orders_today: 0, sales_today: 0 },
            topPerformers: [],
            teamLocations: [],
        });

        onWillStart(async () => { await this._load(); });
    }

    get empId()     { return this.props.employeeId; }
    get isManager() { return this.props.isManager; }

    async _load() {
        this.state.loading = true;
        try {
            if (this.isManager) await this._loadManagerData();
            else                await this._loadFieldUserData();
            // Request GPS non-blocking after main data is ready
            this._loadCurrentLocation();
        } catch (e) { console.error("[MobileHome]", e); }
        finally     { this.state.loading = false; }
    }

    _loadCurrentLocation() {
        if (!navigator.geolocation) {
            this.state.locationInfo.error = "GPS not supported";
            return;
        }
        this.state.locationInfo.loading = true;
        navigator.geolocation.getCurrentPosition(
            (pos) => {
                this.state.locationInfo.lat      = pos.coords.latitude.toFixed(6);
                this.state.locationInfo.lng      = pos.coords.longitude.toFixed(6);
                this.state.locationInfo.accuracy = Math.round(pos.coords.accuracy);
                this.state.locationInfo.loading  = false;
                this.state.locationInfo.error    = null;
            },
            (err) => {
                this.state.locationInfo.error   = "Location unavailable";
                this.state.locationInfo.loading = false;
            },
            { timeout: 10000, enableHighAccuracy: true, maximumAge: 60000 }
        );
    }

    async _loadFieldUserData() {
        if (!this.empId) return;
        const today    = new Date().toISOString().slice(0, 10);
        const now      = new Date();
        const firstDay = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,"0")}-01`;

        // Attendance
        try {
            const att = await this.orm.call("emp360.mobile", "get_today_attendance", [this.empId]);
            if (att && att.check_in) {
                this.state.attendance = {
                    checkedIn:   !att.check_out,
                    checkIn:     att.check_in,
                    checkOut:    att.check_out || null,
                    workedHours: att.worked_hours ? this._fmtHours(att.worked_hours) : null,
                    checkinCity: att.checkin_city || null,
                    lat:         att.checkin_latitude || null,
                    lng:         att.checkin_longitude || null,
                };
            }
        } catch (e) { console.warn("att:", e); }

        // Today + month visits
        try {
            const todayVisits = await this.orm.searchRead("visit.model",
                [["employee_id", "=", this.empId], ["actual_start_time", ">=", today + " 00:00:00"]],
                ["id", "status", "partner_id", "actual_start_time", "order_count", "total_order_amount"],
                { limit: 50 });
            const done = todayVisits.filter(v => v.status === "completed");
            this.state.kpi.visits_today = done.length;
            this.state.activeVisit      = todayVisits.find(v => v.status === "in_progress") || null;
            this.state.recentVisits     = todayVisits.slice(0, 5);
        } catch (e) { console.warn("visits:", e); }

        try {
            const mv = await this.orm.searchRead("visit.model",
                [["employee_id", "=", this.empId], ["actual_start_time", ">=", firstDay + " 00:00:00"]],
                ["id", "status"], { limit: 500 });
            this.state.kpi.visits_month = mv.filter(v => v.status === "completed").length;
        } catch (e) {}

        // Beats
        try {
            const beats = await this.orm.searchRead("beat.module",
                [["employee_id", "=", this.empId], ["beat_date", "=", today]],
                ["id", "name", "beat_number", "status", "customer_count"],
                { limit: 10 });
            this.state.kpi.beats_today     = beats.length;
            this.state.kpi.beats_completed = beats.filter(b => b.status === "completed").length;
            this.state.currentBeat         = beats.find(b => b.status === "in_progress") || beats[0] || null;
        } catch (e) {}

        // Month orders + sales
        try {
            const empRow = await this.orm.searchRead("hr.employee", [["id", "=", this.empId]], ["user_id"]);
            const userId = empRow[0]?.user_id?.[0];
            if (userId) {
                const orders = await this.orm.searchRead("sale.order",
                    [["user_id", "=", userId], ["date_order", ">=", firstDay + " 00:00:00"],
                     ["state", "in", ["sale", "done"]]],
                    ["amount_total"], { limit: 500 });
                this.state.kpi.orders_month = orders.length;
                this.state.kpi.sales_month  = orders.reduce((s, o) => s + (o.amount_total || 0), 0);
            }
        } catch (e) {}

        // KPI achievement
        try {
            const periods = await this.orm.searchRead("kpi.period",
                [["date_from", "<=", today], ["date_to", ">=", today]], ["id"], { limit: 1 });
            if (periods.length) {
                const targets = await this.orm.searchRead("kpi.target",
                    [["employee_id", "=", this.empId], ["period_id", "=", periods[0].id]],
                    ["overall_achievement"], { limit: 1 });
                if (targets.length) this.state.kpi.achievement = Math.round(targets[0].overall_achievement || 0);
            }
        } catch (e) {}

        // Collections
        try {
            const colls = await this.orm.searchRead("visit.collection",
                [["employee_id", "=", this.empId], ["date", ">=", firstDay], ["state", "=", "confirmed"]],
                ["amount"], { limit: 500 });
            this.state.kpi.collections = colls.reduce((s, c) => s + (c.amount || 0), 0);
        } catch (e) {}
    }

    async _loadManagerData() {
        const today = new Date().toISOString().slice(0, 10);
        try {
            const employees = await this.orm.call("emp360.mobile", "get_accessible_employees", []);
            const empIds = employees.map(e => e.id);
            this.state.teamStats.total = employees.length;
            if (!empIds.length) return;

            const [attRows, visitRows, orderRows] = await Promise.all([
                this.orm.searchRead("hr.attendance",
                    [["employee_id", "in", empIds], ["check_in", ">=", today + " 00:00:00"]],
                    ["employee_id", "check_out"], { limit: 500 }),
                this.orm.searchRead("visit.model",
                    [["employee_id", "in", empIds], ["actual_start_time", ">=", today + " 00:00:00"]],
                    ["employee_id", "status", "total_order_amount"], { limit: 500 }),
                this.orm.searchRead("sale.order",
                    [["create_date", ">=", today + " 00:00:00"], ["state", "in", ["sale", "done"]]],
                    ["amount_total"], { limit: 500 }),
            ]);

            this.state.teamStats.active        = new Set(attRows.filter(a => !a.check_out).map(a => a.employee_id[0])).size;
            const done                          = visitRows.filter(v => v.status === "completed");
            this.state.teamStats.visits_today   = done.length;
            this.state.teamStats.orders_today   = orderRows.length;
            this.state.teamStats.sales_today    = orderRows.reduce((s, o) => s + (o.amount_total || 0), 0);

            // Top performers
            const byEmp = {};
            for (const v of visitRows) {
                const eid = v.employee_id[0], name = v.employee_id[1];
                if (!byEmp[eid]) byEmp[eid] = { id: eid, name, visits: 0 };
                if (v.status === "completed") byEmp[eid].visits++;
            }
            this.state.topPerformers = Object.values(byEmp).sort((a, b) => b.visits - a.visits).slice(0, 5);

            // Team locations
            try {
                this.state.teamLocations = await this.orm.call("emp360.mobile", "get_team_locations", []);
            } catch (e) { console.warn("[MobileHome] team locations:", e); }

        } catch (e) { console.error("[MobileHome] manager:", e); }
    }

    // ── Formatters ────────────────────────────────────────────────
    _fmtHours(h) {
        const hrs = Math.floor(h);
        return `${hrs}h ${Math.round((h - hrs) * 60)}m`;
    }

    fmtMoney(v) {
        if (!v) return "₹0";
        if (v >= 10000000) return `₹${(v/10000000).toFixed(1)}Cr`;
        if (v >= 100000)   return `₹${(v/100000).toFixed(1)}L`;
        if (v >= 1000)     return `₹${(v/1000).toFixed(0)}K`;
        return `₹${Math.round(v).toLocaleString("en-IN")}`;
    }

    fmtTime(dt) {
        if (!dt) return "--:--";
        return new Date(dt).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
    }

    get todayDateStr() {
        return new Date().toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" });
    }

    get beatProgressPct() {
        const { beats_completed, beats_today } = this.state.kpi;
        return beats_today > 0 ? Math.round((beats_completed / beats_today) * 100) : 0;
    }

    get achievementColor() {
        const pct = this.state.kpi.achievement;
        if (pct >= 80) return "#06d6a0";
        if (pct >= 50) return "#f77f00";
        return "#ef233c";
    }

    get greeting() {
        const h = new Date().getHours();
        if (h < 12) return "Good Morning";
        if (h < 17) return "Good Afternoon";
        return "Good Evening";
    }

    get greetingIcon() {
        const h = new Date().getHours();
        return h < 12 ? "fa-sun-o" : h < 17 ? "fa-cloud" : "fa-moon-o";
    }

    get mapsUrl() {
        const { lat, lng } = this.state.locationInfo;
        if (!lat || !lng) return "#";
        return `https://maps.google.com/?q=${lat},${lng}`;
    }

    teamMemberMapsUrl(lat, lng) {
        if (!lat || !lng) return "#";
        return `https://maps.google.com/?q=${lat},${lng}`;
    }

    get teamLocationsWithGps() {
        return (this.state.teamLocations || []).filter(l => l.latitude && l.longitude);
    }

    get employeeFirstName() {
        return (this.props.employeeName || "").split(" ")[0] || "there";
    }

    navigateTo(screen) {
        if (this.props.onNavigate) this.props.onNavigate(screen);
    }

    getInitials(name) {
        return (name || "?").split(" ").slice(0, 2).map(w => w[0] || "").join("").toUpperCase();
    }

    getAvatarGradient(str) {
        const g = [
            "linear-gradient(135deg,#4361ee,#3a0ca3)", "linear-gradient(135deg,#06d6a0,#019b72)",
            "linear-gradient(135deg,#f72585,#b5179e)", "linear-gradient(135deg,#f77f00,#d62828)",
            "linear-gradient(135deg,#7209b7,#3a0ca3)", "linear-gradient(135deg,#4cc9f0,#0077b6)",
        ];
        let h = 0;
        for (let i = 0; i < (str || "").length; i++) h = str.charCodeAt(i) + ((h << 5) - h);
        return g[Math.abs(h) % g.length];
    }
}
