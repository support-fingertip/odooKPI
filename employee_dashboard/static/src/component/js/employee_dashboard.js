/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { InvoiceList } from "./invoice_list";
import { PJPList } from "./pjp_list";
import { OrdersList } from "./order_list";
import { ExpenseList } from "./expense";
import { AttendanceList } from "./attendance";
import { VisitList } from "./visit";
import { TodayVisit } from "./today_visit";

export class EmployeeComponent extends Component {
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.state = useState({
            userId: null,
            selectedEmployee: null,
            activeTab: "details",
            details: null,
            employees: [],
            isManager: false,
            currentUserEmployeeId: null,
        });

        onWillStart(async () => {
            await this.loadUserAccessInfo();
            await this.loadEmployees();
            await this.autoSelectEmployee();
        });
    }

    async loadUserAccessInfo() {
        try {
            const accessInfo = await this.orm.call(
                "employee.dashboard",
                "get_user_access_info",
                []
            );
            
            this.state.isManager = accessInfo.is_manager;
            this.state.currentUserEmployeeId = accessInfo.employee_id;
        } catch (error) {
            console.error("Error loading user access info:", error);
            this.notification.add("Error loading user permissions", {
                type: "danger",
            });
        }
    }

    async loadEmployees() {
        try {
            this.state.employees = await this.orm.call(
                "employee.dashboard",
                "get_accessible_employees",
                []
            );
        } catch (error) {
            console.error("Error loading employees:", error);
            this.notification.add("Error loading employees", {
                type: "danger",
            });
        }
    }

    async autoSelectEmployee() {
        if (!this.state.isManager && this.state.currentUserEmployeeId) {
            this.state.selectedEmployee = this.state.currentUserEmployeeId;
            await this.loadEmployeeDetails(this.state.currentUserEmployeeId);
        } else if (this.state.isManager && this.state.employees.length > 0) {
            
        }
    }

    async selectEmployee(ev) {
        const id = parseInt(ev.target.value);
        this.state.selectedEmployee = id || null;
        
        console.log("Selected employee ID:", id); 
        
        if (!id) {
            this.state.userId = null;
            this.state.details = null;
            return;
        }
        
        await this.loadEmployeeDetails(id);
        console.log("After loading details - userId:", this.state.userId, "selectedEmployee:", this.state.selectedEmployee); // DEBUG
    }

    async loadEmployeeDetails(employeeId) {
        try {
            const employeeData = await this.orm.searchRead(
                "hr.employee",
                [["id", "=", employeeId]],
                ["name", "work_email", "work_phone", "user_id"]
            );
            
            if (employeeData.length > 0) {
                this.state.details = employeeData[0];
                this.state.userId = employeeData[0].user_id?.[0] || null;
                console.log("Employee details loaded:", this.state.details); 
            }
        } catch (error) {
            console.error("Error loading employee details:", error);
            this.notification.add("Error loading employee details", {
                type: "danger",
            });
        }
    }

    changeTab(tab) {
        this.state.activeTab = tab;
    }
}

EmployeeComponent.components = { 
    InvoiceList, 
    PJPList, 
    OrdersList, 
    ExpenseList, 
    AttendanceList, 
    VisitList, 
    TodayVisit 
};
EmployeeComponent.template = "employee_dashboard.EmployeeComponent";

registry.category("actions").add("employee_dashboard_component", EmployeeComponent);