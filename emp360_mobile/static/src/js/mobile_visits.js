/** @odoo-module **/
/**
 * EMPLOYEE 360 — MOBILE VISITS SCREEN
 * Visit history list with filters and detail view
 */

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class MobileVisits extends Component {
    static template = "employee_mobile.MobileVisits";

    setup() {
        this.orm          = useService("orm");
        this.notification = useService("notification");

        this.state = useState({
            loading:       true,
            visits:        [],
            filtered:      [],
            filter:        "all",       // all | today | week | month
            statusFilter:  "all",
            search:        "",
            selectedVisit: null,
            showDetail:    false,
            visitDetail:   null,
            detailLoading: false,
            page:          1,
            hasMore:       false,
        });

        onWillStart(async () => {
            await this._load();
        });
    }

    get empId()     { return this.props.employeeId; }
    get isManager() { return this.props.isManager; }

    async _load() {
        this.state.loading = true;
        try {
            const domain = this._buildDomain();
            const visits = await this.orm.searchRead(
                "visit.model", domain,
                ["id", "visit_id", "partner_id", "beat_id", "employee_id",
                 "actual_start_time", "actual_end_time", "duration_display",
                 "status", "order_count", "total_order_amount", "is_productive",
                 "total_collected", "visit_for"],
                { order: "actual_start_time desc", limit: 50 }
            );
            this.state.visits   = visits;
            this.state.hasMore  = visits.length === 50;
            this._applyFilters();
        } catch (e) {
            console.error("[MobileVisits] load:", e);
        } finally {
            this.state.loading = false;
        }
    }

    _buildDomain() {
        const domain = [];
        if (this.empId && !this.isManager) {
            domain.push(["employee_id", "=", this.empId]);
        }
        const now  = new Date();
        const tStr = now.toISOString().slice(0, 10);

        switch (this.state.filter) {
            case "today":
                domain.push(["actual_start_time", ">=", tStr + " 00:00:00"]);
                domain.push(["actual_start_time", "<=", tStr + " 23:59:59"]);
                break;
            case "week": {
                const dow   = now.getDay();
                const start = new Date(now); start.setDate(now.getDate() - dow);
                domain.push(["actual_start_time", ">=", start.toISOString().slice(0, 10) + " 00:00:00"]);
                break;
            }
            case "month": {
                const firstDay = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-01`;
                domain.push(["actual_start_time", ">=", firstDay + " 00:00:00"]);
                break;
            }
        }

        if (this.state.statusFilter !== "all") {
            domain.push(["status", "=", this.state.statusFilter]);
        }
        return domain;
    }

    _applyFilters() {
        let list = [...this.state.visits];
        if (this.state.search) {
            const q = this.state.search.toLowerCase();
            list = list.filter(v =>
                (v.partner_id?.[1] || "").toLowerCase().includes(q) ||
                (v.visit_id || "").toLowerCase().includes(q) ||
                (v.beat_id?.[1] || "").toLowerCase().includes(q)
            );
        }
        this.state.filtered = list;
    }

    async setFilter(f) {
        this.state.filter = f;
        await this._load();
    }

    async setStatusFilter(s) {
        this.state.statusFilter = s;
        await this._load();
    }

    onSearchInput(ev) {
        this.state.search = ev.target.value;
        this._applyFilters();
    }

    async openDetail(visit) {
        this.state.selectedVisit = visit;
        this.state.showDetail    = true;
        this.state.detailLoading = true;

        try {
            const rows = await this.orm.searchRead(
                "visit.model",
                [["id", "=", visit.id]],
                ["id", "visit_id", "partner_id", "beat_id", "employee_id",
                 "actual_start_time", "actual_end_time", "duration_display",
                 "status", "order_count", "total_order_amount", "is_productive",
                 "productivity_reason", "total_collected", "visit_for",
                 "visit_comments", "checkin_latitude", "checkin_longitude",
                 "checkout_latitude", "checkout_longitude", "geofence_valid",
                 "checklist_done", "checklist_total", "travel_type", "vehicle_used"],
                { limit: 1 }
            );

            const collections = await this.orm.searchRead(
                "visit.collection",
                [["visit_id", "=", visit.id], ["state", "=", "confirmed"]],
                ["id", "name", "amount", "payment_mode", "date"],
                { limit: 20 }
            );

            const orders = await this.orm.searchRead(
                "sale.order",
                [["visit_id", "=", visit.id]],
                ["id", "name", "amount_total", "state"],
                { limit: 20 }
            );

            const tickets = await this.orm.searchRead(
                "visit.ticket",
                [["visit_id", "=", visit.id]],
                ["id", "name", "subject", "category", "priority", "state"],
                { limit: 10 }
            );

            this.state.visitDetail = {
                ...rows[0],
                collections,
                orders,
                tickets,
            };
        } catch (e) {
            console.error("[MobileVisits] detail:", e);
        } finally {
            this.state.detailLoading = false;
        }
    }

    closeDetail() {
        this.state.showDetail  = false;
        this.state.visitDetail = null;
    }

    // ── Formatters ───────────────────────────────────────────────────────────
    fmtDate(dt) {
        if (!dt) return "—";
        return new Date(dt).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
    }

    fmtTime(dt) {
        if (!dt) return "--:--";
        return new Date(dt).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
    }

    fmtMoney(v) {
        if (!v) return "₹0";
        if (v >= 100000) return `₹${(v / 100000).toFixed(1)}L`;
        if (v >= 1000)   return `₹${(v / 1000).toFixed(0)}K`;
        return `₹${Math.round(v).toLocaleString("en-IN")}`;
    }

    statusClass(status) {
        const map = { completed: "success", in_progress: "warning", planned: "info", cancelled: "danger" };
        return map[status] || "muted";
    }

    statusLabel(status) {
        const map = { completed: "Completed", in_progress: "In Progress", planned: "Planned", cancelled: "Cancelled" };
        return map[status] || status;
    }

    statusIcon(status) {
        const map = { completed: "fa-check-circle", in_progress: "fa-circle", planned: "fa-clock-o", cancelled: "fa-times-circle" };
        return map[status] || "fa-circle";
    }

    priorityClass(p) {
        const map = { Low: "info", Medium: "warning", High: "danger", Critical: "danger" };
        return map[p] || "muted";
    }

    getInitials(name) {
        return (name || "?").split(" ").slice(0, 2).map(w => w[0] || "").join("").toUpperCase();
    }

    getAvatarGradient(str) {
        const gradients = [
            "linear-gradient(135deg,#4361ee,#3a0ca3)",
            "linear-gradient(135deg,#06d6a0,#019b72)",
            "linear-gradient(135deg,#f72585,#b5179e)",
            "linear-gradient(135deg,#f77f00,#d62828)",
            "linear-gradient(135deg,#7209b7,#3a0ca3)",
            "linear-gradient(135deg,#4cc9f0,#0077b6)",
        ];
        let hash = 0;
        for (let i = 0; i < (str || "").length; i++) hash = str.charCodeAt(i) + ((hash << 5) - hash);
        return gradients[Math.abs(hash) % gradients.length];
    }
}
