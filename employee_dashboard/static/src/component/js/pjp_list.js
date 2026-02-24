/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class PJPList extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            loading: true,
            beats: [],
            selectedBeatId: false,
            existingBeatLineIds: [],
            showCustomerSelection: false,
            showCalendarSelection: false,
            showCustomerList: false,
            showCreatePJPModal: false,
            beatReadonly: false,
            selectedCustomers: [],
            customerSearchText: "",
            searchByArea: "",
            searchByCity: "",
            searchByCategory: "",
            filteredCustomers: [],
            allCustomers: [],
            availableBeats: [],
            draggedBeat: null,
            
            currentMonth: new Date().getMonth(),
            currentYear: new Date().getFullYear(),
            calendarDates: [],
            beatsByDate: {},
            
         
            beatSearchText: "",
            filteredBeats: [],

            rotationFrequency: 1,

            createPJPForm: {
                startDate: "",
                endDate: "",
            },

            cloneBeatForm: {
                show: false,
                selectedBeatId: null,
                newBeatName: "",
            },
        });

        onWillStart(async () => {
            await this.loadPJP();
        });
    }

    
    onRotationFrequencyChange(ev) {
        const value = parseInt(ev.target.value);
        if (value > 0) {
            this.state.rotationFrequency = value;
        }
        this.generateCalendar();
    }

    async rotateBeats() {
        if (!this.props.employeeId) {
            this.notification.add("Please select an employee first", { type: "warning" });
            return;
        }

        if (this.state.rotationFrequency < 1) {
            this.notification.add("Please enter valid rotation frequency (minimum 1)", { type: "warning" });
            return;
        }

        const beatCount = this.state.beats.length;
        if (this.state.rotationFrequency < beatCount) {
            this.notification.add(
                `Rotation frequency (${this.state.rotationFrequency}) must be at least equal to number of beats (${beatCount}). Please increase the rotation frequency to ${beatCount} or more.`, 
                { type: "warning" }
            );
            this.state.rotationFrequency = beatCount;
            return;
        }

        try {
            const result = await this.orm.call(
                "hr.employee",
                "rotate_beats_in_month",
                [this.props.employeeId],
                {
                    month: this.state.currentMonth + 1,
                    year: this.state.currentYear,
                    rotation_frequency: this.state.rotationFrequency,
                }
            );

            if (result.success) {
                this.notification.add(result.message, { type: "success" });
                await this.loadPJP();
                await this.loadCalendarData();
            } else {
                this.notification.add(result.message || "Failed to rotate beats", { type: "danger" });
            }
        } catch (error) {
            console.error("Error rotating beats:", error);
            this.notification.add("Failed to rotate beats: " + error.message, { type: "danger" });
        }
    }

    
    onBeatSearchChange(ev) {
        this.state.beatSearchText = ev.target.value.toLowerCase();
        this.filterBeats();
    }

    filterBeats() {
        if (!this.state.beatSearchText) {
            this.state.filteredBeats = [...this.state.beats];
        } else {
            this.state.filteredBeats = this.state.beats.filter(beat => 
                beat.name.toLowerCase().includes(this.state.beatSearchText) ||
                (beat.beat_number && beat.beat_number.toLowerCase().includes(this.state.beatSearchText))
            );
        }
    }

    generateCalendar() {
        const year = this.state.currentYear;
        const month = this.state.currentMonth;
        
        const firstDay = new Date(year, month, 1);
        const lastDay = new Date(year, month + 1, 0);
        const daysInMonth = lastDay.getDate();
        const startDayOfWeek = firstDay.getDay();
        
        const dates = [];
        
        
        const prevMonthLastDay = new Date(year, month, 0).getDate();
        for (let i = startDayOfWeek - 1; i >= 0; i--) {
            dates.push({
                date: prevMonthLastDay - i,
                month: month - 1,
                year: month === 0 ? year - 1 : year,
                isCurrentMonth: false,
                fullDate: this.formatDate(new Date(month === 0 ? year - 1 : year, month === 0 ? 11 : month - 1, prevMonthLastDay - i))
            });
        }
        
        for (let date = 1; date <= daysInMonth; date++) {
            const currentDate = new Date(year, month, date);
            dates.push({
                date: date,
                month: month,
                year: year,
                isCurrentMonth: true,
                isWeekend: currentDate.getDay() === 0 || currentDate.getDay() === 6,
                isToday: this.isToday(currentDate),
                fullDate: this.formatDate(currentDate),
                isInRotationCycle: this.isDateInRotationCycle(currentDate)
            });
        }
        
       
        const remainingDays = 42 - dates.length;
        for (let date = 1; date <= remainingDays; date++) {
            dates.push({
                date: date,
                month: month + 1,
                year: month === 11 ? year + 1 : year,
                isCurrentMonth: false,
                fullDate: this.formatDate(new Date(month === 11 ? year + 1 : year, month === 11 ? 0 : month + 1, date))
            });
        }
        
        this.state.calendarDates = dates;
    }

    isDateInRotationCycle(date) {
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        
        const checkDate = new Date(date);
        checkDate.setHours(0, 0, 0, 0);
        
        
        const viewingMonthFirstDay = new Date(this.state.currentYear, this.state.currentMonth, 1);
        viewingMonthFirstDay.setHours(0, 0, 0, 0);
        
        const currentMonthFirstDay = new Date(today.getFullYear(), today.getMonth(), 1);
        currentMonthFirstDay.setHours(0, 0, 0, 0);
        
        if (viewingMonthFirstDay < currentMonthFirstDay) {
            return false;
        }
        let referenceDate;
        
        if (viewingMonthFirstDay.getTime() === currentMonthFirstDay.getTime()) {
            referenceDate = today;
        } else {
            referenceDate = viewingMonthFirstDay;
        }
        if (checkDate < referenceDate) {
            return false;
        }
        const timeDiff = checkDate.getTime() - referenceDate.getTime();
        const daysDiff = Math.floor(timeDiff / (1000 * 60 * 60 * 24));

        return daysDiff >= 0 && daysDiff < this.state.rotationFrequency;
    }

    formatDate(date) {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    }

    isToday(date) {
        const today = new Date();
        return date.getDate() === today.getDate() &&
               date.getMonth() === today.getMonth() &&
               date.getFullYear() === today.getFullYear();
    }

    getMonthName() {
        const months = ['January', 'February', 'March', 'April', 'May', 'June',
                       'July', 'August', 'September', 'October', 'November', 'December'];
        return months[this.state.currentMonth];
    }

    previousMonth() {
        if (this.state.currentMonth === 0) {
            this.state.currentMonth = 11;
            this.state.currentYear--;
        } else {
            this.state.currentMonth--;
        }
        this.generateCalendar();
    }

    nextMonth() {
        if (this.state.currentMonth === 11) {
            this.state.currentMonth = 0;
            this.state.currentYear++;
        } else {
            this.state.currentMonth++;
        }
        this.generateCalendar();
    }

    getBeatForDate(dateStr) {
        const beats = this.state.beatsByDate[dateStr] || [];
        return beats.length > 0 ? beats[0] : null;
    }
    
    onBeatDragStart(ev, beat) {
        this.state.draggedBeat = beat;
        ev.dataTransfer.effectAllowed = "copy";
        ev.dataTransfer.setData("text/plain", JSON.stringify({
            id: beat.id,
            name: beat.name,
            beat_number: beat.beat_number
        }));
        if (ev.target.classList) {
            ev.target.classList.add("dragging");
        }
    }

    onBeatDragEnd(ev) {
        if (ev.target.classList) {
            ev.target.classList.remove("dragging");
        }
    }

    onCalendarDragOver(ev, dateData) {
        ev.preventDefault();
        ev.stopPropagation();
        if (dateData.isCurrentMonth) {
            ev.dataTransfer.dropEffect = "copy";
        } else {
            ev.dataTransfer.dropEffect = "none";
        }
    }

    onCalendarDragEnter(ev, dateData) {
        ev.preventDefault();
        ev.stopPropagation();
        if (dateData.isCurrentMonth) {
            ev.currentTarget.classList.add("drag-over");
        }
    }

    onCalendarDragLeave(ev) {
        ev.currentTarget.classList.remove("drag-over");
    }

    async onCalendarDrop(ev, dateData) {
        ev.preventDefault();
        ev.stopPropagation();
        ev.currentTarget.classList.remove("drag-over");

        if (!dateData.isCurrentMonth) {
            this.notification.add("Please select a date from current month", { type: "warning" });
            this.state.draggedBeat = null;
            return;
        }

        const existingBeat = this.getBeatForDate(dateData.fullDate);
        if (existingBeat) {
            this.notification.add(`This date already has beat: ${existingBeat.beat_number}. Remove it first.`, { 
                type: "warning" 
            });
            this.state.draggedBeat = null;
            return;
        }

        const beat = this.state.draggedBeat;
        if (!beat || !beat.id) {
            this.state.draggedBeat = null;
            return;
        }

        try {
            const result = await this.orm.call("beat.module", "copy_to_date", [[beat.id], dateData.fullDate]);

            const customerMsg = result.customer_count
                ? ` with ${result.customer_count} customer(s)`
                : "";
            this.notification.add(`New beat ${result.beat_number} created for ${dateData.fullDate}${customerMsg}`, {
                type: "success",
            });

            await this.loadCalendarData();
        } catch (error) {
            console.error("Error creating beat:", error);
            this.notification.add("Failed to create beat: " + (error.message || error), { type: "danger" });
        } finally {
            this.state.draggedBeat = null;
        }
    }

    async removeBeatFromDate(beatId, dateStr) {
        if (!confirm("Remove this beat from the calendar date?")) {
            return;
        }

        try {
            await this.orm.write("beat.module", [beatId], { beat_date: false });
            this.notification.add("Beat removed from date", { type: "success" });
            await this.loadCalendarData();
        } catch (error) {
            console.error("Error removing beat:", error);
            this.notification.add("Failed to remove beat", { type: "danger" });
        }
    }


    async loadCalendarData() {
        try {
            const beats = await this.orm.searchRead(
                "beat.module",
                [
                    ["employee_id", "=", this.props.employeeId],
                    ["beat_date", "!=", false]
                ],
                ["id", "name", "beat_number", "beat_date", "customer_count"]
            );

            const beatsByDate = {};
            beats.forEach(beat => {
                if (beat.beat_date) {
                    if (!beatsByDate[beat.beat_date]) {
                        beatsByDate[beat.beat_date] = [];
                    }
                    beatsByDate[beat.beat_date].push(beat);
                }
            });

            this.state.beatsByDate = beatsByDate;
            this.generateCalendar();
        } catch (error) {
            console.error("Error loading calendar data:", error);
        }
    }


    toggleCustomerList() {
        this.state.showCustomerList = !this.state.showCustomerList;
    }

    getGridHeight() {
        const overflow = this.state.showCustomerList ? "overflow-y: auto;" : "";
        return `
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(calc(100% / 5 - 12px), 1fr));
            gap: 15px;
            width: 100%;
            flex: 1;
            min-height: 0;
            ${overflow}
        `;
    }

    isCustomerSelected(customerId) {
        return this.state.selectedCustomers.includes(customerId);
    }

    isCustomerAlreadyInBeat(customerId) {
        return this.state.existingBeatLineIds.includes(customerId);
    }

    getUniqueAreas() {
        const areas = new Set();
        this.state.allCustomers.forEach(c => {
            if (c.state_id) areas.add(c.state_id[1]);
        });
        return Array.from(areas).sort();
    }

    getUniqueCities() {
        const cities = new Set();
        this.state.allCustomers.forEach(c => {
            if (c.city) cities.add(c.city);
        });
        return Array.from(cities).sort();
    }



    async loadPJP() {
        try {
            const beats = await this.orm.searchRead(
                "beat.module",
                [["employee_id", "=", this.props.employeeId]],
                ["name", "beat_number", "id", "customer_count", "beat_date"]
            );

            this.state.beats = beats.sort((a, b) => {
                const numA = a.beat_number || "";
                const numB = b.beat_number || "";
                return numA.localeCompare(numB);
            });

            this.state.filteredBeats = [...this.state.beats];

            const beatIds = beats.map(b => b.id);

            if (beatIds.length > 0) {
                const allBeatLines = await this.orm.searchRead(
                    "beat.line",
                    [["beat_id", "in", beatIds]],
                    ["id", "partner_id", "partner_phone", "partner_mobile", "partner_email", "sequence", "notes", "beat_id"]
                );

                const beatCustomers = {};
                for (const beat of this.state.beats) {
                    beatCustomers[beat.id] = allBeatLines
                        .filter(line => line.beat_id[0] === beat.id)
                        .sort((a, b) => (a.sequence || 0) - (b.sequence || 0));
                }
                this.state.beatCustomers = beatCustomers;
            } else {
                this.state.beatCustomers = {};
            }

            this.state.loading = false;
        } catch (error) {
            console.error("Error loading PJP:", error);
            this.notification.add("Failed to load PJP data", { type: "danger" });
            this.state.loading = false;
        }
    }


    getToday() {
        return new Date().toISOString().split('T')[0];
    }

    openCreatePJPModal() {
        if (!this.props.employeeId) {
            this.notification.add("Please select an employee first", { type: "warning" });
            return;
        }

        const today = new Date().toISOString().split('T')[0];
        
        this.state.createPJPForm = {
            startDate: today,
            endDate: today,
        };

        this.state.showCreatePJPModal = true;
    }

    closeCreatePJPModal() {
        this.state.showCreatePJPModal = false;
    }

    async saveCreatePJP() {
        const form = this.state.createPJPForm;

        if (!form.startDate || !form.endDate) {
            this.notification.add("Please select start and end dates", { type: "warning" });
            return;
        }

        const today = new Date().toISOString().split('T')[0];
        const startDate = new Date(form.startDate);
        const endDate = new Date(form.endDate);

        if (form.startDate < today) {
            this.notification.add("Start date must be today or a future date", { type: "warning" });
            return;
        }

        if (startDate > endDate) {
            this.notification.add("End date must be on or after start date", { type: "warning" });
            return;
        }

        try {
            const result = await this.orm.call(
                "hr.employee",
                "create_pjp_from_calendar",
                [this.props.employeeId],
                {
                    start_date: form.startDate,
                    end_date: form.endDate,
                }
            );

            if (result.success) {
                this.notification.add(result.message, { type: "success" });
                this.closeCreatePJPModal();
                
                this.action.doAction({
                    type: "ir.actions.act_window",
                    res_model: "pjp.item",
                    name: "PJP Items",
                    view_mode: "list,form",
                    views: [[false, "list"], [false, "form"]],
                    domain: [["pjp_id", "=", result.pjp_id]],
                    target: "current",
                });
            } else {
                this.notification.add(result.message || "Failed to create PJP", { type: "danger" });
            }
        } catch (error) {
            console.error("Error creating PJP:", error);
            this.notification.add("Failed to create PJP: " + error.message, { type: "danger" });
        }
    }

    async addBeat() {
        if (!this.props.employeeId) {
            this.notification.add("Please select an employee first", { type: "warning" });
            return;
        }

        try {
            const employee = await this.orm.searchRead(
                "hr.employee",
                [["id", "=", this.props.employeeId]],
                ["name"]
            );

            const beatCount = this.state.beats.length + 1;
            const beatName = `${employee[0].name} - Beat ${beatCount}`;

            const newBeatIds = await this.orm.create("beat.module", [{
                name: beatName,
                employee_id: this.props.employeeId,
            }]);

            this.notification.add("Beat created successfully!", { type: "success" });

            const createdBeatId = newBeatIds[0];
            await this.loadPJP();
            await this.addCustomers(createdBeatId);
        } catch (error) {
            console.error("Error creating beat:", error);
            this.notification.add("Failed to create beat", { type: "danger" });
        }
    }

    cloneBeatPopup(event) {
        event.stopPropagation();
        this.state.cloneBeatForm = {
            show: true,
            selectedBeatId: null,
            newBeatName: "",
        };
    }

    closeClonePopup() {
        this.state.cloneBeatForm.show = false;
    }

    async cloneBeat() {
        const beatId = parseInt(this.state.cloneBeatForm.selectedBeatId);
        const newName = this.state.cloneBeatForm.newBeatName.trim();

        if (!beatId) {
            this.notification.add("Please select a beat.", { type: "warning" });
            return;
        }
        if (!newName) {
            this.notification.add("Please enter a name.", { type: "warning" });
            return;
        }
        
        try {
            const [beat] = await this.orm.read("beat.module", [beatId], ["employee_id"]);

            const newBeatIds = await this.orm.create("beat.module", [{
                name: newName,
                employee_id: beat.employee_id[0],
            }]);

            const newBeatId = newBeatIds[0];
            const beatLines = await this.orm.searchRead(
                "beat.line",
                [["beat_id", "=", beatId]],
                ["partner_id", "sequence"]
            );

            if (beatLines.length) {
                const newLines = beatLines.map((line) => ({
                    beat_id: newBeatId,
                    partner_id: line.partner_id[0],
                    sequence: line.sequence,
                }));
                await this.orm.create("beat.line", newLines);
            }

            this.notification.add("Beat cloned successfully!", { type: "success" });
            this.state.cloneBeatForm.show = false;
            await this.loadPJP();
        } catch (error) {
            console.error("Error cloning beat:", error);
            this.notification.add("Failed to clone beat", { type: "danger" });
        }
    }


    async goBackToPJP() {
        await this.loadPJP();
        this.state.showCustomerSelection = false;
        this.state.showCalendarSelection = false;
        this.state.beatReadonly = false;
        this.state.selectedCustomers = [];
        this.state.customerSearchText = "";
        this.state.searchByArea = "";
        this.state.searchByCity = "";
        this.state.searchByCategory = "";
    }

    async onBeatChange(ev) {
        this.state.selectedBeatId = parseInt(ev.target.value);
        await this.loadExistingBeatLines();
    }

    async loadExistingBeatLines() {
        if (!this.state.selectedBeatId) return;
        try {
            const beatLines = await this.orm.searchRead(
                "beat.line",
                [["beat_id", "=", this.state.selectedBeatId]],
                ["id", "partner_id"]
            );
            this.state.existingBeatLineIds = beatLines.map(line => line.partner_id[0]);
        } catch (error) {
            console.error("Error loading existing beat lines:", error);
        }
    }

    toggleCustomerSelection(customerId) {
        const index = this.state.selectedCustomers.indexOf(customerId);
        if (index > -1) {
            this.state.selectedCustomers.splice(index, 1);
        } else {
            this.state.selectedCustomers.push(customerId);
        }
    }

    filterCustomers() {
        let filtered = [...this.state.allCustomers];
        if (this.state.customerSearchText) {
            const searchLower = this.state.customerSearchText.toLowerCase();
            filtered = filtered.filter(c =>
                c.name.toLowerCase().includes(searchLower)
            );
        }
        if (this.state.searchByArea && this.state.searchByArea !== "All") {
            filtered = filtered.filter(c =>
                c.state_id && c.state_id[1] === this.state.searchByArea
            );
        }
        if (this.state.searchByCity && this.state.searchByCity !== "All") {
            filtered = filtered.filter(c =>
                c.city && c.city === this.state.searchByCity
            );
        }
        this.state.filteredCustomers = filtered;
    }

    onSearchChange(ev) {
        this.state.customerSearchText = ev.target.value;
        this.filterCustomers();
    }

    onAreaChange(ev) {
        this.state.searchByArea = ev.target.value;
        this.filterCustomers();
    }

    onCityChange(ev) {
        this.state.searchByCity = ev.target.value;
        this.filterCustomers();
    }

    onCategoryChange(ev) {
        this.state.searchByCategory = ev.target.value;
        this.filterCustomers();
    }

    async saveCustomerSelection() {
        if (!this.state.selectedBeatId) {
            this.notification.add("Please select a beat", { type: "warning" });
            return;
        }

        if (this.state.selectedCustomers.length === 0) {
            this.notification.add("Please select at least one customer", { type: "warning" });
            return;
        }

        try {
            const existingLines = await this.orm.searchRead(
                "beat.line",
                [["beat_id", "=", this.state.selectedBeatId]],
                ["sequence"],
                { order: "sequence desc", limit: 1 }
            );

            let nextSequence = 10;
            if (existingLines.length > 0) {
                nextSequence = existingLines[0].sequence + 10;
            }

            const beatLineData = this.state.selectedCustomers.map((customerId, index) => ({
                beat_id: this.state.selectedBeatId,
                partner_id: customerId,
                sequence: nextSequence + (index * 10),
            }));

            await this.orm.create("beat.line", beatLineData);

            this.notification.add(`${this.state.selectedCustomers.length} customer(s) added successfully!`, {
                type: "success",
            });

            this.goBackToPJP();
            await this.loadPJP();

        } catch (error) {
            console.error("Error saving customers:", error);
            this.notification.add("Failed to save customers", { type: "danger" });
        }
    }

    async addSingleCustomerToBeat(customerId) {
        if (!this.state.selectedBeatId) {
            this.notification.add("Please select a beat first", { type: "warning" });
            return;
        }

        if (this.isCustomerAlreadyInBeat(customerId)) {
            this.notification.add("This customer is already added to this beat", { type: "warning" });
            return;
        }

        try {
            const existingLines = await this.orm.searchRead(
                "beat.line",
                [["beat_id", "=", this.state.selectedBeatId]],
                ["sequence"],
                { order: "sequence desc", limit: 1 }
            );

            let nextSequence = 10;
            if (existingLines.length > 0) {
                nextSequence = existingLines[0].sequence + 10;
            }

            await this.orm.create("beat.line", [{
                beat_id: this.state.selectedBeatId,
                partner_id: customerId,
                sequence: nextSequence,
            }]);

            this.notification.add("Customer added successfully!", { type: "success" });
            await this.loadExistingBeatLines();

        } catch (error) {
            console.error("Error adding customer:", error);
            this.notification.add("Failed to add customer", { type: "danger" });
        }
    }

    async removeSingleCustomerFromBeat(customerId) {
        if (!this.state.selectedBeatId) {
            this.notification.add("Please select a beat first", { type: "warning" });
            return;
        }

        try {
            const beatLines = await this.orm.searchRead(
                "beat.line",
                [
                    ["beat_id", "=", this.state.selectedBeatId],
                    ["partner_id", "=", customerId]
                ],
                ["id"]
            );

            if (beatLines.length === 0) {
                this.notification.add("Customer not found in this beat", { type: "warning" });
                return;
            }

            await this.orm.unlink("beat.line", [beatLines[0].id]);
            this.notification.add("Customer removed successfully!", { type: "success" });
            await this.loadExistingBeatLines();

        } catch (error) {
            console.error("Error removing customer:", error);
            this.notification.add("Failed to remove customer", { type: "danger" });
        }
    }


    async movetoCalendar() {
        try {
            this.state.showCalendarSelection = true;
            this.state.filteredBeats = [...this.state.beats];
            await this.loadCalendarData();
        } catch (error) {
            console.error("Error loading calendar:", error);
            this.notification.add("Failed to load calendar", { type: "danger" });
        }
    }

    async addCustomers(beatId = null) {
        if (beatId instanceof Event) {
            beatId = null;
        }

        if (!this.props.employeeId) {
            this.notification.add("Please select an employee first", { type: "warning" });
            return;
        }

        try {
            const beats = await this.orm.searchRead(
                "beat.module",
                [["employee_id", "=", this.props.employeeId]],
                ["id", "name", "beat_number"]
            );

            if (beats.length === 0) {
                this.notification.add("No beats found. Please create a beat first.", { type: "warning" });
                return;
            }

            this.state.beatReadonly = !!beatId;
            this.state.availableBeats = beats;
            this.state.selectedBeatId = beatId || beats[0].id;

            const customers = await this.orm.searchRead(
                "res.partner",
                [["customer_rank", "=", [0, 1]]],
                ["id", "name", "phone", "mobile", "email", "city", "state_id", "create_date"]
            );

            this.state.allCustomers = customers;
            this.state.filteredCustomers = customers;
            this.state.selectedCustomers = [];
            await this.loadExistingBeatLines();
            this.state.showCustomerSelection = true;

        } catch (error) {
            console.error("Error loading customers:", error);
            this.notification.add("Failed to load customers", { type: "danger" });
        }
    }

    async actionUpload() {
        this.notification.add("Upload functionality to be implemented", { type: "info" });
    }

    async openBeatLineForm(beatLineId) {
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "beat.line",
            res_id: beatLineId,
            views: [[false, "form"]],
            target: "new",
        });

        setTimeout(() => this.loadPJP(), 1000);
    }
}

PJPList.template = "employee_dashboard.PJPList";