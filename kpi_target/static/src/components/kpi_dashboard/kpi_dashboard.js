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
            kpiTypes: [],
            periods: [],
            selectedPeriodId: null,
            loading: true,
            editingCell: null, // format: "targetId-kpiKey"
            editValue: "",
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData() {
        this.state.loading = true;
        try {
            const data = await this.orm.call(
                "kpi.target",
                "get_kpi_dashboard_data",
                [this.state.selectedPeriodId]
            );
            this.state.rows = data.rows || [];
            this.state.kpiTypes = data.kpi_types || [];
            this.state.periods = data.periods || [];
            
            // Set default period to first one if not selected
            if (!this.state.selectedPeriodId && this.state.periods.length > 0) {
                this.state.selectedPeriodId = this.state.periods[0].id;
                // Reload with the selected period
                await this.loadData();
                return;
            }
        } catch (error) {
            this.notification.add("Failed to load dashboard data", { type: "danger" });
            console.error(error);
        } finally {
            this.state.loading = false;
        }
    }

    async onPeriodChange(ev) {
        this.state.selectedPeriodId = parseInt(ev.target.value);
        await this.loadData();
    }

    onCellClick(targetId, kpiKey) {
        const cellKey = `${targetId}-${kpiKey}`;
        const row = this.state.rows.find(r => r.id === targetId);
        if (row) {
            this.state.editingCell = cellKey;
            this.state.editValue = row.targets[kpiKey].toString();
        }
    }

    async onInputBlur() {
        await this.saveCell();
    }

    async onInputKeydown(ev) {
        if (ev.key === 'Enter') {
            await this.saveCell();
        } else if (ev.key === 'Escape') {
            this.state.editingCell = null;
            this.state.editValue = "";
        }
    }

    async saveCell() {
        if (!this.state.editingCell) return;

        const [targetIdStr, kpiKey] = this.state.editingCell.split('-');
        const targetId = parseInt(targetIdStr);
        const value = parseFloat(this.state.editValue) || 0;

        try {
            const result = await this.orm.call(
                "kpi.target",
                "save_target_value",
                [targetId, kpiKey, value]
            );

            if (result.success) {
                // Update the row data
                const row = this.state.rows.find(r => r.id === targetId);
                if (row) {
                    row.targets[kpiKey] = value;
                    row.actuals[kpiKey] = result.actual;
                    row.achievements[kpiKey] = result.achievement;
                }
                this.notification.add("Target value saved successfully", { type: "success" });
            } else {
                this.notification.add(result.error || "Failed to save target value", { type: "danger" });
            }
        } catch (error) {
            this.notification.add("Failed to save target value", { type: "danger" });
            console.error(error);
        } finally {
            this.state.editingCell = null;
            this.state.editValue = "";
        }
    }

    getAchievementClass(pct) {
        if (pct >= 100) return 'text-success';
        if (pct >= 75) return 'text-warning';
        return 'text-danger';
    }

    getProgressVariant(pct) {
        if (pct >= 100) return 'success';
        if (pct >= 75) return 'warning';
        return 'danger';
    }

    formatNumber(val) {
        return val ? val.toFixed(2) : '0.00';
    }

    formatPct(val) {
        return val ? val.toFixed(1) + '%' : '0.0%';
    }

    getStateBadgeClass(state) {
        const classes = {
            'draft': 'badge bg-info',
            'confirmed': 'badge bg-success',
            'done': 'badge bg-secondary',
        };
        return classes[state] || 'badge bg-secondary';
    }

    async openTargetForm(targetId) {
        await this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'kpi.target',
            res_id: targetId,
            views: [[false, 'form']],
            target: 'current',
        });
    }
}

registry.category("actions").add("kpi_target_dashboard", KpiTargetDashboard);
