/** @odoo-module **/

import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class ExpenseList extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.actionService = useService("action");

        this.state = useState({
            loading: true,
            expenseRecords: [],
            expenseFromDate: "",
            expenseToDate: "",
            expenseStatus: "all",
        });

        onWillStart(async () => {
            await this.loadExpenses();
        });
    }

    async loadExpenses() {
        if (!this.props.employeeId) return;

        try {
            const today = new Date();
            const firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
            const lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0);

            this.state.expenseFromDate = firstDay.toISOString().split('T')[0];
            this.state.expenseToDate = lastDay.toISOString().split('T')[0];
            this.state.expenseStatus = "all";

            await this.loadExpenseData();
        } catch (error) {
            console.error("Error loading expenses:", error);
        }
    }

    async onExpenseDateChange() {
        await this.loadExpenseData();
    }

    async onExpenseStatusChange(ev) {
        this.state.expenseStatus = ev.target.value;
        await this.loadExpenseData();
    }

    async loadExpenseData() {
        if (!this.props.employeeId) return;

        try {
            const fromDate = this.state.expenseFromDate || '';
            const toDate = this.state.expenseToDate || '';
            const status = this.state.expenseStatus || 'all';

            const domain = [
                ["employee_id", "=", this.props.employeeId]
            ];

            if (fromDate) {
                domain.push(["date", ">=", fromDate]);
            }
            if (toDate) {
                domain.push(["date", "<=", toDate]);
            }
            if (status && status !== "all") {
                domain.push(["state", "=", status]);
            }

            const expenseRecords = await this.orm.searchRead(
                "hr.expense",
                domain,
                ["name", "date", "state", "total_amount", "product_id"],
                { order: "date desc" }
            );

            const expensesByMonth = {};

            expenseRecords.forEach(record => {
                const date = new Date(record.date);
                const monthKey = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-01`;

                if (!expensesByMonth[monthKey]) {
                    expensesByMonth[monthKey] = {
                        month: monthKey,
                        status: this.getExpenseStatusLabel(record.state),
                        ta: 0,
                        da: 0,
                        other: 0,
                        totalAmt: 0
                    };
                }

                const amount = record.total_amount || 0;
                const productName = record.product_id ? record.product_id[1].toLowerCase() : '';

                if (productName.includes('travel') || productName.includes('ta')) {
                    expensesByMonth[monthKey].ta += amount;
                } else if (productName.includes('da') || productName.includes('allowance')) {
                    expensesByMonth[monthKey].da += amount;
                } else {
                    expensesByMonth[monthKey].other += amount;
                }

                expensesByMonth[monthKey].totalAmt += amount;
            });

            this.state.expenseRecords = Object.values(expensesByMonth).sort((a, b) =>
                new Date(b.month) - new Date(a.month)
            );

        } catch (error) {
            console.error("Error loading expense data:", error);
            this.state.expenseRecords = [];
        }
    }

    getExpenseStatusLabel(state) {
        const statusMap = {
            'draft': 'Not Submitted',
            'reported': 'Submitted',
            'approved': 'Approved',
            'done': 'Paid',
            'refused': 'Refused'
        };
        return statusMap[state] || 'Submitted';
    }

}

ExpenseList.template = "employee_dashboard.ExpenseList";
