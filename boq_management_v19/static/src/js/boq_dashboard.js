/** @odoo-module **/
/**
 * BOQ Dashboard — Odoo 19 OWL Component
 * Task 4: Vendor-wise RFQ summary, margin %, project stage, payment status.
 */

import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

// ─── Helper: format currency ────────────────────────────────────────────────
function formatCurrency(value, symbol, position) {
    const formatted = Number(value || 0).toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });
    return position === "after" ? `${formatted} ${symbol}` : `${symbol}${formatted}`;
}

// ─── Helper: margin color class ─────────────────────────────────────────────
function marginClass(pct) {
    if (pct >= 30) return "boq_margin_high";
    if (pct >= 15) return "boq_margin_mid";
    if (pct >= 0)  return "boq_margin_low";
    return "boq_margin_neg";
}

// ─── Helper: BOQ state badge ─────────────────────────────────────────────────
function stateBadgeClass(state) {
    const map = {
        draft: "bg-secondary",
        submitted: "bg-warning text-dark",
        approved: "bg-info",
        rejected: "bg-danger",
        done: "bg-success",
    };
    return map[state] || "bg-secondary";
}

// ═══════════════════════════════════════════════════════════════════════════════
// BoqDashboard Component
// ═══════════════════════════════════════════════════════════════════════════════
export class BoqDashboard extends Component {
    static template = "boq_management_v19.BoqDashboard";
    static props = {};

    setup() {
        this.orm        = useService("orm");
        this.action     = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            loading: true,
            stats: {},
            vendors: [],
            error: null,
            filterVendor: "",
        });

        onWillStart(() => this._loadAll());
    }

    // ── Data loading ────────────────────────────────────────────────────────
    async _loadAll() {
        try {
            const [stats, vendors] = await Promise.all([
                this.orm.call("boq.boq", "get_dashboard_stats", []),
                this.orm.call("boq.boq", "get_vendor_summary", []),
            ]);
            this.state.stats   = stats;
            this.state.vendors = vendors;
        } catch (err) {
            this.state.error = err.message || "Failed to load dashboard data.";
        } finally {
            this.state.loading = false;
        }
    }

    async refresh() {
        this.state.loading = true;
        this.state.error = null;
        await this._loadAll();
    }

    // ── Navigation helpers ──────────────────────────────────────────────────
    openAllBoqs() {
        this.action.doAction("boq_management_v19.action_boq_boq");
    }

    openRfqs() {
        this.action.doAction("boq_management_v19.action_boq_rfq_list");
    }

    openVendorRfqs(vendorId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "RFQs",
            res_model: "purchase.order",
            view_mode: "list,form",
            domain: [["partner_id", "=", vendorId]],
            target: "current",
        });
    }

    // ── Computed getters ────────────────────────────────────────────────────
    get filteredVendors() {
        const q = (this.state.filterVendor || "").toLowerCase();
        if (!q) return this.state.vendors;
        return this.state.vendors.filter(v =>
            (v.vendor_name || "").toLowerCase().includes(q)
        );
    }

    get currencySymbol() {
        return this.state.stats.currency_symbol || "$";
    }

    get currencyPosition() {
        return this.state.stats.currency_position || "before";
    }

    fmtCurrency(val) {
        return formatCurrency(val, this.currencySymbol, this.currencyPosition);
    }

    marginClass(pct) { return marginClass(pct); }
    stateBadgeClass(state) { return stateBadgeClass(state); }

    get stateLabels() {
        return {
            draft: "Draft",
            submitted: "Submitted",
            approved: "Approved",
            rejected: "Rejected",
            done: "Done",
        };
    }

    get stateSummary() {
        const sc = this.state.stats.state_counts || {};
        return [
            { key: "draft",     label: "Draft",     cls: "bg-secondary",        val: sc.draft     || 0 },
            { key: "submitted", label: "Submitted",  cls: "bg-warning text-dark", val: sc.submitted || 0 },
            { key: "approved",  label: "Approved",   cls: "bg-info",             val: sc.approved  || 0 },
            { key: "rejected",  label: "Rejected",   cls: "bg-danger",           val: sc.rejected  || 0 },
            { key: "done",      label: "Done",       cls: "bg-success",          val: sc.done      || 0 },
        ].filter(s => s.val > 0);
    }
}

// Register as client action
registry.category("actions").add("boq_management_v19.boq_dashboard_action", BoqDashboard);
