/** @odoo-module **/
/**
 * EMPLOYEE 360 — MOBILE ORDERS SCREEN
 * Sales orders list with filters and stats
 */

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class MobileOrders extends Component {
    static template = "employee_mobile.MobileOrders";

    setup() {
        this.orm          = useService("orm");
        this.notification = useService("notification");

        this.state = useState({
            loading:      true,
            orders:       [],
            filtered:     [],
            filter:       "month",    // today | week | month | all
            statusFilter: "all",
            search:       "",
            stats: {
                total:     0,
                confirmed: 0,
                draft:     0,
                amount:    0,
            },
            selectedOrder:   null,
            showOrderDetail: false,
            orderLines:      [],
            orderDetailBusy: false,
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
            const domain  = await this._buildDomain();
            const orders  = await this.orm.searchRead(
                "sale.order", domain,
                ["id", "name", "partner_id", "amount_total", "state",
                 "date_order", "order_line", "visit_id", "user_id"],
                { order: "date_order desc", limit: 100 }
            );
            this.state.orders   = orders;
            this._applyFilters();
            this._calcStats();
        } catch (e) {
            console.error("[MobileOrders] load:", e);
        } finally {
            this.state.loading = false;
        }
    }

    async _buildDomain() {
        const domain = [];
        const now    = new Date();

        switch (this.state.filter) {
            case "today": {
                const d = now.toISOString().slice(0, 10);
                domain.push(["date_order", ">=", d + " 00:00:00"]);
                domain.push(["date_order", "<=", d + " 23:59:59"]);
                break;
            }
            case "week": {
                const start = new Date(now); start.setDate(now.getDate() - now.getDay());
                domain.push(["date_order", ">=", start.toISOString().slice(0, 10) + " 00:00:00"]);
                break;
            }
            case "month": {
                const f = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-01`;
                domain.push(["date_order", ">=", f + " 00:00:00"]);
                break;
            }
        }

        if (this.state.statusFilter !== "all") {
            domain.push(["state", "=", this.state.statusFilter]);
        }

        // Scope by user
        if (this.empId && !this.isManager) {
            try {
                const emp = await this.orm.searchRead(
                    "hr.employee", [["id", "=", this.empId]], ["user_id"]
                );
                const userId = emp[0]?.user_id?.[0];
                if (userId) domain.push(["user_id", "=", userId]);
            } catch (e) {}
        }

        return domain;
    }

    _applyFilters() {
        let list = [...this.state.orders];
        if (this.state.search) {
            const q = this.state.search.toLowerCase();
            list = list.filter(o =>
                (o.name || "").toLowerCase().includes(q) ||
                (o.partner_id?.[1] || "").toLowerCase().includes(q)
            );
        }
        this.state.filtered = list;
    }

    _calcStats() {
        const orders = this.state.filtered;
        this.state.stats = {
            total:     orders.length,
            confirmed: orders.filter(o => o.state === "sale" || o.state === "done").length,
            draft:     orders.filter(o => o.state === "draft").length,
            amount:    orders.reduce((s, o) => s + (o.amount_total || 0), 0),
        };
    }

    async setFilter(f) {
        this.state.filter = f;
        await this._load();
    }

    async setStatusFilter(s) {
        this.state.statusFilter = s;
        this._applyFilters();
        this._calcStats();
    }

    onSearchInput(ev) {
        this.state.search = ev.target.value;
        this._applyFilters();
        this._calcStats();
    }

    async openOrderDetail(order) {
        this.state.selectedOrder   = order;
        this.state.showOrderDetail = true;
        this.state.orderDetailBusy = true;
        this.state.orderLines      = [];
        try {
            const lines = await this.orm.searchRead(
                "sale.order.line",
                [["order_id", "=", order.id]],
                ["id", "product_id", "product_uom_qty", "price_unit", "price_subtotal", "product_tag", "scheme_discount"],
                { limit: 50 }
            );
            this.state.orderLines = lines;
        } catch (e) {
            console.warn("[MobileOrders] order lines:", e);
        } finally {
            this.state.orderDetailBusy = false;
        }
    }

    closeOrderDetail() {
        this.state.showOrderDetail = false;
        this.state.selectedOrder   = null;
        this.state.orderLines      = [];
    }

    // ── Formatters ───────────────────────────────────────────────────────────
    fmtMoney(v) {
        if (!v) return "₹0";
        if (v >= 10000000) return `₹${(v / 10000000).toFixed(1)}Cr`;
        if (v >= 100000)   return `₹${(v / 100000).toFixed(1)}L`;
        if (v >= 1000)     return `₹${(v / 1000).toFixed(0)}K`;
        return `₹${Math.round(v).toLocaleString("en-IN")}`;
    }

    fmtDate(dt) {
        if (!dt) return "—";
        return new Date(dt).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
    }

    fmtDateTime(dt) {
        if (!dt) return "—";
        const d = new Date(dt);
        return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) +
               " " + d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
    }

    statusLabel(state) {
        const map = { draft: "Draft", sent: "Sent", sale: "Confirmed", done: "Done", cancel: "Cancelled" };
        return map[state] || state;
    }

    statusClass(state) {
        const map = { sale: "success", done: "success", draft: "warning", sent: "info", cancel: "danger" };
        return map[state] || "muted";
    }

    getInitials(name) {
        return (name || "?").split(" ").slice(0, 2).map(w => w[0] || "").join("").toUpperCase();
    }

    getAvatarGradient(str) {
        const gradients = [
            "linear-gradient(135deg,#f72585,#b5179e)",
            "linear-gradient(135deg,#4361ee,#3a0ca3)",
            "linear-gradient(135deg,#06d6a0,#019b72)",
            "linear-gradient(135deg,#f77f00,#d62828)",
        ];
        let h = 0;
        for (let i = 0; i < (str || "").length; i++) h = str.charCodeAt(i) + ((h << 5) - h);
        return gradients[Math.abs(h) % gradients.length];
    }
}
