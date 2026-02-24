/** @odoo-module **/

import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class InvoiceList extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.actionService = useService("action");

        this.state = useState({
            loading: true,
            invoices: [],
            invoiceFilter : {customer: "", from_date: "", to_date: "", status: ""},
        });

        onWillStart(async () => {
            await this.loadInvoices();
        });
    }

    async loadInvoices(){
        const invoiceData = await this.orm.searchRead(
            "account.move",
            [["invoice_user_id", "=", this.props.userId], ["invoice_user_id", "!=", false], ["move_type", "=", "out_invoice"]],
            ["name", "partner_id", "invoice_date", "state", "amount_total", "invoice_line_ids"]
        );
        const invoices = invoiceData.map(invoice => ({
            ...invoice,
            item_count: invoice.invoice_line_ids.length
        }));
        this.state.invoices = invoices || null;
        this.state.loading = false;
    }

    async applyInvoiceFilters() {
        const filters = this.state.invoiceFilter;
        const results =  await this.orm.call("hr.employee", "get_account_filtered_data", [this.props.employeeId, this.state.invoiceFilter]);
        this.state.invoices = results || null;
    }
}

InvoiceList.template = "employee_dashboard.InvoiceList";
