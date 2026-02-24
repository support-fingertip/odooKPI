/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class KpiTargetDashboard extends Component {
    static template = "kpi_target.KpiDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            rows: [],
            teamRows: [],
            kpiTypes: [],
            periods: [],
            // undefined = "not yet initialised" (auto-select first period on first load)
            // null      = user explicitly chose "All Periods"
            selectedPeriodId: undefined,
            loading: true,
            activeTab: "individual",  
            editingCell: null,   
            editValue: "",
            summary: {
                totalIndividual: 0,
                avgAchievement: 0,
                achievedCount: 0,
                teamCount: 0,
            },
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData() {
        this.state.loading = true;
        try {
            // Pass null when "All Periods"; undefined is treated as null by JSON serialisation
            const periodArg = this.state.selectedPeriodId ?? null;
            const data = await this.orm.call(
                "kpi.target",
                "get_kpi_dashboard_data",
                [periodArg]
            );
            this.state.rows = data.rows || [];
            this.state.teamRows = data.team_rows || [];
            this.state.kpiTypes = data.kpi_types || [];
            this.state.periods = data.periods || [];

            // Auto-select the most-recent period only on the very first load
            // (selectedPeriodId === undefined). After that, honour the user's choice,
            // including null which means "All Periods".
            if (this.state.selectedPeriodId === undefined && this.state.periods.length > 0) {
                this.state.selectedPeriodId = this.state.periods[0].id;
                await this.loadData();
                return;
            }

            this._computeSummary();
        } catch (error) {
            this.notification.add("Failed to load dashboard data", { type: "danger" });
            console.error(error);
        } finally {
            this.state.loading = false;
        }
    }

    _computeSummary() {
        const rows = this.state.rows;
        const totalIndividual = rows.length;
        const avgAchievement = totalIndividual > 0
            ? rows.reduce((s, r) => s + r.achievements.overall, 0) / totalIndividual
            : 0;
        const achievedCount = rows.filter(r => r.achievements.overall >= 100).length;
        this.state.summary = {
            totalIndividual,
            avgAchievement: Math.round(avgAchievement * 10) / 10,
            achievedCount,
            teamCount: this.state.teamRows.length,
        };
    }


    async onPeriodChange(ev) {
        const val = parseInt(ev.target.value);
        this.state.selectedPeriodId = isNaN(val) ? null : val;
        await this.loadData();
    }

    setTab(tab) {
        this.state.activeTab = tab;
        this.state.editingCell = null;
        this.state.editValue = "";
    }


    onCellClick(targetId, kpiKey) {
        const cellKey = `${targetId}__${kpiKey}`;
        const row = this.state.rows.find(r => r.id === targetId);
        if (row) {
            this.state.editingCell = cellKey;
            this.state.editValue = String(row.targets[kpiKey] || 0);
        }
    }

    async onInputBlur() {
        await this.saveCell();
    }

    async onInputKeydown(ev) {
        if (ev.key === "Enter") {
            await this.saveCell();
        } else if (ev.key === "Escape") {
            this.state.editingCell = null;
            this.state.editValue = "";
        }
    }

    async saveCell() {
        if (!this.state.editingCell) return;

        const sepIdx = this.state.editingCell.indexOf("__");
        const targetId = parseInt(this.state.editingCell.slice(0, sepIdx));
        const kpiKey = this.state.editingCell.slice(sepIdx + 2);
        const value = parseFloat(this.state.editValue) || 0;

        try {
            const result = await this.orm.call(
                "kpi.target",
                "save_target_value",
                [targetId, kpiKey, value]
            );

            if (result.success) {
                const row = this.state.rows.find(r => r.id === targetId);
                if (row) {
                    row.targets[kpiKey] = value;
                    row.actuals[kpiKey] = result.actual;
                    row.achievements[kpiKey] = result.achievement;
                    row.achievements.overall = result.overall;
                }
                this._computeSummary();
                this.notification.add("Target updated successfully", { type: "success" });
            } else {
                this.notification.add(result.error || "Failed to save target", { type: "danger" });
            }
        } catch (error) {
            this.notification.add("Failed to save target", { type: "danger" });
            console.error(error);
        } finally {
            this.state.editingCell = null;
            this.state.editValue = "";
        }
    }

    async openTargetForm(targetId) {
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "kpi.target",
            res_id: targetId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async openTeamTargetForm(teamTargetId) {
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "kpi.manager.target",
            res_id: teamTargetId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async openCreateIndividualTarget() {
        const ctx = {};
        if (this.state.selectedPeriodId) {
            ctx.default_period_id = this.state.selectedPeriodId;
        }
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "kpi.target",
            views: [[false, "form"]],
            target: "current",
            context: ctx,
        });
    }

    async openCreateTeamTarget() {
        const ctx = {};
        if (this.state.selectedPeriodId) {
            ctx.default_period_id = this.state.selectedPeriodId;
        }
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "kpi.manager.target",
            views: [[false, "form"]],
            target: "current",
            context: ctx,
        });
    }


    getAchievementClass(pct) {
        if (pct >= 100) return "kpi-ach-excellent";
        if (pct >= 75) return "kpi-ach-good";
        if (pct >= 50) return "kpi-ach-average";
        return "kpi-ach-low";
    }

    getProgressStyle(pct) {
        const clamped = Math.min(pct || 0, 100);
        let color = "#dc3545"; 
        if (clamped >= 100) color = "#198754"; 
        else if (clamped >= 75) color = "#ffc107"; 
        else if (clamped >= 50) color = "#fd7e14"; 
        return `width: ${clamped}%; background-color: ${color};`;
    }

    getStateBadgeClass(state) {
        const map = {
            draft: "badge rounded-pill bg-secondary",
            confirmed: "badge rounded-pill bg-primary",
            done: "badge rounded-pill bg-success",
        };
        return map[state] || "badge rounded-pill bg-secondary";
    }

    getModeBadgeClass(mode) {
        return mode === "distribute"
            ? "badge rounded-pill bg-info text-dark"
            : "badge rounded-pill bg-warning text-dark";
    }

    formatNumber(val, decimals = 0) {
        if (!val && val !== 0) return "—";
        if (decimals === 0 && Number.isInteger(val)) return val.toString();
        return Number(val).toFixed(decimals);
    }

    formatPct(val) {
        if (!val && val !== 0) return "0%";
        return `${Number(val).toFixed(1)}%`;
    }

    isEditing(targetId, kpiKey) {
        return this.state.editingCell === `${targetId}__${kpiKey}`;
    }
}

registry.category("actions").add("kpi_target_dashboard", KpiTargetDashboard);
