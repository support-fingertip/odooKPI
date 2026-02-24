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
        const results =  await this.orm.call("hr.employee", "get_account_filtered_data", [this.props.employeeId, this.state.orderFilter]);
        this.state.orders = results || null;
        this.state.expandedOrderId = null;
        this.state.expandedOrderLines = [];
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
