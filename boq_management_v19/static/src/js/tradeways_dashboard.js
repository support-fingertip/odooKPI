/** @odoo-module **/
/**
 * Tradeways Dashboard — Odoo 19 OWL Component  (Task 4)
 * Similar structure to BoqDashboard but focused on Tradeways vendor ratings.
 */

import { Component, useState, onWillStart, onPatched, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

// ─── Helpers ────────────────────────────────────────────────────────────────
function ratingStars(avg) {
    const filled = Math.round(avg || 0);
    return "★".repeat(filled) + "☆".repeat(5 - filled);
}

function ratingColorClass(avg) {
    if (avg >= 4.5) return "tw_rating_excellent";
    if (avg >= 3.5) return "tw_rating_good";
    if (avg >= 2.5) return "tw_rating_fair";
    if (avg > 0)    return "tw_rating_poor";
    return "tw_rating_none";
}

function tradeTypeBadgeClass(type) {
    const map = {
        supplier:      "bg-primary",
        subcontractor: "bg-info text-dark",
        consultant:    "bg-warning text-dark",
        manufacturer:  "bg-success",
        other:         "bg-secondary",
    };
    return map[type] || "bg-secondary";
}

// ═══════════════════════════════════════════════════════════════════════════════
// TradewysDashboard Component
// ═══════════════════════════════════════════════════════════════════════════════
export class TradewysDashboard extends Component {
    static template = "boq_management_v19.TradewysDashboard";
    static props = {
        action:            { type: Object,   optional: true },
        actionId:          { optional: true },
        updateActionState: { type: Function, optional: true },
        className:         { type: String,   optional: true },
    };

    setup() {
        this.orm          = useService("orm");
        this.action       = useService("action");
        this.notification = useService("notification");
        this.scrollContainerRef = useRef("scrollContainer");
        this.notebookRef        = useRef("notebook");
        this._scrollPending = false;

        this.state = useState({
            loading: true,
            stats: {},
            vendors: [],
            error: null,
            filterVendor: "",
            filterType: "",
            selectedVendor: null,
            activeTab: "history",
            ratingHistory: [],
            ratingHistoryLoading: false,
        });

        onWillStart(() => this._loadAll());
        onPatched(() => {
            if (this._scrollPending && this.notebookRef.el) {
                this._scrollPending = false;
                const notebook  = this.notebookRef.el;
                const container = this.scrollContainerRef.el;
                if (!container) return;
                requestAnimationFrame(() => {
                    const cRect = container.getBoundingClientRect();
                    const nRect = notebook.getBoundingClientRect();
                    container.scrollBy({ top: nRect.top - cRect.top - 16, behavior: "smooth" });
                });
            }
        });
    }

    // ── Data loading ──────────────────────────────────────────────────────
    async _loadAll() {
        try {
            const [stats, vendors] = await Promise.all([
                this.orm.call("tradeways.vendor", "get_tradeways_dashboard_stats", []),
                this.orm.call("tradeways.vendor", "get_tradeways_vendor_list",     []),
            ]);
            this.state.stats   = stats;
            this.state.vendors = vendors;
        } catch (err) {
            this.state.error = err.message || "Failed to load Tradeways dashboard data.";
        } finally {
            this.state.loading = false;
        }
    }

    async refresh() {
        this.state.loading = true;
        this.state.error = null;
        this.state.selectedVendor = null;
        await this._loadAll();
    }

    // ── Navigation ────────────────────────────────────────────────────────
    openAllVendors() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Tradeways Vendors",
            res_model: "tradeways.vendor",
            views: [[false, "list"], [false, "kanban"], [false, "form"]],
            target: "current",
        });
    }

    openAllRatings() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Tradeways Ratings",
            res_model: "tradeways.rating",
            views: [[false, "list"], [false, "form"]],
            target: "current",
        });
    }

    openVendorForm(vendorId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Tradeways Vendor",
            res_model: "tradeways.vendor",
            res_id: vendorId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async selectVendor(vendor) {
        this.state.selectedVendor = vendor;
        this.state.activeTab = "history";
        this.state.ratingHistory = [];
        this.state.ratingHistoryLoading = true;
        this._scrollPending = true;
        try {
            const history = await this.orm.call(
                "tradeways.vendor", "get_tradeways_rating_history", [vendor.id]
            );
            this.state.ratingHistory = history;
        } catch (_) {
            this.state.ratingHistory = [];
        } finally {
            this.state.ratingHistoryLoading = false;
        }
    }

    closeNotebook() {
        this.state.selectedVendor = null;
    }

    clearFilter() {
        this.state.filterVendor = "";
        this.state.filterType = "";
    }

    setActiveTab(tab) {
        this.state.activeTab = tab;
    }

    // ── Computed getters ──────────────────────────────────────────────────
    get filteredVendors() {
        let list = this.state.vendors;
        const q = (this.state.filterVendor || "").toLowerCase();
        if (q) {
            list = list.filter(v =>
                (v.name || "").toLowerCase().includes(q) ||
                (v.contact_name || "").toLowerCase().includes(q)
            );
        }
        if (this.state.filterType) {
            list = list.filter(v => v.trade_type_key === this.state.filterType);
        }
        return list;
    }

    get vendorTotals() {
        const vendors = this.filteredVendors;
        const totalRatings  = vendors.reduce((s, v) => s + (v.rating_count || 0), 0);
        const rated         = vendors.filter(v => v.avg_rating > 0);
        const overallAvg    = rated.length
            ? (rated.reduce((s, v) => s + v.avg_rating, 0) / rated.length).toFixed(2)
            : "—";
        return { count: vendors.length, totalRatings, overallAvg, ratedCount: rated.length };
    }

    get tradeTypeOptions() {
        // Collect unique types from current vendor list
        const types = {};
        for (const v of this.state.vendors) {
            if (v.trade_type_key && !types[v.trade_type_key]) {
                types[v.trade_type_key] = v.trade_type;
            }
        }
        return Object.entries(types).map(([key, label]) => ({ key, label }));
    }

    ratingStars(avg)  { return ratingStars(avg); }
    ratingColorClass(avg) { return ratingColorClass(avg); }
    tradeTypeBadgeClass(type) { return tradeTypeBadgeClass(type); }

    get overallStars() {
        return ratingStars(this.state.stats.overall_avg || 0);
    }
}

// Register as client action
registry.category("actions").add(
    "boq_management_v19.tradeways_dashboard_action",
    TradewysDashboard
);
