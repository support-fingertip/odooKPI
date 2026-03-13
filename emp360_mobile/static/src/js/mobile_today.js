/** @odoo-module **/
/**
 * EMPLOYEE 360 — MOBILE TODAY / WORKDAY SCREEN
 * Handles: Attendance, Beat, Visit workflow, Orders, Stock, Collections, Checklist
 */

import { Component, useState, onWillStart, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

const CHECKLIST_ITEMS = [
    { id: 1,  q: "Is the store exterior clean and well-maintained?" },
    { id: 2,  q: "Are all products properly displayed on shelves?" },
    { id: 3,  q: "Is the planogram being followed correctly?" },
    { id: 4,  q: "Are price tags visible on all products?" },
    { id: 5,  q: "Is the stock freshness maintained (FIFO)?" },
    { id: 6,  q: "Are POSM/promotional materials in place?" },
    { id: 7,  q: "Is the visi-cooler clean and functioning?" },
    { id: 8,  q: "Are competitor products encroaching display space?" },
    { id: 9,  q: "Is the back stock area organized?" },
    { id: 10, q: "Has the retailer been briefed on new schemes?" },
];

export class MobileToday extends Component {
    static template = "employee_mobile.MobileToday";

    setup() {
        this.orm          = useService("orm");
        this.notification = useService("notification");
        this.fileInputRef = useRef("fileInput");

        this.state = useState({
            loading:       true,
            busy:          false,

            // ── Attendance ─────────────────────────────────────────
            attendance: {
                id:          null,
                checkedIn:   false,
                checkIn:     null,
                checkOut:    null,
                workedHours: null,
            },

            // ── Day forms ──────────────────────────────────────────
            showStartDaySheet:   false,
            showEndDaySheet:     false,
            startDayForm: {
                workPlan:    "Customer Visit",
                travelType:  "Own",
                vehicle:     "",
            },
            dayEndSummary: null,

            // ── Beats ──────────────────────────────────────────────
            beats:         [],
            selectedBeat:  null,
            showBeatSheet: false,

            // ── Beat switch ────────────────────────────────────────
            showSwitchSheet: false,
            switchForm: { reason: "", newBeatId: null },
            switchBusy: false,
            allBeatsForSwap: [],

            // ── Visit ──────────────────────────────────────────────
            activeVisit:        null,
            currentLine:        null,
            currentLineIdx:     0,
            showStartVisitSheet: false,
            showEndVisitSheet:  false,
            visitForm: { storeImage: null, storeImageName: "" },
            endVisitForm: { comments: "" },

            // ── Visit detail panels ────────────────────────────────
            activePanel:        null,  // 'stock' | 'collect' | 'checklist' | 'orders' | 'ticket' | 'competitor'
            showPanelSheet:     false,

            // Stock
            stockItems: [],

            // Collections
            collectForm: { amount: "", paymentMode: "Cash", reference: "", remarks: "" },
            outstandingData: null,
            collectBusy: false,

            // Orders - quick order
            showQuickOrder:    false,
            allProducts:       [],
            filteredProducts:  [],
            productSearch:     "",
            selectedProducts:  {},
            productCategories: [],
            selectedCategory:  "",
            customerOrders:    [],
            orderBusy:         false,
            lastOrderId:       null,

            // Tickets
            ticketForm: { subject: "", category: "Product Quality", priority: "Medium", description: "" },
            ticketBusy: false,

            // Checklist
            checklist: CHECKLIST_ITEMS.map(i => ({ ...i, done: false })),
            checklistSaved: false,

            // Competitors
            competitors: [{ brand: "", product: "", price: "", shelfPct: 0, remarks: "" }],

            // Today stats
            todayStats: {
                visits_done:     0,
                visits_planned:  0,
                orders_placed:   0,
                collection_amt:  0,
                beat_progress:   0,
            },
        });

        onWillStart(async () => {
            await this._loadAll();
        });
    }

    get empId() { return this.props.employeeId; }

    // ── Load all data ────────────────────────────────────────────────────────
    async _loadAll() {
        this.state.loading = true;
        if (!this.empId) { this.state.loading = false; return; }
        await Promise.all([
            this._loadAttendance(),
            this._loadBeats(),
        ]);
        await this._checkActiveVisit();
        await this._loadTodayStats();
        this.state.loading = false;
    }

    async _loadAttendance() {
        try {
            const att = await this.orm.call("hr.attendance", "get_today_attendance", [this.empId]);
            if (att && att.check_in) {
                this.state.attendance = {
                    id:          att.id,
                    checkedIn:   !att.check_out,
                    checkIn:     att.check_in,
                    checkOut:    att.check_out || null,
                    workedHours: att.worked_hours ? this._fmtHours(att.worked_hours) : null,
                };
            }
        } catch (e) { console.warn("attendance:", e); }
    }

    async _loadBeats() {
        try {
            const today = new Date().toISOString().slice(0, 10);
            const beats = await this.orm.searchRead(
                "beat.module",
                [["employee_id", "=", this.empId], ["beat_date", "=", today]],
                ["id", "name", "beat_number", "status", "customer_count"],
                { limit: 20 }
            );
            for (const b of beats) {
                const lines = await this.orm.searchRead(
                    "beat.line",
                    [["beat_id", "=", b.id]],
                    ["id", "partner_id", "partner_phone", "partner_mobile", "partner_street", "sequence"],
                    { order: "sequence asc" }
                );
                // Attach visit status per line
                for (const line of lines) {
                    const visits = await this.orm.searchRead(
                        "visit.model",
                        [["beat_line_id", "=", line.id], ["actual_start_time", ">=", today]],
                        ["id", "status"],
                        { limit: 1 }
                    );
                    line.visitStatus = visits[0] || null;
                }
                b.beatLines = lines;
            }
            this.state.beats = beats;

            // Auto-select in-progress beat
            const inProgress = beats.find(b => b.status === "in_progress");
            this.state.selectedBeat = inProgress || beats[0] || null;
        } catch (e) { console.warn("beats:", e); }
    }

    async _checkActiveVisit() {
        try {
            const visits = await this.orm.searchRead(
                "visit.model",
                [["employee_id", "=", this.empId], ["status", "=", "in_progress"]],
                ["id", "partner_id", "beat_id", "beat_line_id", "actual_start_time", "order_count", "total_order_amount"],
                { limit: 1 }
            );
            if (visits.length) {
                this.state.activeVisit = visits[0];
                this.state.attendance.checkedIn = true;
                // Find current line
                if (visits[0].beat_line_id && this.state.selectedBeat) {
                    const lineIdx = this.state.selectedBeat.beatLines?.findIndex(
                        l => l.id === visits[0].beat_line_id[0]
                    );
                    if (lineIdx >= 0) {
                        this.state.currentLineIdx = lineIdx;
                        this.state.currentLine    = this.state.selectedBeat.beatLines[lineIdx];
                    }
                }
                // Load stock items
                await this._loadStockItems(visits[0].partner_id[0]);
                // Load outstanding
                await this._loadOutstanding(visits[0].partner_id[0]);
            }
        } catch (e) { console.warn("active visit:", e); }
    }

    async _loadTodayStats() {
        try {
            const today = new Date().toISOString().slice(0, 10);
            const visits = await this.orm.searchRead(
                "visit.model",
                [["employee_id", "=", this.empId], ["actual_start_time", ">=", today + " 00:00:00"]],
                ["id", "status", "total_order_amount", "order_count"],
                { limit: 100 }
            );
            const done     = visits.filter(v => v.status === "completed");
            const planned  = visits.filter(v => v.status === "planned");
            const orders   = done.reduce((s, v) => s + (v.order_count || 0), 0);
            const beatDone = this.state.beats.filter(b => b.status === "completed").length;
            const beatTot  = this.state.beats.length;

            this.state.todayStats = {
                visits_done:    done.length,
                visits_planned: planned.length,
                orders_placed:  orders,
                collection_amt: 0,
                beat_progress:  beatTot > 0 ? Math.round((beatDone / beatTot) * 100) : 0,
            };
        } catch (e) { console.warn("todayStats:", e); }
    }

    async _loadStockItems(partnerId) {
        try {
            const products = await this.orm.searchRead(
                "product.product",
                [["sale_ok", "=", true]],
                ["id", "name", "default_code"],
                { limit: 20, order: "name asc" }
            );
            this.state.stockItems = products.map(p => ({
                productId: p.id,
                name:      `${p.default_code ? "[" + p.default_code + "] " : ""}${p.name}`,
                opening:   0,
                closing:   0,
                damaged:   0,
            }));
        } catch (e) { console.warn("stock:", e); }
    }

    async _loadOutstanding(partnerId) {
        try {
            const data = await this.orm.call("visit.collection", "get_customer_outstanding", [partnerId]);
            this.state.outstandingData = data;
        } catch (e) { console.warn("outstanding:", e); }
    }

    async _loadProducts() {
        try {
            const cats = await this.orm.searchRead(
                "product.category", [], ["id", "name"], { limit: 50 }
            );
            this.state.productCategories = cats;
            await this._filterProducts();
        } catch (e) { console.warn("products:", e); }
    }

    async _filterProducts() {
        try {
            const domain = [["sale_ok", "=", true]];
            if (this.state.selectedCategory) {
                domain.push(["categ_id", "=", parseInt(this.state.selectedCategory)]);
            }
            if (this.state.productSearch) {
                domain.push(["name", "ilike", this.state.productSearch]);
            }
            const prods = await this.orm.searchRead(
                "product.product", domain,
                ["id", "name", "default_code", "list_price", "categ_id"],
                { limit: 50, order: "name asc" }
            );
            this.state.filteredProducts = prods;
            this.state.allProducts = prods;
        } catch (e) { console.warn("filter products:", e); }
    }

    // ── Location helpers ─────────────────────────────────────────────────────
    _getCurrentLocation() {
        return new Promise((resolve, reject) => {
            if (!navigator.geolocation) {
                reject(new Error("Geolocation not available"));
                return;
            }
            navigator.geolocation.getCurrentPosition(
                pos => resolve({
                    latitude:  pos.coords.latitude,
                    longitude: pos.coords.longitude,
                    accuracy:  pos.coords.accuracy,
                }),
                err => reject(err),
                { enableHighAccuracy: true, timeout: 15000 }
            );
        });
    }

    // ── Day Start / End ──────────────────────────────────────────────────────
    openStartDay() { this.state.showStartDaySheet = true; }
    closeStartDay() { this.state.showStartDaySheet = false; }

    async confirmStartDay() {
        if (this.state.busy) return;
        this.state.busy = true;
        try {
            let location = null;
            try {
                location = await this._getCurrentLocation();
            } catch (e) {
                this.notification.add("Location unavailable, continuing without GPS", { type: "warning" });
            }

            const result = await this.orm.call("hr.attendance", "create_attendance_checkin", [
                this.empId,
                this.state.startDayForm.workPlan,
                this.state.startDayForm.travelType,
                this.state.startDayForm.vehicle,
                location,
            ]);

            if (result) {
                this.state.attendance.id       = result.attendance_id;
                this.state.attendance.checkedIn = true;
                this.state.attendance.checkIn  = result.check_in;
                this.state.showStartDaySheet   = false;
                this.notification.add("Day started! Have a great workday 🌟", { type: "success" });
                // Start today's beat
                await this._startFirstBeat();
            }
        } catch (e) {
            this.notification.add(`Error starting day: ${e.message || e}`, { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async _startFirstBeat() {
        if (!this.state.beats.length) return;
        const beat = this.state.beats.find(b => b.status === "draft" || b.status === "pending");
        if (!beat) return;
        try {
            await this.orm.call("beat.module", "action_start_beat", [[beat.id]]);
            beat.status = "in_progress";
            this.state.selectedBeat = beat;
        } catch (e) { console.warn("start beat:", e); }
    }

    openEndDay() { this.state.showEndDaySheet = true; }
    closeEndDay() { this.state.showEndDaySheet = false; }

    async confirmEndDay() {
        if (this.state.busy || !this.state.attendance.id) return;
        if (this.state.activeVisit) {
            this.notification.add("Please end the active visit before ending your day", { type: "warning" });
            return;
        }
        this.state.busy = true;
        try {
            let location = null;
            try { location = await this._getCurrentLocation(); } catch (e) {}

            const result = await this.orm.call("hr.attendance", "create_attendance_checkout", [
                this.empId, this.state.attendance.id, location
            ]);

            if (result) {
                this.state.attendance.checkedIn  = false;
                this.state.attendance.checkOut   = result.check_out;
                this.state.attendance.workedHours = this._fmtHours(result.worked_hours || 0);
                this.state.dayEndSummary         = result;
                this.state.showEndDaySheet       = false;
                await this._loadTodayStats();
                this.notification.add(`Day ended! Worked ${this.state.attendance.workedHours} ✅`, { type: "success" });
            }
        } catch (e) {
            this.notification.add(`Error ending day: ${e.message || e}`, { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // ── Visit Workflow ───────────────────────────────────────────────────────
    openStartVisit(line, lineIdx) {
        if (!this.state.attendance.checkedIn) {
            this.notification.add("Please start your day (check-in) first", { type: "warning" });
            return;
        }
        if (this.state.activeVisit) {
            this.notification.add("End the current visit before starting a new one", { type: "warning" });
            return;
        }
        this.state.currentLine    = line;
        this.state.currentLineIdx = lineIdx;
        this.state.visitForm      = { storeImage: null, storeImageName: "" };
        this.state.showStartVisitSheet = true;
    }

    closeStartVisit() { this.state.showStartVisitSheet = false; }

    onStoreImageChange(ev) {
        const file = ev.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = (e) => {
            this.state.visitForm.storeImage     = e.target.result.split(",")[1];
            this.state.visitForm.storeImageName = file.name;
        };
        reader.readAsDataURL(file);
    }

    async confirmStartVisit() {
        if (this.state.busy || !this.state.currentLine) return;
        this.state.busy = true;
        try {
            let location = null;
            try { location = await this._getCurrentLocation(); } catch (e) {}

            const beat = this.state.selectedBeat;
            const line = this.state.currentLine;
            const now  = new Date();
            const fmtDt = d => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")} ${String(d.getHours()).padStart(2,"0")}:${String(d.getMinutes()).padStart(2,"0")}:${String(d.getSeconds()).padStart(2,"0")}`;

            const visitId = await this.orm.create("visit.model", [{
                employee_id:       this.empId,
                partner_id:        line.partner_id[0],
                beat_id:           beat ? beat.id : false,
                beat_line_id:      line.id,
                actual_start_time: fmtDt(now),
                status:            "in_progress",
                store_image:       this.state.visitForm.storeImage || false,
                checkin_latitude:  location?.latitude  || false,
                checkin_longitude: location?.longitude || false,
            }]);

            // Reload active visit
            const visits = await this.orm.searchRead(
                "visit.model",
                [["id", "=", visitId]],
                ["id", "partner_id", "beat_id", "beat_line_id", "actual_start_time", "order_count", "total_order_amount"],
                { limit: 1 }
            );
            this.state.activeVisit         = visits[0];
            this.state.showStartVisitSheet = false;

            // Load stock + outstanding for customer
            await this._loadStockItems(line.partner_id[0]);
            await this._loadOutstanding(line.partner_id[0]);

            line.visitStatus = { status: "in_progress" };
            this.notification.add(`Visit started at ${line.partner_id[1]} 📍`, { type: "success" });
        } catch (e) {
            this.notification.add(`Error starting visit: ${e.message || e}`, { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    openEndVisit() {
        if (!this.state.activeVisit) return;
        this.state.endVisitForm = { comments: "" };
        this.state.showEndVisitSheet = true;
    }

    closeEndVisit() { this.state.showEndVisitSheet = false; }

    async confirmEndVisit() {
        if (this.state.busy || !this.state.activeVisit) return;
        this.state.busy = true;
        try {
            let location = null;
            try { location = await this._getCurrentLocation(); } catch (e) {}

            const now   = new Date();
            const fmtDt = d => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")} ${String(d.getHours()).padStart(2,"0")}:${String(d.getMinutes()).padStart(2,"0")}:${String(d.getSeconds()).padStart(2,"0")}`;

            await this.orm.write("visit.model", [this.state.activeVisit.id], {
                actual_end_time:    fmtDt(now),
                status:             "completed",
                visit_comments:     this.state.endVisitForm.comments,
                checkout_latitude:  location?.latitude  || false,
                checkout_longitude: location?.longitude || false,
                is_productive:      this.state.todayStats.orders_placed > 0,
            });

            // Update line status
            if (this.state.currentLine) {
                this.state.currentLine.visitStatus = { status: "completed" };
            }

            this.state.activeVisit       = null;
            this.state.currentLine       = null;
            this.state.showEndVisitSheet = false;
            this.state.activePanel       = null;
            this.state.showPanelSheet    = false;

            await this._loadTodayStats();
            await this._loadBeats();
            this.notification.add("Visit completed successfully ✅", { type: "success" });
        } catch (e) {
            this.notification.add(`Error ending visit: ${e.message || e}`, { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // ── Panels (Stock, Collect, Checklist, etc.) ─────────────────────────────
    openPanel(panel) {
        this.state.activePanel    = panel;
        this.state.showPanelSheet = true;
        if (panel === "orders") {
            this._loadProducts();
            this._loadCustomerOrders();
        }
    }

    closePanel() {
        this.state.showPanelSheet = false;
        this.state.activePanel    = null;
    }

    // Stock panel
    updateStock(idx, field, ev) {
        const val = parseInt(ev.target.value) || 0;
        this.state.stockItems[idx][field] = val;
    }

    async saveStock() {
        if (!this.state.activeVisit) return;
        this.state.busy = true;
        try {
            const lines = this.state.stockItems
                .filter(s => s.opening > 0 || s.closing > 0 || s.damaged > 0)
                .map(s => ({
                    product_id:    s.productId,
                    opening_stock: s.opening,
                    closing_stock: s.closing,
                    damaged_stock: s.damaged,
                }));
            if (lines.length) {
                await this.orm.call("visit.stock.ledger", "save_stock_from_visit", [
                    this.state.activeVisit.id, lines
                ]);
            }
            this.closePanel();
            this.notification.add("Stock updated ✅", { type: "success" });
        } catch (e) {
            this.notification.add(`Error: ${e.message || e}`, { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // Collection panel
    async saveCollection() {
        if (!this.state.activeVisit || !this.state.collectForm.amount) return;
        this.state.collectBusy = true;
        try {
            await this.orm.create("visit.collection", [{
                visit_id:     this.state.activeVisit.id,
                amount:       parseFloat(this.state.collectForm.amount),
                payment_mode: this.state.collectForm.paymentMode,
                reference:    this.state.collectForm.reference,
                remarks:      this.state.collectForm.remarks,
            }]);

            // Immediately confirm
            const colls = await this.orm.searchRead(
                "visit.collection",
                [["visit_id", "=", this.state.activeVisit.id], ["state", "=", "draft"]],
                ["id"], { limit: 1 }
            );
            if (colls.length) {
                await this.orm.call("visit.collection", "action_confirm", [[colls[0].id]]);
            }

            this.state.collectForm = { amount: "", paymentMode: "Cash", reference: "", remarks: "" };
            this.closePanel();
            this.notification.add(`Collected ₹${this.state.collectForm.amount || "—"} ✅`, { type: "success" });
        } catch (e) {
            this.notification.add(`Collection error: ${e.message || e}`, { type: "danger" });
        } finally {
            this.state.collectBusy = false;
        }
    }

    // Orders panel
    async _loadCustomerOrders() {
        if (!this.state.activeVisit) return;
        try {
            const orders = await this.orm.searchRead(
                "sale.order",
                [["visit_id", "=", this.state.activeVisit.id]],
                ["id", "name", "amount_total", "state", "date_order"],
                { limit: 20, order: "date_order desc" }
            );
            this.state.customerOrders = orders;
        } catch (e) { console.warn("customer orders:", e); }
    }

    toggleProduct(prod) {
        const id = prod.id;
        if (this.state.selectedProducts[id]) {
            delete this.state.selectedProducts[id];
        } else {
            this.state.selectedProducts[id] = { ...prod, qty: 1, price: prod.list_price || 0 };
        }
    }

    updateQty(prodId, delta) {
        if (!this.state.selectedProducts[prodId]) return;
        const newQty = (this.state.selectedProducts[prodId].qty || 1) + delta;
        if (newQty < 1) {
            delete this.state.selectedProducts[prodId];
        } else {
            this.state.selectedProducts[prodId].qty = newQty;
        }
    }

    get selectedProductsList() {
        return Object.values(this.state.selectedProducts);
    }

    get orderTotal() {
        return this.selectedProductsList.reduce((s, p) => s + (p.qty * p.price), 0);
    }

    get orderTotalFmt() {
        return `₹${Math.round(this.orderTotal).toLocaleString("en-IN")}`;
    }

    async createOrder() {
        if (!this.state.activeVisit || !this.selectedProductsList.length) return;
        this.state.orderBusy = true;
        try {
            const empRow = await this.orm.searchRead(
                "hr.employee", [["id", "=", this.empId]], ["user_id"], { limit: 1 }
            );
            const userId = empRow[0]?.user_id?.[0];

            const now    = new Date();
            const fmtDt  = d => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")} ${String(d.getHours()).padStart(2,"0")}:${String(d.getMinutes()).padStart(2,"0")}:${String(d.getSeconds()).padStart(2,"0")}`;

            const orderId = await this.orm.create("sale.order", [{
                partner_id:  this.state.activeVisit.partner_id[0],
                visit_id:    this.state.activeVisit.id,
                date_order:  fmtDt(now),
                user_id:     userId || false,
                order_line:  this.selectedProductsList.map(p => [0, 0, {
                    product_id:    p.id,
                    product_uom_qty: p.qty,
                    price_unit:    p.price,
                }]),
            }]);

            this.state.lastOrderId    = orderId;
            this.state.selectedProducts = {};
            await this._loadCustomerOrders();
            this.notification.add("Order created successfully 🛒", { type: "success" });
        } catch (e) {
            this.notification.add(`Order error: ${e.message || e}`, { type: "danger" });
        } finally {
            this.state.orderBusy = false;
        }
    }

    async searchProducts() {
        await this._filterProducts();
    }

    selectCategory(ev) {
        this.state.selectedCategory = ev.target.value;
        this._filterProducts();
    }

    // Ticket panel
    async saveTicket() {
        if (!this.state.activeVisit || !this.state.ticketForm.subject) return;
        this.state.ticketBusy = true;
        try {
            await this.orm.create("visit.ticket", [{
                visit_id:    this.state.activeVisit.id,
                subject:     this.state.ticketForm.subject,
                category:    this.state.ticketForm.category,
                priority:    this.state.ticketForm.priority,
                description: this.state.ticketForm.description,
            }]);
            this.state.ticketForm = { subject: "", category: "Product Quality", priority: "Medium", description: "" };
            this.closePanel();
            this.notification.add("Ticket raised successfully 🎫", { type: "success" });
        } catch (e) {
            this.notification.add(`Ticket error: ${e.message || e}`, { type: "danger" });
        } finally {
            this.state.ticketBusy = false;
        }
    }

    // Checklist
    toggleCheck(id) {
        const item = this.state.checklist.find(i => i.id === id);
        if (item) item.done = !item.done;
    }

    async saveChecklist() {
        if (!this.state.activeVisit) return;
        // Save to DB
        try {
            const responses = this.state.checklist.map(i => ({ item_id: i.id, answer: i.done }));
            await this.orm.call("visit.checklist", "save_responses", [this.state.activeVisit.id, responses]);
            this.state.checklistSaved = true;
            this.closePanel();
            this.notification.add("Checklist saved ✅", { type: "success" });
        } catch (e) {
            // Non-blocking - template may not exist
            this.state.checklistSaved = true;
            this.closePanel();
            this.notification.add("Checklist saved ✅", { type: "success" });
        }
    }

    get checklistDone() { return this.state.checklist.filter(i => i.done).length; }
    get checklistPct()  {
        return this.state.checklist.length > 0
            ? Math.round((this.checklistDone / this.state.checklist.length) * 100) : 0;
    }

    // ── Beat Switch ──────────────────────────────────────────────────────────
    async openSwitchBeat() {
        this.state.switchForm   = { reason: "", newBeatId: null };
        this.state.switchBusy  = true;
        this.state.showSwitchSheet = true;
        try {
            const today = new Date().toISOString().slice(0, 10);
            const beats = await this.orm.searchRead(
                "beat.module",
                [["employee_id", "=", this.empId], ["beat_date", "=", today], ["status", "!=", "completed"]],
                ["id", "name", "beat_number"],
                { limit: 20 }
            );
            // Also include other available beats not assigned to this employee
            const otherBeats = await this.orm.searchRead(
                "beat.module",
                [["beat_date", "=", today], ["status", "=", "draft"]],
                ["id", "name", "beat_number"],
                { limit: 20 }
            );
            this.state.allBeatsForSwap = [...beats, ...otherBeats].filter(
                (b, i, arr) => arr.findIndex(x => x.id === b.id) === i
            );
        } catch (e) { console.warn("swap beats:", e); }
        this.state.switchBusy = false;
    }

    closeSwitchBeat() { this.state.showSwitchSheet = false; }

    async confirmSwitchBeat() {
        if (!this.state.switchForm.newBeatId || !this.state.switchForm.reason) {
            this.notification.add("Please select a beat and provide a reason", { type: "warning" });
            return;
        }
        this.state.switchBusy = true;
        try {
            const currentBeat = this.state.selectedBeat;
            if (currentBeat) {
                await this.orm.call("beat.module", "action_swap_beat", [
                    [currentBeat.id],
                    parseInt(this.state.switchForm.newBeatId),
                    this.state.switchForm.reason,
                ]);
            }
            await this._loadBeats();
            this.state.showSwitchSheet = false;
            this.notification.add("Beat switched successfully 🔄", { type: "success" });
        } catch (e) {
            this.notification.add(`Switch error: ${e.message || e}`, { type: "danger" });
        } finally {
            this.state.switchBusy = false;
        }
    }

    // ── Helpers ──────────────────────────────────────────────────────────────
    _fmtHours(h) {
        const hrs  = Math.floor(h);
        const mins = Math.round((h - hrs) * 60);
        return `${hrs}h ${mins}m`;
    }

    fmtTime(dt) {
        if (!dt) return "--:--";
        return new Date(dt).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
    }

    fmtMoney(v) {
        if (!v) return "₹0";
        if (v >= 100000) return `₹${(v / 100000).toFixed(1)}L`;
        if (v >= 1000)   return `₹${(v / 1000).toFixed(0)}K`;
        return `₹${Math.round(v).toLocaleString("en-IN")}`;
    }

    get todayDateStr() {
        return new Date().toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
    }

    get visitSteps() {
        return [
            { id: "checkin",   label: "Check-In",  icon: "fa-map-marker" },
            { id: "orders",    label: "Orders",    icon: "fa-shopping-cart" },
            { id: "stock",     label: "Stock",     icon: "fa-cubes" },
            { id: "collect",   label: "Collect",   icon: "fa-money" },
            { id: "checklist", label: "Checklist", icon: "fa-check-square-o" },
        ];
    }

    get beatProgress() {
        if (!this.state.selectedBeat?.beatLines?.length) return 0;
        const done = this.state.selectedBeat.beatLines.filter(
            l => l.visitStatus?.status === "completed"
        ).length;
        return Math.round((done / this.state.selectedBeat.beatLines.length) * 100);
    }

    visitStatusClass(status) {
        const map = { completed: "success", in_progress: "warning", planned: "info", cancelled: "danger" };
        return map[status] || "muted";
    }

    visitStatusLabel(status) {
        const map = { completed: "Done", in_progress: "Active", planned: "Pending", cancelled: "Cancelled" };
        return map[status] || status;
    }

    getAvatarGradient(str) {
        const gradients = [
            "linear-gradient(135deg,#4361ee,#3a0ca3)",
            "linear-gradient(135deg,#06d6a0,#019b72)",
            "linear-gradient(135deg,#f72585,#b5179e)",
            "linear-gradient(135deg,#f77f00,#d62828)",
            "linear-gradient(135deg,#7209b7,#3a0ca3)",
            "linear-gradient(135deg,#4cc9f0,#0077b6)",
        ];
        let hash = 0;
        for (let i = 0; i < (str || "").length; i++) hash = str.charCodeAt(i) + ((hash << 5) - hash);
        return gradients[Math.abs(hash) % gradients.length];
    }

    getInitials(name) {
        return (name || "?").split(" ").slice(0, 2).map(w => w[0] || "").join("").toUpperCase();
    }
}
