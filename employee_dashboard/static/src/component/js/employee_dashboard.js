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
import { LocationMapCard } from "./location_map";
import { DashboardReport } from "./dashboard_report";

// ── Tab metadata ─────────────────────────────────────────────────
const TAB_META = {
    overview:    { title: "Dashboard",            icon: "fa-home",              gradient: "linear-gradient(135deg,#4361ee,#3a0ca3)" },
    todayvisit:  { title: "Today Visit",          icon: "fa-calendar-check-o",  gradient: "linear-gradient(135deg,#06d6a0,#019b72)" },  // nav label shown as "Today's Plan"
    visits:      { title: "Visit History",        icon: "fa-history",           gradient: "linear-gradient(135deg,#4cc9f0,#0077b6)" },
    orders:      { title: "Orders",               icon: "fa-shopping-cart",     gradient: "linear-gradient(135deg,#f72585,#b5179e)" },
    retailer:    { title: "Retailer Orders",      icon: "fa-list",              gradient: "linear-gradient(135deg,#0077b6,#023e8a)" },
    pjp:         { title: "PJP",                  icon: "fa-map",               gradient: "linear-gradient(135deg,#7209b7,#3a0ca3)" },
    attendance:  { title: "Attendance",           icon: "fa-clock-o",           gradient: "linear-gradient(135deg,#0077b6,#023e8a)" },
    expenses:    { title: "Expenses",             icon: "fa-money",             gradient: "linear-gradient(135deg,#f77f00,#d62828)" },
    invoices:    { title: "Invoices",             icon: "fa-file-text",         gradient: "linear-gradient(135deg,#06d6a0,#019b72)" },
    incentives:  { title: "Incentives",           icon: "fa-trophy",            gradient: "linear-gradient(135deg,#ffd166,#f77f00)" },
    summary:     { title: "Analytics",            icon: "fa-bar-chart",         gradient: "linear-gradient(135deg,#7209b7,#560bad)" },
};

// Checklist questions (from image (4).jpeg)
const DEFAULT_CHECKLIST = [
    { id: 1,  question: "Is the store exterior clean and well-maintained?",   done: false },
    { id: 2,  question: "Are all products properly displayed on shelves?",      done: false },
    { id: 3,  question: "Is the planogram being followed correctly?",           done: false },
    { id: 4,  question: "Are price tags visible on all products?",              done: false },
    { id: 5,  question: "Is the stock freshness maintained (FIFO)?",            done: false },
    { id: 6,  question: "Are POSM/promotional materials in place?",             done: false },
    { id: 7,  question: "Is the visi-cooler clean and functioning?",            done: false },
    { id: 8,  question: "Are competitor products encroaching display space?",   done: false },
    { id: 9,  question: "Is the back stock area organized?",                    done: false },
    { id: 10, question: "Has the retailer been briefed on new schemes?",        done: false },
];

export class EmployeeComponent extends Component {
    setup() {
        this.orm          = useService("orm");
        this.action       = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            userId:              null,
            selectedEmployee:    null,
            activeTab:           "todayvisit",
            details:             null,
            employees:           [],
            isManager:           false,
            currentUserEmployeeId: null,

            // Checkin
            checkinTime:         null,
            todayLabel:          this._todayLabel(),

            // Overview KPIs
            overviewKpi: {
                total_sales:   0,
                avg_sales:     0,
                outstanding:   0,
                visits:        0,
                collections:   0,
                achievement:   0,
                total_orders:  0,
            },

            // Beat Statistics
            beatStats: {
                total:       0,
                in_progress: 0,
                completed:   0,
                pending:     0,
                coverage:    0,
            },

            // PJP / Visit Statistics
            pjpStats: {
                total:     0,
                planned:   0,
                completed: 0,
                missed:    0,
                working_hours: "0m",
                visit_pct: 0,
                avg_visit: "0m",
            },

            // Target vs Achievement
            targetAchievement: {
                target:     0,
                actual:     0,
                pct:        0,
            },

            // Store / Region Performance
            storePerformance: [],

            // Top Accounts
            topAccounts: [],

            // Retailer Orders
            retailerOrders: [],
            retailerOrderStats: { retailers: 0, orders: 0, totalValue: 0 },
            retailerTab: 'retailers',

            // Dashboard period filter
            dashPeriod: "month",

            // Accordion state
            accordion: {
                lastVisit:    false,
                currentVisit: false,
                assets:       false,
                checklist:    false,
                brochures:    false,
                beatStats:    true,
                pjpStats:     true,
                storePerf:    true,
                targetAch:    true,
            },

            // Last/current visit
            lastVisit:    null,
            currentVisit: null,

            // Checklist
            checklistItems: [...DEFAULT_CHECKLIST],
            checklistDone:  0,
            checklistTotal: DEFAULT_CHECKLIST.length,
        });

        onWillStart(async () => {
            await this.loadUserAccessInfo();
            await this.loadEmployees();
            await this.autoSelectEmployee();
            this._loadCheckinTime();
        });
    }

    // ── Tab helpers ───────────────────────────────────────────────
    tabTitle(tab)       { return (TAB_META[tab] || {}).title    || tab; }
    tabIconClass(tab)   { return (TAB_META[tab] || {}).icon     || "fa-circle"; }
    tabIconGradient(tab){ return (TAB_META[tab] || {}).gradient || "linear-gradient(135deg,#4361ee,#3a0ca3)"; }

    // ── Date helpers ──────────────────────────────────────────────
    _todayLabel() {
        const d = new Date();
        return d.toLocaleDateString("en-US", { weekday: "short", year: "numeric", month: "short", day: "numeric" });
    }

    _loadCheckinTime() {
        const now = new Date();
        this.state.checkinTime = now.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
    }

    formatDate(dt) {
        if (!dt) return "-";
        return new Date(dt).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
    }

    formatTime(dt) {
        if (!dt) return "-";
        return new Date(dt).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
    }

    formatLargeNumber(val) {
        if (!val) return "0";
        if (val >= 10000000) return (val / 10000000).toFixed(1) + "Cr";
        if (val >= 100000)   return (val / 100000).toFixed(1) + "L";
        if (val >= 1000)     return (val / 1000).toFixed(0) + "K";
        return Number(val).toLocaleString();
    }

    // ── User greeting helpers (role-aware) ────────────────────────
    greeting() {
        const h = new Date().getHours();
        if (h < 12) return "Good Morning";
        if (h < 17) return "Good Afternoon";
        return "Good Evening";
    }

    greetingIcon() {
        const h = new Date().getHours();
        if (h < 12) return "fa-sun-o";
        if (h < 17) return "fa-cloud-sun-o";  // afternoon
        return "fa-moon-o";
    }

    userFirstName() {
        if (!this.state.details || !this.state.details.name) return "there";
        return this.state.details.name.split(" ")[0];
    }

    // Returns a friendly topbar title — for users on Today tab: "My Workday"
    topbarTitle() {
        if (!this.state.isManager && this.state.activeTab === "todayvisit") {
            return "My Workday";
        }
        return this.tabTitle(this.state.activeTab);
    }

    // Returns the topbar icon gradient for current tab (user-aware)
    topbarGradient() {
        if (!this.state.isManager && this.state.activeTab === "todayvisit") {
            return "linear-gradient(135deg,#06d6a0,#019b72)";
        }
        return this.tabIconGradient(this.state.activeTab);
    }

    // Returns the topbar icon class (user-aware)
    topbarIcon() {
        if (!this.state.isManager && this.state.activeTab === "todayvisit") {
            return "fa-briefcase";
        }
        return this.tabIconClass(this.state.activeTab);
    }

    statusBadgeClass(status) {
        const map = {
            completed:   "emp360-badge emp360-badge-success",
            planned:     "emp360-badge emp360-badge-info",
            in_progress: "emp360-badge emp360-badge-warning",
            cancelled:   "emp360-badge emp360-badge-danger",
        };
        return map[status] || "emp360-badge emp360-badge-secondary";
    }

    // ── User & employee loading ───────────────────────────────────
    async loadUserAccessInfo() {
        try {
            const info = await this.orm.call("employee.dashboard", "get_user_access_info", []);
            this.state.isManager             = info.is_manager;
            this.state.currentUserEmployeeId = info.employee_id;
        } catch (e) {
            console.error("loadUserAccessInfo:", e);
            this.notification.add("Error loading user permissions", { type: "danger" });
        }
    }

    async loadEmployees() {
        try {
            this.state.employees = await this.orm.call("employee.dashboard", "get_accessible_employees", []);
        } catch (e) {
            console.error("loadEmployees:", e);
            this.notification.add("Error loading employees", { type: "danger" });
        }
    }

    async autoSelectEmployee() {
        if (!this.state.isManager && this.state.currentUserEmployeeId) {
            this.state.selectedEmployee = this.state.currentUserEmployeeId;
            // Regular users land directly on Today screen only
            this.state.activeTab = "todayvisit";
            await this.loadEmployeeDetails(this.state.currentUserEmployeeId);
            await this.loadOverviewKpi(this.state.currentUserEmployeeId);
        } else if (this.state.isManager) {
            // Managers default to overview dashboard
            this.state.activeTab = "overview";
        }
    }

    async selectEmployee(ev) {
        const id = parseInt(ev.target.value);
        this.state.selectedEmployee = id || null;
        if (!id) {
            this.state.userId = null;
            this.state.details = null;
            this.state.overviewKpi = { total_sales: 0, avg_sales: 0, outstanding: 0, visits: 0 };
            this.state.retailerOrders = [];
            this.state.retailerOrderStats = { retailers: 0, orders: 0, totalValue: 0 };
            return;
        }
        await this.loadEmployeeDetails(id);
        await this.loadOverviewKpi(id);
        // Auto-refresh current active tab data
        if (this.state.activeTab === 'retailer') {
            await this.loadRetailerOrders();
        }
        this.notification.add("Dashboard refreshed for selected employee", { type: "info" });
    }

    async loadEmployeeDetails(empId) {
        try {
            const rows = await this.orm.searchRead(
                "hr.employee",
                [["id", "=", empId]],
                ["name", "work_email", "work_phone", "user_id"]
            );
            if (rows.length > 0) {
                this.state.details = rows[0];
                this.state.userId  = rows[0].user_id?.[0] || null;
            }
        } catch (e) {
            console.error("loadEmployeeDetails:", e);
        }
    }

    async loadOverviewKpi(empId) {
        try {
            const today    = new Date();
            const firstDay = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,"0")}-01`;
            const todayStr = today.toISOString().split("T")[0];

            // ── Sales orders this month ──────────────────────────────
            const orders = await this.orm.searchRead(
                "sale.order",
                [
                    ["user_id", "=", this.state.userId || false],
                    ["date_order", ">=", firstDay + " 00:00:00"],
                    ["date_order", "<=", todayStr  + " 23:59:59"],
                    ["state",     "in", ["sale", "done"]],
                ],
                ["amount_total", "partner_id"],
                { limit: 1000 }
            );

            const totalSales  = orders.reduce((s, o) => s + (o.amount_total || 0), 0);
            const avgSales    = orders.length > 0 ? totalSales / orders.length : 0;
            const collections = Math.round(totalSales * 0.5); // approx 50% collected

            // ── Visits this month ────────────────────────────────────
            const allVisits = await this.orm.searchRead(
                "visit.model",
                [
                    ["employee_id",       "=", empId],
                    ["actual_start_time", ">=", firstDay + " 00:00:00"],
                ],
                ["id", "status", "partner_id", "actual_start_time"],
                { limit: 1000 }
            );

            const completedVisits = allVisits.filter(v => v.status === "completed").length;
            const plannedVisits   = allVisits.filter(v => v.status === "planned").length;
            const missedVisits    = allVisits.filter(v => v.status === "cancelled").length;

            // ── Last visit ───────────────────────────────────────────
            const lastVisitArr = await this.orm.searchRead(
                "visit.model",
                [["employee_id", "=", empId]],
                ["id","partner_id","beat_id","actual_start_time","actual_end_time","duration_display","status","order_count","total_order_amount"],
                { order: "actual_start_time desc", limit: 1 }
            );

            // ── Current in-progress visit ────────────────────────────
            const currentArr = await this.orm.searchRead(
                "visit.model",
                [["employee_id", "=", empId], ["status", "=", "in_progress"]],
                ["id","partner_id","actual_start_time","order_count","total_order_amount"],
                { limit: 1 }
            );

            // ── Beat statistics ──────────────────────────────────────
            await this._loadBeatStats(empId, todayStr);

            // ── Store performance ────────────────────────────────────
            await this._loadStorePerformance(orders, empId);

            // ── PJP stats ────────────────────────────────────────────
            this.state.pjpStats = {
                total:     allVisits.length,
                planned:   plannedVisits,
                completed: completedVisits,
                missed:    missedVisits,
                working_hours: `${Math.round(completedVisits * 0.5)}h`,
                visit_pct: allVisits.length > 0 ? Math.round((completedVisits / allVisits.length) * 100) : 0,
                avg_visit: "20m",
            };

            // ── Target vs achievement (placeholder using sales) ───────
            const monthlyTarget = totalSales * 1.2 || 100000;
            this.state.targetAchievement = {
                target: Math.round(monthlyTarget),
                actual: Math.round(totalSales),
                pct:    monthlyTarget > 0 ? Math.min(100, Math.round((totalSales / monthlyTarget) * 100)) : 0,
            };

            this.state.overviewKpi = {
                total_sales:   Math.round(totalSales),
                avg_sales:     Math.round(avgSales),
                outstanding:   0,
                visits:        allVisits.length,
                collections:   collections,
                achievement:   this.state.targetAchievement.pct,
                total_orders:  orders.length,
            };

            this.state.lastVisit    = lastVisitArr[0]  || null;
            this.state.currentVisit = currentArr[0]    || null;

        } catch (e) {
            console.error("loadOverviewKpi:", e);
        }
    }

    async _loadBeatStats(empId, todayStr) {
        try {
            const beats = await this.orm.searchRead(
                "beat.module",
                [["employee_id", "=", empId]],
                ["id", "status", "beat_number", "beat_date"],
                { limit: 200 }
            );
            const todayBeats = beats.filter(b => b.beat_date === todayStr);
            this.state.beatStats = {
                total:       beats.length,
                in_progress: beats.filter(b => b.status === "in_progress").length,
                completed:   beats.filter(b => b.status === "completed").length,
                pending:     beats.filter(b => b.status === "pending" || b.status === "draft").length,
                coverage:    beats.length > 0 ? Math.round((beats.filter(b => b.status === "completed").length / beats.length) * 100) : 0,
                today_total: todayBeats.length,
            };
        } catch (e) {
            console.warn("_loadBeatStats:", e);
            this.state.beatStats = { total: 0, in_progress: 0, completed: 0, pending: 0, coverage: 0, today_total: 0 };
        }
    }

    async _loadStorePerformance(orders, empId) {
        try {
            // Group orders by partner
            const byPartner = {};
            for (const o of orders) {
                const pid  = o.partner_id ? o.partner_id[0] : 0;
                const name = o.partner_id ? o.partner_id[1] : "Unknown";
                if (!byPartner[pid]) byPartner[pid] = { id: pid, name, revenue: 0, orders: 0 };
                byPartner[pid].revenue += (o.amount_total || 0);
                byPartner[pid].orders  += 1;
            }
            const totalRev = orders.reduce((s, o) => s + (o.amount_total || 0), 0);
            const perf = Object.values(byPartner).map(p => ({
                ...p,
                revenue:     Math.round(p.revenue),
                achievement: totalRev > 0 ? Math.min(100, Math.round((p.revenue / (totalRev / Object.keys(byPartner).length || 1)) * 60)) : 0,
                target:      Math.round(p.revenue * 1.35),
            })).sort((a, b) => b.revenue - a.revenue).slice(0, 6);

            this.state.storePerformance = perf;

            // Top accounts (top 3 by revenue)
            this.state.topAccounts = perf.slice(0, 3).map((p, i) => ({
                rank:    i + 1,
                name:    p.name,
                revenue: p.revenue,
                orders:  p.orders,
            }));
        } catch (e) {
            console.warn("_loadStorePerformance:", e);
            this.state.storePerformance = [];
            this.state.topAccounts      = [];
        }
    }

    setDashPeriod(period) {
        this.state.dashPeriod = period;
        if (this.state.selectedEmployee) {
            this.loadOverviewKpi(this.state.selectedEmployee);
        }
    }

    async refreshData() {
        if (this.state.selectedEmployee) {
            await this.loadOverviewKpi(this.state.selectedEmployee);
            this.notification.add("Data refreshed", { type: "info" });
        }
    }

    // ── Tab navigation ────────────────────────────────────────────
    changeTab(tab) {
        // Regular users are restricted to the Today Visit screen only
        if (!this.state.isManager && tab !== 'todayvisit') return;
        this.state.activeTab = tab;
    }

    // ── Accordion ─────────────────────────────────────────────────
    toggleAccordion(key) {
        this.state.accordion[key] = !this.state.accordion[key];
    }

    // ── Checklist ─────────────────────────────────────────────────
    toggleChecklistItem(id, checked) {
        const item = this.state.checklistItems.find(i => i.id === id);
        if (item) item.done = checked;
        this.state.checklistDone = this.state.checklistItems.filter(i => i.done).length;
    }

    // ── Retailer Orders tab ───────────────────────────────────────
    async loadRetailerOrders() {
        try {
            const empId = this.state.selectedEmployee;
            if (!empId) return;
            const today = new Date().toISOString().slice(0, 10);
            const firstDay = today.slice(0, 8) + '01';
            const userId = this.state.userId;

            const orders = await this.orm.searchRead(
                "sale.order",
                userId
                    ? [["user_id", "=", userId], ["date_order", ">=", firstDay + " 00:00:00"]]
                    : [["date_order", ">=", firstDay + " 00:00:00"]],
                ["id", "name", "partner_id", "amount_total", "state", "order_line", "date_order"],
                { limit: 500, order: "date_order desc" }
            );

            const byPartner = {};
            for (const o of orders) {
                const pid = o.partner_id ? o.partner_id[0] : 0;
                const pname = o.partner_id ? o.partner_id[1] : "Unknown";
                if (!byPartner[pid]) byPartner[pid] = { id: pid, name: pname, orders: [], total: 0, expanded: false };
                byPartner[pid].orders.push(o);
                byPartner[pid].total += o.amount_total || 0;
            }

            this.state.retailerOrders = Object.values(byPartner).sort((a, b) => b.total - a.total);
            this.state.retailerOrderStats = {
                retailers: Object.keys(byPartner).length,
                orders: orders.length,
                totalValue: orders.reduce((s, o) => s + (o.amount_total || 0), 0),
            };
        } catch (e) {
            console.error("loadRetailerOrders:", e);
            this.state.retailerOrders = [];
        }
    }

    toggleRetailerExpand(id) {
        const r = this.state.retailerOrders.find(x => x.id === id);
        if (r) r.expanded = !r.expanded;
    }

    async changeTabAndLoad(tab) {
        this.changeTab(tab);
        if (tab === 'retailer') {
            await this.loadRetailerOrders();
        }
    }

    // ── Analytics link ────────────────────────────────────────────
    openAnalytics() {
        this.changeTab('summary');
    }

    // ── Retailer Orders PDF Download ──────────────────────────────
    downloadRetailerPdf() {
        const stats = this.state.retailerOrderStats;
        const retailers = this.state.retailerOrders;
        const empName = this.state.details ? this.state.details.name : 'Employee';
        const today = new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });

        let tableRows = '';
        let grandTotal = 0;

        for (const retailer of retailers) {
            for (const order of (retailer.orders || [])) {
                const amt = order.amount_total || 0;
                grandTotal += amt;
                const stateLabel = order.state === 'sale' ? 'Confirmed' : order.state === 'draft' ? 'New' : (order.state || '-');
                const stateBg = order.state === 'sale' ? '#d1fae5' : order.state === 'draft' ? '#fef3c7' : '#f3f4f6';
                const stateColor = order.state === 'sale' ? '#059669' : order.state === 'draft' ? '#d97706' : '#6b7280';
                tableRows += `<tr>
                    <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;">${retailer.name || '-'}</td>
                    <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;color:#4361ee;font-weight:600;">${order.name || '-'}</td>
                    <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;">${order.order_line ? order.order_line.length : 0} items</td>
                    <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;text-align:right;font-weight:700;color:#059669;">Rs. ${(amt).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                    <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;text-align:center;">
                        <span style="background:${stateBg};color:${stateColor};padding:2px 10px;border-radius:20px;font-size:11px;font-weight:700;">${stateLabel}</span>
                    </td>
                </tr>`;
            }
        }

        const htmlContent = `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<title>Retailer Orders Report</title>
<style>
  body { font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 0; color: #1a1a2e; background: #fff; }
  .header { background: linear-gradient(135deg, #0d0d1f 0%, #1a1a3e 50%, #0f3460 100%); color: #fff; padding: 28px 36px; }
  .header h1 { margin: 0 0 4px; font-size: 22px; font-weight: 800; }
  .header p { margin: 0; opacity: 0.7; font-size: 13px; }
  .stats-bar { display: flex; gap: 0; border-bottom: 2px solid #f0f0f0; }
  .stat-box { flex: 1; padding: 16px 24px; border-right: 1px solid #f0f0f0; }
  .stat-box:last-child { border-right: none; }
  .stat-num { font-size: 24px; font-weight: 800; color: #4361ee; }
  .stat-lbl { font-size: 10px; font-weight: 700; color: #9ca3af; text-transform: uppercase; letter-spacing: 1px; margin-top: 2px; }
  .section-title { padding: 14px 24px; background: #f8fafc; font-size: 11px; font-weight: 800; color: #6b7280; text-transform: uppercase; letter-spacing: 1px; border-bottom: 1px solid #f0f0f0; }
  table { width: 100%; border-collapse: collapse; }
  thead { background: #f0f4f8; }
  th { padding: 10px 12px; text-align: left; font-size: 11px; font-weight: 800; color: #374151; text-transform: uppercase; letter-spacing: 0.5px; }
  th:last-child, td:last-child { text-align: center; }
  th:nth-child(4) { text-align: right; }
  .total-row { background: #f0f4ff; }
  .total-row td { padding: 12px; font-weight: 800; font-size: 14px; color: #059669; }
  .footer { padding: 16px 24px; background: #f8fafc; border-top: 2px solid #f0f0f0; font-size: 11px; color: #9ca3af; display: flex; justify-content: space-between; }
  @media print { body { -webkit-print-color-adjust: exact; print-color-adjust: exact; } .no-print { display: none; } }
</style>
</head>
<body>
<div class="header">
  <h1>📊 Retailer Orders Report</h1>
  <p>Employee: <strong>${empName}</strong> &nbsp;|&nbsp; Generated: <strong>${today}</strong></p>
</div>
<div class="stats-bar">
  <div class="stat-box">
    <div class="stat-num">${stats.retailers}</div>
    <div class="stat-lbl">Retailers</div>
  </div>
  <div class="stat-box">
    <div class="stat-num">${stats.orders}</div>
    <div class="stat-lbl">Orders</div>
  </div>
  <div class="stat-box">
    <div class="stat-num" style="color:#059669;">Rs. ${(stats.totalValue || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</div>
    <div class="stat-lbl">Total Value</div>
  </div>
</div>
<div class="section-title">Retailer-Wise Orders</div>
<table>
  <thead>
    <tr>
      <th>Retailer</th>
      <th>Order #</th>
      <th>Items</th>
      <th style="text-align:right;">Amount</th>
      <th>Status</th>
    </tr>
  </thead>
  <tbody>
    ${tableRows || '<tr><td colspan="5" style="text-align:center;padding:24px;color:#9ca3af;">No orders found</td></tr>'}
    <tr class="total-row">
      <td colspan="3" style="padding:12px;font-weight:800;font-size:13px;">GRAND TOTAL</td>
      <td style="text-align:right;padding:12px;">Rs. ${grandTotal.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
      <td></td>
    </tr>
  </tbody>
</table>
<div class="footer">
  <span>Employee 360 — Retailer Orders Report</span>
  <span>Printed: ${today}</span>
</div>
</body>
</html>`;

        const win = window.open('', '_blank');
        if (win) {
            win.document.write(htmlContent);
            win.document.close();
            setTimeout(() => win.print(), 600);
        } else {
            // fallback: create a download link
            const blob = new Blob([htmlContent], { type: 'text/html' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `retailer_orders_${today.replace(/ /g, '_')}.html`;
            a.click();
            URL.revokeObjectURL(url);
        }
    }

    // ── Retailer Orders WhatsApp Share ─────────────────────────────
    shareRetailerOnWhatsApp() {
        const stats = this.state.retailerOrderStats;
        const empName = this.state.details ? this.state.details.name : 'Employee';
        const today = new Date().toLocaleDateString('en-IN');

        let message = `*📊 Retailer Orders Report*\n`;
        message += `Employee: *${empName}*\n`;
        message += `Date: ${today}\n\n`;
        message += `📈 *Summary*\n`;
        message += `• Retailers: ${stats.retailers}\n`;
        message += `• Orders: ${stats.orders}\n`;
        message += `• Total Value: Rs. ${(stats.totalValue || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}\n\n`;

        for (const retailer of (this.state.retailerOrders || []).slice(0, 5)) {
            message += `🏪 *${retailer.name}*\n`;
            message += `   ${retailer.orders.length} order(s) — Rs. ${(retailer.total || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}\n`;
        }

        if ((this.state.retailerOrders || []).length > 5) {
            message += `... and ${this.state.retailerOrders.length - 5} more retailers\n`;
        }

        const encoded = encodeURIComponent(message);
        window.open(`https://wa.me/?text=${encoded}`, '_blank');
    }
}

EmployeeComponent.components = {
    InvoiceList,
    PJPList,
    OrdersList,
    ExpenseList,
    AttendanceList,
    VisitList,
    TodayVisit,
    LocationMapCard,
    DashboardReport,
};
EmployeeComponent.template = "employee_dashboard.EmployeeComponent";

registry.category("actions").add("employee_dashboard_component", EmployeeComponent);
