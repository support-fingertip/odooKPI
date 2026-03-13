/** @odoo-module **/

import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class OrdersList extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.actionService = useService("action");

        this.state = useState({
            loading: true,
            orders: [],
            orderFilter : {customer: "", from_date: "", to_date: "", status: ""},
            expandedOrderId: null,
            expandedOrderLines: [],
        });

        onWillStart(async () => {
            await this.loadOrders();
        });
    }

    async loadOrders(){
        const orderData = await this.orm.searchRead(
            "sale.order",
            [["user_id", "=", this.props.userId]],
            ["name", "partner_id", "date_order", "state", "amount_total", "order_line"]
        );
        const orders = orderData.map(order => ({
            ...order,
            item_count: order.order_line.length
        }));
        this.state.orders = orders || null;
        this.state.loading = false;
    }

    async applyOrderFilters() {
        const { customer, from_date, to_date, status } = this.state.orderFilter;
        const domain = [["user_id", "=", this.props.userId]];
        if (customer) domain.push(["partner_id.name", "ilike", customer]);
        if (from_date) domain.push(["date_order", ">=", from_date]);
        if (to_date) domain.push(["date_order", "<=", to_date + " 23:59:59"]);
        if (status && status !== "All") domain.push(["state", "=", status]);
        const orderData = await this.orm.searchRead(
            "sale.order", domain,
            ["name", "partner_id", "date_order", "state", "amount_total", "order_line"]
        );
        this.state.orders = orderData.map(o => ({ ...o, item_count: o.order_line.length }));
        this.state.expandedOrderId = null;
        this.state.expandedOrderLines = [];
    }

    get uniqueRetailerCount() {
        if (!this.state.orders) return 0;
        const ids = new Set(this.state.orders.map(o => o.partner_id ? o.partner_id[0] : 0));
        return ids.size;
    }

    async toggleOrderDetails(orderId, orderLineIds) {
        if (this.state.expandedOrderId === orderId) {
            this.state.expandedOrderId = null;
            this.state.expandedOrderLines = [];
            return;
        }

        try {
            if (orderLineIds && orderLineIds.length > 0) {
                const lines = await this.orm.searchRead(
                    "sale.order.line",
                    [["id", "in", orderLineIds]],
                    ["product_id", "product_uom_qty", "price_unit", "price_subtotal", "name"]
                );
                this.state.expandedOrderLines = lines;
            } else {
                this.state.expandedOrderLines = [];
            }
            this.state.expandedOrderId = orderId;
        } catch (error) {
            console.error("Error loading order details:", error);
            this.notification.add("Failed to load order details", { type: "danger" });
        }
    }
}

OrdersList.template = "employee_dashboard.OrdersList";
