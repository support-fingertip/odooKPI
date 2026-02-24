/** @odoo-module **/

import { Component, useState, onWillStart, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class TodayVisit extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        
        this.startDayFileInputRef = useRef("startDayFileInput");

        this.state = useState({
            loading: true,
            beats: [],
            allBeatsToday: [],  
            selectedBeat: null,
            showStartDayModal: false,
            showStartBeatModal: false,
            showStartVisitModal: false,
            showEndVisitModal: false,
            showEndBeatModal: false,
            showEndDayModal: false,
            showSwitchBeatModal: false,
            showVisitCommentsModal: false,
            activeVisit: null,
            dayStarted: false,
            dayEnded: false,
            beatStarted: false,
            currentBeatLine: null,
            currentBeatLineIndex: 0,
            currentAttendanceId: null,
            isProcessing: false,
            isCapturingLocation: false,

            showVisitListModal: false,
            visitListData: [],

            showSalesOrderListModal: false,
            salesOrderListData: [],

            showQuickOrder: false,
            customerSummary: null,
            quickOrderTab: 'orders',
            allProducts: [],
            filteredProducts: [],
            productSearchText: "",
            selectedCategoryId: "",
            productCategories: [],
            selectedProducts: {},
            customerOrders: [],
            customerVisits: [],
            lastOrderDetails: null,
            
            startDayForm: {
                todayWorkPlan: "Customer Visit",
                travelType: "",
                vehicleUsed: "",
                uploadedFiles: [],
                locationData: null,
            },
            
            startVisitForm: {
                storeImage: null,
                storeImageName: "",
            },
            
            endVisitForm: {
                comments: "",
            },
            
            endDayForm: {
                locationData: null,
            },
            
            switchBeatForm: {
                reason: "",
                newBeat: null,
            },
            allBeatsForSwap: [],       
            switchBeatLoading: false,  

            visitCommentsForm: {
                comments: "",
            },

            todayKpi: null,          
            kpiLoading: false,

          
            beatSwitchHistory: [],
            showSwitchHistoryModal: false,
        });

        onWillStart(async () => {
            await this.loadTodayBeats();
            await this.checkDayStatus();
            await this.loadTodayKpi();
            await this.loadBeatSwitchHistory();
        });
    }

    formatDateTimeForOdoo(date) {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        const hours = String(date.getHours()).padStart(2, '0');
        const minutes = String(date.getMinutes()).padStart(2, '0');
        const seconds = String(date.getSeconds()).padStart(2, '0');
        return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
    }

    getEmployeeId() {
        const empId = this.props.employeeId || this.props.userId;
        if (!empId) {
            return null;
        }
        return typeof empId === 'number' ? empId : parseInt(empId, 10);
    }

    async loadTodayBeats() {
        const employeeId = this.getEmployeeId();
        
        if (!employeeId) {
            this.state.loading = false;
            return;
        }

        try {
            const today = new Date().toISOString().slice(0, 10);
            
            const beats = await this.orm.searchRead(
                "beat.module",
                [
                    ["employee_id", "=", employeeId],
                    ["beat_date", "=", today]
                ],
                ["id", "name", "beat_number", "beat_date", "status", "swapped_from_beat_id", "swapped_to_beat_id"]
            );

            for (const beat of beats) {
                const beatLines = await this.orm.searchRead(
                    "beat.line",
                    [["beat_id", "=", beat.id]],
                    ["id", "partner_id", "partner_phone", "partner_mobile", "partner_email", "partner_street", "sequence"],
                    { order: "sequence asc" }
                );
                beat.beatLines = beatLines;
                beat.customerCount = beatLines.length;

                for (const line of beatLines) {
                    const visits = await this.orm.searchRead(
                        "visit.model",
                        [
                            ["beat_line_id", "=", line.id],
                            ["actual_start_time", ">=", today],
                            ["actual_start_time", "<=", today + " 23:59:59"]
                        ],
                        ["id", "status", "actual_start_time", "actual_end_time", "visit_comments"]
                    );
                    line.visitStatus = visits.length > 0 ? visits[0] : null;
                }
            }

            this.state.allBeatsToday = beats;

            this.state.beats = beats.filter(beat => {
                if (!beat.beatLines || beat.beatLines.length === 0) {
                    return true;
                }

                const allVisited = beat.beatLines.every(line =>
                    line.visitStatus && line.visitStatus.status === 'completed'
                );

                return !allVisited;
            });
            
            this.state.loading = false;
        } catch (error) {
            console.error("Error loading today's beats:", error);
            this.notification.add("Failed to load today's beats", { type: "danger" });
            this.state.loading = false;
        }
    }

    async checkDayStatus() {
        const employeeId = this.getEmployeeId();
        
        if (!employeeId) return;

        try {
            console.log("🔍 Checking day status for employee:", employeeId);

            const activeVisits = await this.orm.searchRead(
                "visit.model",
                [
                    ["employee_id", "=", employeeId],
                    ["actual_start_time", "!=", false],
                    ["actual_end_time", "=", false]
                ],
                ["id", "beat_id", "beat_line_id", "actual_start_time", "partner_id", "visit_comments", "order_count"]
            );

            if (activeVisits.length > 0) {
                console.log("✅ Active visit found:", activeVisits[0]);
                this.state.activeVisit = activeVisits[0];
                this.state.dayStarted = true;
                this.state.beatStarted = true;
                this.state.selectedBeat = this.state.beats.find(
                    b => b.id === activeVisits[0].beat_id[0]
                );
                
                if (this.state.selectedBeat) {
                    const lineIndex = this.state.selectedBeat.beatLines.findIndex(
                        line => line.id === activeVisits[0].beat_line_id[0]
                    );
                    if (lineIndex !== -1) {
                        this.state.currentBeatLine = this.state.selectedBeat.beatLines[lineIndex];
                        this.state.currentBeatLineIndex = lineIndex;
                    }
                }
                
                await this.loadCustomerSummary(activeVisits[0].partner_id[0]);
            } else {
                console.log("ℹ️ No active visit found");
                
                const today = new Date().toISOString().slice(0, 10);
                const activeBeats = await this.orm.searchRead(
                    "beat.module",
                    [
                        ["employee_id", "=", employeeId],
                        ["beat_date", "=", today],
                        ["status", "=", "in_progress"]
                    ],
                    ["id", "name", "beat_number", "beat_date", "status"]
                );

                if (activeBeats.length > 0) {
                    console.log("✅ Active beat found (in_progress):", activeBeats[0]);
                    const activeBeat = this.state.beats.find(b => b.id === activeBeats[0].id);
                    if (activeBeat) {
                        this.state.selectedBeat = activeBeat;
                        this.state.beatStarted = true;
                        this.state.dayStarted = true;
                        console.log("✅ Beat state restored:", activeBeat.beat_number);
                    }
                }
            }
            const today = new Date().toISOString().slice(0, 10);
            
            const todayAttendance = await this.orm.searchRead(
                "hr.attendance",
                [
                    ["employee_id", "=", employeeId],
                    ["check_in", ">=", today + " 00:00:00"],
                    ["check_in", "<=", today + " 23:59:59"]
                ],
                ["id", "check_in", "check_out"],
                { order: "check_in desc", limit: 1 }
            );

            console.log("📋 Today's attendance records:", todayAttendance);

            if (todayAttendance.length > 0) {
                const attendance = todayAttendance[0];
                this.state.currentAttendanceId = attendance.id;
                
                console.log("📝 Attendance record:", {
                    id: attendance.id,
                    check_in: attendance.check_in,
                    check_out: attendance.check_out
                });

                const hasCheckedOut = attendance.check_out && attendance.check_out !== false;
                
                if (!hasCheckedOut) {
                    console.log("✅ Day is ACTIVE (no check-out)");
                    this.state.dayStarted = true;
                    this.state.dayEnded = false;
                } else {
                    console.log("❌ Day has ENDED (check-out exists)");
                    this.state.dayStarted = false;
                    this.state.dayEnded = true;
                    this.state.beatStarted = false;
                    this.state.currentAttendanceId = null;
                    this.state.activeVisit = null;
                    this.state.selectedBeat = null;
                    this.state.currentBeatLine = null;
                    this.state.customerSummary = null;
                }
            } else {
                console.log("ℹ️ No attendance record for today");
                this.state.dayStarted = false;
                this.state.dayEnded = false;
                this.state.beatStarted = false;
                this.state.currentAttendanceId = null;
                this.state.activeVisit = null;
                this.state.selectedBeat = null;
                this.state.currentBeatLine = null;
                this.state.customerSummary = null;
            }

            console.log("📊 Final day status:", {
                dayStarted: this.state.dayStarted,
                beatStarted: this.state.beatStarted,
                hasActiveVisit: !!this.state.activeVisit,
                hasActiveBeat: !!this.state.selectedBeat,
                attendanceId: this.state.currentAttendanceId
            });

        } catch (error) {
            console.error("❌ Error checking day status:", error);
        }
    }

    async refresh() {
        console.log("🔄 External refresh triggered for TodayVisit");
        await this.loadTodayBeats();
        await this.checkDayStatus();
    }

    openStartDayModal() {
        const employeeId = this.getEmployeeId();
        
        if (!employeeId) {
            this.notification.add("Please select an employee first", { type: "warning" });
            return;
        }

        if (this.state.beats.length === 0) {
            this.notification.add("No beats scheduled for today", { type: "warning" });
            return;
        }

        if (this.state.dayStarted) {
            this.notification.add("Day has already been started", { type: "warning" });
            return;
        }

        this.state.startDayForm = {
            todayWorkPlan: "Customer Visit",
            travelType: "",
            vehicleUsed: "",
            uploadedFiles: [],
            locationData: null,
        };

        this.state.showStartDayModal = true;
        
        this.captureStartDayLocation();
    }

    async captureStartDayLocation() {
        if (this.state.isCapturingLocation) return;
        
        this.state.isCapturingLocation = true;
        this.notification.add("📍 Capturing your location automatically...", { type: "info" });
        
        try {
            const locationData = await this.captureLocationWithAddress();
            
            if (locationData) {
                this.state.startDayForm.locationData = locationData;
                
                let message = `✅ Location captured successfully!\n\nAccuracy: ±${Math.round(locationData.accuracy)}m`;
                if (locationData.full_address) {
                    message += `\n\n📮 ${locationData.full_address}`;
                }
                
                this.notification.add(message, { 
                    type: "success",
                    sticky: false 
                });
            }
        } catch (error) {
            console.error("Location capture error:", error);
            this.notification.add("Failed to capture location: " + error.message, { 
                type: "danger",
                sticky: true 
            });
        } finally {
            this.state.isCapturingLocation = false;
        }
    }

    async captureLocationWithAddress() {
        return new Promise((resolve, reject) => {
            if (!navigator.geolocation) {
                reject(new Error("Geolocation is not supported by your browser"));
                return;
            }

            const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);

            console.log("🌍 Geolocation capture started");
            console.log(`📡 Device: ${isMobile ? "Mobile (GPS)" : "Desktop (WiFi/IP)"}`);

            const options = {
                enableHighAccuracy: true,
                timeout: isMobile ? 45000 : 30000,
                maximumAge: 0
            };

            let attempts = 0;
            const maxAttempts = isMobile ? 4 : 2;
            let bestPosition = null;
            let bestAccuracy = Infinity;
            let watchId = null;

            watchId = navigator.geolocation.watchPosition(
                async (position) => {
                    attempts++;
                    const coords = position.coords;
                    const accuracy = coords.accuracy;

                    console.log(`📍 Reading #${attempts}:`, {
                        lat: coords.latitude.toFixed(6),
                        lon: coords.longitude.toFixed(6),
                        accuracy: accuracy.toFixed(2) + "m"
                    });

                    if (coords.latitude < -90 || coords.latitude > 90 ||
                        coords.longitude < -180 || coords.longitude > 180) {
                        console.error("❌ Invalid coordinates!");
                        return;
                    }

                    if (accuracy < bestAccuracy) {
                        bestAccuracy = accuracy;
                        bestPosition = position;
                        console.log(`✅ New best accuracy: ${accuracy.toFixed(2)}m`);
                    }

                    const targetAccuracy = isMobile ? 50 : 200;
                    const hasGoodAccuracy = accuracy < targetAccuracy;
                    const reachedMaxAttempts = attempts >= maxAttempts;
                    const hasMinimumData = attempts >= 1 && bestPosition !== null;

                    if (hasGoodAccuracy || reachedMaxAttempts || (hasMinimumData && !isMobile)) {
                        if (watchId) {
                            navigator.geolocation.clearWatch(watchId);
                        }
                        
                        console.log(`\n🎯 Acquisition complete after ${attempts} reading(s)`);
                        console.log(`   Best accuracy: ${bestAccuracy.toFixed(2)}m`);

                        try {
                            const addressData = await this.reverseGeocode(
                                bestPosition.coords.latitude,
                                bestPosition.coords.longitude
                            );

                            const locationData = {
                                latitude: bestPosition.coords.latitude,
                                longitude: bestPosition.coords.longitude,
                                accuracy: bestPosition.coords.accuracy,
                                ...addressData
                            };

                            resolve(locationData);
                        } catch (error) {
                            console.error("Reverse geocoding failed:", error);
                            resolve({
                                latitude: bestPosition.coords.latitude,
                                longitude: bestPosition.coords.longitude,
                                accuracy: bestPosition.coords.accuracy,
                                full_address: "Address lookup failed"
                            });
                        }
                    }
                },
                (error) => {
                    if (watchId) {
                        navigator.geolocation.clearWatch(watchId);
                    }
                    
                    console.error("❌ Geolocation error:", error);
                    
                    let errorMessage = "";
                    switch(error.code) {
                        case error.PERMISSION_DENIED:
                            errorMessage = "Location permission denied. Please allow location access.";
                            break;
                        case error.POSITION_UNAVAILABLE:
                            errorMessage = "Location unavailable. Please enable GPS and try again.";
                            break;
                        case error.TIMEOUT:
                            errorMessage = "Location request timed out. Please try again.";
                            break;
                        default:
                            errorMessage = "Unknown location error";
                    }
                    
                    reject(new Error(errorMessage));
                },
                options
            );
        });
    }

    async reverseGeocode(latitude, longitude) {
        try {
            console.log("🔍 Reverse geocoding coordinates...");
            
            const url = `https://nominatim.openstreetmap.org/reverse?format=json&lat=${latitude}&lon=${longitude}&zoom=18&addressdetails=1`;
            
            const response = await fetch(url, {
                headers: {
                    'User-Agent': 'OdooAttendanceApp/1.0'
                }
            });

            if (!response.ok) {
                throw new Error("Geocoding service error");
            }

            const data = await response.json();
            
            if (!data || !data.address) {
                throw new Error("No address data returned");
            }

            const address = data.address;
            
            const house_number = address.house_number || '';
            const road = address.road || '';
            const suburb = address.suburb || address.neighbourhood || address.quarter || '';
            const city = address.city || address.town || address.village || address.municipality || '';
            const district = address.county || address.state_district || '';
            const state = address.state || '';
            const country = address.country || '';
            const postcode = address.postcode || '';

            const address_parts = [];
            if (house_number) address_parts.push(house_number);
            if (road) address_parts.push(road);
            if (suburb) address_parts.push(suburb);
            if (city) address_parts.push(city);
            if (district && district !== city) address_parts.push(district);
            if (state) address_parts.push(state);
            if (postcode) address_parts.push(postcode);
            if (country) address_parts.push(country);

            const full_address = address_parts.join(', ') || data.display_name;

            console.log("✅ Geocoded successfully:", full_address);

            return {
                full_address: full_address,
                house_number: house_number,
                road: road,
                suburb: suburb,
                city: city,
                district: district,
                state: state,
                country: country,
                postcode: postcode
            };

        } catch (error) {
            console.error("Reverse geocoding error:", error);
            throw error;
        }
    }

    
    async loadCustomerSummary(partnerId) {
        if (!partnerId) return;
        
        try {
            const [partner] = await this.orm.searchRead(
                "res.partner",
                [["id", "=", partnerId]],
                ["name", "phone", "mobile", "email", "credit", "debit",
                 "category_id", "company_type", "street", "street2", "city",
                 "state_id", "zip", "country_id", "industry_id", "function"]
            );

            const allOrders = await this.orm.searchRead(
                "sale.order",
                [["partner_id", "=", partnerId]],
                ["id", "amount_total", "date_order", "state"],
                { order: "date_order desc" }
            );

           
            const confirmedOrders = allOrders.filter(o => 
                o.state === 'sale' || o.state === 'done'
            );

            const visits = await this.orm.searchRead(
                "visit.model",
                [["partner_id", "=", partnerId]],
                ["id", "actual_start_time"]
            );

            const outstanding = (partner.debit || 0) - (partner.credit || 0);
            
            const lastOrderDate = allOrders.length > 0 
                ? allOrders[0].date_order
                : null;

            const totalSales = confirmedOrders.reduce((sum, order) => sum + (order.amount_total || 0), 0);

            const addressParts = [];
            if (partner.street) addressParts.push(partner.street);
            if (partner.street2) addressParts.push(partner.street2);
            if (partner.city) addressParts.push(partner.city);
            if (partner.state_id) addressParts.push(partner.state_id[1]);
            if (partner.zip) addressParts.push(partner.zip);
            if (partner.country_id) addressParts.push(partner.country_id[1]);
            const fullAddress = addressParts.join(', ');

            this.state.customerSummary = {
                name: partner.name,
                phone: partner.phone || partner.mobile,
                outstanding: outstanding,
                totalSales: totalSales,
                orderCount: confirmedOrders.length,
                visitCount: visits.length,
                lastOrderDate: lastOrderDate,
                category: partner.category_id && partner.category_id.length > 0
                    ? partner.category_id.map(c => c[1] || c).join(', ')
                    : '',
                companyType: partner.company_type === 'company' ? 'Company' : 'Individual',
                address: fullAddress,
                mobile: partner.mobile || '',
                email: partner.email || '',
                businessType: partner.industry_id ? partner.industry_id[1] : '',
            };

        } catch (error) {
            console.error("Error loading customer summary:", error);
        }
    }

    async openVisitListView() {
        if (!this.state.activeVisit) {
            this.notification.add("Please start a visit first", { type: "warning" });
            return;
        }

        try {
            const visits = await this.orm.searchRead(
                "visit.model",
                [["partner_id", "=", this.state.activeVisit.partner_id[0]]],
                ["id", "name", "actual_start_time", "actual_end_time", "status", "visit_comments", "is_productive", "beat_id"],
                { order: "actual_start_time desc" }
            );

            for (const visit of visits) {
                try {
                    const orders = await this.orm.searchRead(
                        "sale.order",
                        [["visit_id", "=", visit.id]],
                        ["id"]
                    );
                    visit.order_count = orders.length;
                } catch (e) {
                    visit.order_count = 0;
                }
            }

            this.state.visitListData = visits;
            this.state.showVisitListModal = true;
        } catch (error) {
            console.error("Error loading visit list:", error);
            this.notification.add("Failed to load visit list", { type: "danger" });
        }
    }

    closeVisitListModal() {
        this.state.showVisitListModal = false;
        this.state.visitListData = [];
    }

    formatDateTime(datetime) {
        if (!datetime) return "-";
        let date;
        if (datetime.includes('T')) {
            date = new Date(datetime);
        } else {
            date = new Date(datetime.replace(' ', 'T') + 'Z');
        }
        
        return date.toLocaleString("en-US", {
            year: "numeric",
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
            hour12: true
        });
    }

    formatDateOnly(datetime) {
        if (!datetime) return "-";
        
        let date;
        if (datetime.includes('T')) {
            date = new Date(datetime);
        } else {
            date = new Date(datetime.replace(' ', 'T') + 'Z');
        }
        
        return date.toLocaleDateString("en-US", {
            year: "numeric",
            month: "short",
            day: "numeric"
        });
    }

    calculateDuration(startTime, endTime) {
        if (!startTime || !endTime) return "-";
        const start = new Date(startTime.replace(' ', 'T'));
        const end = new Date(endTime.replace(' ', 'T'));
        const diff = Math.floor((end - start) / 1000 / 60);
        const hours = Math.floor(diff / 60);
        const minutes = diff % 60;
        return `${hours}h ${minutes}m`;
    }

    async viewVisitDetails(visitId) {
        try {
            this.action.doAction({
                type: "ir.actions.act_window",
                res_model: "visit.model",
                res_id: visitId,
                name: "Visit Details",
                view_mode: "form",
                views: [[false, "form"]],
                target: "new",
            });
        } catch (error) {
            console.error("Error opening visit details:", error);
            this.notification.add("Failed to open visit details", { type: "danger" });
        }
    }


    async openSalesOrderList() {
        if (!this.state.activeVisit) {
            this.notification.add("Please start a visit first", { type: "warning" });
            return;
        }

        try {
            const orders = await this.orm.searchRead(
                "sale.order",
                [["partner_id", "=", this.state.activeVisit.partner_id[0]]],
                ["id", "name", "date_order", "amount_total", "state", "order_line"],
                { order: "date_order desc" }
            );

            for (const order of orders) {
                if (order.order_line && order.order_line.length > 0) {
                    const orderLines = await this.orm.searchRead(
                        "sale.order.line",
                        [["id", "in", order.order_line]],
                        ["product_id", "product_uom_qty", "price_unit", "price_subtotal", "name"]
                    );
                    order.lines = orderLines;
                } else {
                    order.lines = [];
                }
            }

            this.state.salesOrderListData = orders;
            this.state.showSalesOrderListModal = true;
        } catch (error) {
            console.error("Error loading sales order list:", error);
            this.notification.add("Failed to load sales orders", { type: "danger" });
        }
    }

    closeSalesOrderListModal() {
        this.state.showSalesOrderListModal = false;
        this.state.salesOrderListData = [];
    }

    async viewSalesOrderDetails(orderId) {
        try {
            this.action.doAction({
                type: "ir.actions.act_window",
                res_model: "sale.order",
                res_id: orderId,
                name: "Sales Order Details",
                view_mode: "form",
                views: [[false, "form"]],
                target: "new",
            });
        } catch (error) {
            console.error("Error opening sales order:", error);
            this.notification.add("Failed to open sales order", { type: "danger" });
        }
    }

    getOrderStateBadge(state) {
        const badgeMap = {
            draft: "bg-secondary",
            sent: "bg-info",
            sale: "bg-success",
            done: "bg-success",
            cancel: "bg-danger",
        };
        return badgeMap[state] || "bg-secondary";
    }

    getOrderStateText(state) {
        const stateMap = {
            draft: "Quotation",
            sent: "Quotation Sent",
            sale: "Sales Order",
            done: "Locked",
            cancel: "Cancelled",
        };
        return stateMap[state] || state;
    }

    async openQuickOrder() {
        if (!this.state.activeVisit) {
            this.notification.add("Please start a visit first", { type: "warning" });
            return;
        }

        this.state.showQuickOrder = true;
        this.state.quickOrderTab = 'orders';
        this.state.selectedCategoryId = "";

        await this.loadProducts();
        await this.loadProductCategories();
        await this.loadCustomerOrders();
        await this.loadCustomerVisits();
        await this.loadLastOrderDetails();
    }

    closeQuickOrder() {
        this.state.showQuickOrder = false;
        this.state.selectedProducts = {};
        this.state.productSearchText = "";
        this.state.selectedCategoryId = "";
    }

    async loadProducts() {
        try {
            const products = await this.orm.searchRead(
                "product.product",
                [["sale_ok", "=", true]],
                ["id", "name", "list_price", "default_code", "categ_id", "taxes_id", "uom_id"]
            );

            this.state.allProducts = products;
            this.state.filteredProducts = products;
        } catch (error) {
            console.error("Error loading products:", error);
            this.notification.add("Failed to load products", { type: "danger" });
        }
    }

    async loadProductCategories() {
        try {
            const categories = await this.orm.searchRead(
                "product.category",
                [],
                ["id", "name", "complete_name"],
                { order: "complete_name asc" }
            );
            this.state.productCategories = categories;
        } catch (error) {
            console.error("Error loading product categories:", error);
            this.state.productCategories = [];
        }
    }

    onProductSearchChange(ev) {
        this.state.productSearchText = ev.target.value.toLowerCase();
        this.filterProducts();
    }

    onCategoryChange(ev) {
        this.state.selectedCategoryId = ev.target.value;
        this.filterProducts();
    }

    filterProducts() {
        let filtered = [...this.state.allProducts]; 
        if (this.state.selectedCategoryId) {
            const categId = parseInt(this.state.selectedCategoryId);
            filtered = filtered.filter(product =>
                product.categ_id && product.categ_id[0] === categId
            );
        }

        if (this.state.productSearchText) {
            filtered = filtered.filter(product =>
                product.name.toLowerCase().includes(this.state.productSearchText) ||
                (product.default_code && product.default_code.toLowerCase().includes(this.state.productSearchText))
            );
        }

        this.state.filteredProducts = filtered;
    }

    onQuantityChange(productId, quantity) {
        const product = this.state.allProducts.find(p => p.id === productId);
        if (!product) return;

        const qty = parseInt(quantity) || 0;
        
        if (qty > 0) {
            const price = product.list_price * qty;
            const taxRate = 0.18;
            const taxAmount = price * taxRate;
            
            this.state.selectedProducts[productId] = {
                id: productId,
                name: product.name,
                quantity: qty,
                price: product.list_price,
                uom_id: product.uom_id ? product.uom_id[0] : false,
                subtotal: price,
                tax: taxAmount,
                total: price + taxAmount
            };
        } else {
            delete this.state.selectedProducts[productId];
        }
    }

    getOrderSummary() {
        const products = Object.values(this.state.selectedProducts);
        const subtotal = products.reduce((sum, p) => sum + p.subtotal, 0);
        const tax = products.reduce((sum, p) => sum + p.tax, 0);
        const total = subtotal + tax;
        
        return { subtotal, tax, total, itemCount: products.length };
    }

    async saveQuickOrder() {
        const summary = this.getOrderSummary();
        
        if (summary.itemCount === 0) {
            this.notification.add("Please select at least one product", { type: "warning" });
            return;
        }

        try {
            const employeeId = this.getEmployeeId();

            let userId = false;
            try {
                const [emp] = await this.orm.searchRead(
                    "hr.employee",
                    [["id", "=", employeeId]],
                    ["user_id"]
                );
                if (emp && emp.user_id) {
                    userId = emp.user_id[0];
                }
            } catch (e) {
                console.warn("Could not fetch employee user_id:", e);
            }

            const orderData = {
                partner_id: this.state.activeVisit.partner_id[0],
                visit_id: this.state.activeVisit.id,
            };
            if (userId) {
                orderData.user_id = userId;
            }

            const orderIds = await this.orm.create("sale.order", [orderData]);
            const orderId = orderIds[0];

            for (const product of Object.values(this.state.selectedProducts)) {
                const lineVals = {
                    order_id: orderId,
                    product_id: product.id,
                    product_uom_qty: product.quantity,
                    price_unit: product.price,
                };
                if (product.uom_id) {
                    lineVals.product_uom = product.uom_id;
                }
                await this.orm.create("sale.order.line", [lineVals]);
            }

            if (this.state.activeVisit && this.state.activeVisit.id) {
                await this.orm.write("visit.model", [this.state.activeVisit.id], {
                    is_productive: true,
                });

                this.state.activeVisit.order_count = (this.state.activeVisit.order_count || 0) + 1;
                this.state.activeVisit.is_productive = true;
            }

            this.notification.add(`Order created successfully! Total: ₹${summary.total.toFixed(2)}`, {
                type: "success",
            });

            await this.loadLastOrderDetails();

            this.closeQuickOrder();
            await this.loadTodayBeats();
            await this.loadTodayKpi();

            if (this.state.activeVisit) {
                await this.loadCustomerSummary(this.state.activeVisit.partner_id[0]);
                await this.loadCustomerOrders();
            }

        } catch (error) {
            console.error("Error creating order:", error);

            let errorMsg = "Failed to create order";
            if (error.data && error.data.message) {
                errorMsg += ": " + error.data.message;
            } else if (error.message) {
                errorMsg += ": " + error.message;
            }

            this.notification.add(errorMsg, { type: "danger" });
        }
    }

    switchQuickOrderTab(tab) {
        this.state.quickOrderTab = tab;
    }

    async loadCustomerOrders() {
        if (!this.state.activeVisit) return;
        
        try {
            const orders = await this.orm.searchRead(
                "sale.order",
                [["partner_id", "=", this.state.activeVisit.partner_id[0]]],
                ["id", "name", "date_order", "amount_total", "state", "order_line"],
                { order: "date_order desc", limit: 20 }
            );
            
            for (const order of orders) {
                if (order.order_line && order.order_line.length > 0) {
                    const orderLines = await this.orm.searchRead(
                        "sale.order.line",
                        [["id", "in", order.order_line]],
                        ["product_id", "product_uom_qty", "price_unit", "price_subtotal", "name"]
                    );
                    order.lines = orderLines;
                } else {
                    order.lines = [];
                }
            }
            
            this.state.customerOrders = orders;
        } catch (error) {
            console.error("Error loading customer orders:", error);
            this.state.customerOrders = [];
        }
    }

    async loadCustomerVisits() {
        if (!this.state.activeVisit) return;

        try {
            const visits = await this.orm.searchRead(
                "visit.model",
                [["partner_id", "=", this.state.activeVisit.partner_id[0]]],
                ["id", "actual_start_time", "actual_end_time", "status", "visit_comments", "is_productive"],
                { order: "actual_start_time desc", limit: 20 }
            );

            for (const visit of visits) {
                try {
                    const orders = await this.orm.searchRead(
                        "sale.order",
                        [["visit_id", "=", visit.id]],
                        ["id"]
                    );
                    visit.order_count = orders.length;
                } catch (e) {
                    visit.order_count = 0;
                }
            }

            this.state.customerVisits = visits;
        } catch (error) {
            console.error("Error loading customer visits:", error);
            this.state.customerVisits = [];
        }
    }

    async loadLastOrderDetails() {
        if (!this.state.activeVisit) return;
        
        try {
            const orders = await this.orm.searchRead(
                "sale.order",
                [
                    ["partner_id", "=", this.state.activeVisit.partner_id[0]]
                ],
                ["id", "name", "date_order", "amount_total", "state", "order_line"],
                { order: "date_order desc", limit: 1 }
            );
            
            if (orders.length > 0) {
                const lastOrder = orders[0];
                
                if (lastOrder.order_line && lastOrder.order_line.length > 0) {
                    const orderLines = await this.orm.searchRead(
                        "sale.order.line",
                        [["id", "in", lastOrder.order_line]],
                        ["product_id", "product_uom_qty", "price_unit", "price_subtotal", "name"]
                    );
                    lastOrder.lines = orderLines;
                } else {
                    lastOrder.lines = [];
                }
                
                this.state.lastOrderDetails = lastOrder;
                console.log("✅ Last order loaded:", lastOrder);
            } else {
                this.state.lastOrderDetails = null;
                console.log("ℹ️ No orders found for this customer");
            }
        } catch (error) {
            console.error("Error loading last order details:", error);
            this.state.lastOrderDetails = null;
        }
    }

    async viewOrderDetails(orderId) {
        try {
            this.action.doAction({
                type: "ir.actions.act_window",
                res_model: "sale.order",
                res_id: orderId,
                name: "Order Details",
                view_mode: "form",
                views: [[false, "form"]],
                target: "new",
            });
        } catch (error) {
            console.error("Error opening order:", error);
            this.notification.add("Failed to open order", { type: "danger" });
        }
    }

    closeStartDayModal() {
        this.state.showStartDayModal = false;
        this.state.startDayForm = {
            todayWorkPlan: "Customer Visit",
            travelType: "",
            vehicleUsed: "",
            uploadedFiles: [],
            locationData: null,
        };
    }

    triggerFileUpload() {
        if (this.startDayFileInputRef.el) {
            this.startDayFileInputRef.el.click();
        }
    }

    handleStartDayFileUpload(event) {
        const files = Array.from(event.target.files);
        if (files.length === 0) return;

        for (const file of files) {
            const reader = new FileReader();
            reader.onload = (e) => {
                this.state.startDayForm.uploadedFiles.push({
                    name: file.name,
                    data: e.target.result.split(",")[1],
                });
            };
            reader.readAsDataURL(file);
        }
        
        this.notification.add("Files uploaded successfully!", { type: "success" });
    }

    async saveStartDay() {
        if (this.state.isProcessing) return;

        const form = this.state.startDayForm;

        if (!form.todayWorkPlan || !form.travelType || !form.vehicleUsed) {
            this.notification.add("Please fill all required fields", { type: "warning" });
            return;
        }

        if (!form.locationData) {
            this.notification.add("Please capture your location first", { type: "warning" });
            return;
        }

        try {
            this.state.isProcessing = true;
            const employeeId = this.getEmployeeId();

            const result = await this.orm.call(
                "hr.employee",
                "create_attendance_checkin",
                [employeeId, form.todayWorkPlan, form.travelType, form.vehicleUsed, form.locationData]
            );

            if (result.success) {
                this.state.currentAttendanceId = result.attendance_id;
                this.state.dayStarted = true;
                this.state.showStartDayModal = false;
                
                this.state.startDayForm = {
                    todayWorkPlan: "Customer Visit",
                    travelType: "",
                    vehicleUsed: "",
                    uploadedFiles: [],
                    locationData: null,
                };
                
                this.notification.add(result.message || "Day started successfully!", { type: "success" });
                
                this.env.bus.trigger('attendance-refresh');
                
                await this.checkDayStatus();
            } else {
                throw new Error(result.error || "Failed to record attendance");
            }

        } catch (error) {
            console.error("Error starting day:", error);
            this.notification.add("Failed to start day: " + (error.message || "Unknown error"), { type: "danger" });
        } finally {
            this.state.isProcessing = false;
        }
    }

    
    openStartVisitModal(beatLine, index) {
        if (!this.state.beatStarted) {
            this.notification.add("Please start a beat first", { type: "warning" });
            return;
        }

        if (this.state.activeVisit) {
            this.notification.add("Please end current visit first", { type: "warning" });
            return;
        }

        if (beatLine.visitStatus && beatLine.visitStatus.status === 'completed') {
            this.notification.add("This customer has already been visited today", { type: "warning" });
            return;
        }

        this.state.currentBeatLine = beatLine;
        this.state.currentBeatLineIndex = index;
        this.state.showStartVisitModal = true;
    }

    closeStartVisitModal() {
        this.state.showStartVisitModal = false;
        this.state.startVisitForm = {
            storeImage: null,
            storeImageName: "",
        };
    }

    handleImageUpload(event) {
        const file = event.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (e) => {
            this.state.startVisitForm.storeImage = e.target.result.split(",")[1];
            this.state.startVisitForm.storeImageName = file.name;
        };
        reader.readAsDataURL(file);
    }

    async saveStartVisit() {
        if (!this.state.currentBeatLine) {
            this.notification.add("Please select a customer", { type: "warning" });
            return;
        }

        if (!this.state.startVisitForm.storeImage) {
            this.notification.add("Store Image is required to start a visit", { type: "warning" });
            return;
        }

        try {
            const employeeId = this.getEmployeeId();
            const now = new Date();
            const formattedNow = this.formatDateTimeForOdoo(now);

            const visitData = {
                employee_id: employeeId,
                beat_id: this.state.selectedBeat.id,
                beat_line_id: this.state.currentBeatLine.id,
                partner_id: this.state.currentBeatLine.partner_id[0],
                planned_start_time: formattedNow,
                actual_start_time: formattedNow,
                status: "in_progress",
                visit_for: "Secondary Customer",
                today_work_plan: this.state.startDayForm.todayWorkPlan,
                travel_type: this.state.startDayForm.travelType,
                vehicle_used: this.state.startDayForm.vehicleUsed,
                is_productive: true,
            };

            if (this.state.startVisitForm.storeImage) {
                visitData.store_image = this.state.startVisitForm.storeImage;
                visitData.store_image_filename = this.state.startVisitForm.storeImageName;
            }

            const visitIds = await this.orm.create("visit.model", [visitData]);

            this.state.activeVisit = {
                id: visitIds[0],
                beat_id: [this.state.selectedBeat.id, this.state.selectedBeat.name],
                beat_line_id: [this.state.currentBeatLine.id],
                partner_id: [this.state.currentBeatLine.partner_id[0], this.state.currentBeatLine.partner_id[1]],
                actual_start_time: formattedNow,
                visit_comments: "",
                order_count: 0,
            };

            this.notification.add("Visit started successfully!", { type: "success" });

            this.closeStartVisitModal();
            await this.loadTodayBeats();
            await this.loadCustomerSummary(this.state.currentBeatLine.partner_id[0]);
        } catch (error) {
            console.error("Error starting visit:", error);
            this.notification.add("Failed to start visit: " + (error.message || "Unknown error"), { type: "danger" });
        }
    }

    
    openEndVisitModal() {
        if (!this.state.activeVisit) {
            this.notification.add("No active visit to end", { type: "warning" });
            return;
        }

        this.state.endVisitForm.comments = this.state.activeVisit.visit_comments || "";
        this.state.showEndVisitModal = true;
    }

    closeEndVisitModal() {
        this.state.showEndVisitModal = false;
        this.state.endVisitForm = {
            comments: "",
        };
    }

    async saveEndVisit() {
        try {
            const now = new Date();
            const formattedNow = this.formatDateTimeForOdoo(now);

            const updateData = {
                actual_end_time: formattedNow,
                status: "completed",
                is_productive: true,
            };

            if (this.state.endVisitForm.comments) {
                updateData.visit_comments = this.state.endVisitForm.comments;
            }

            await this.orm.write("visit.model", [this.state.activeVisit.id], updateData);

            this.notification.add("Visit ended successfully!", { type: "success" });

            this.state.activeVisit = null;
            this.state.currentBeatLine = null;
            this.state.customerSummary = null;
            this.closeEndVisitModal();

            await this.loadTodayBeats();
            await this.loadTodayKpi();
        } catch (error) {
            console.error("Error ending visit:", error);
            this.notification.add("Failed to end visit", { type: "danger" });
        }
    }

    
    initiateSwitchBeat(newBeat) {
        if (!this.state.beatStarted) {
            this.notification.add("No active beat to switch", { type: "warning" });
            return;
        }

        if (this.state.activeVisit) {
            this.notification.add("Please end the current visit before switching beats", { type: "warning" });
            return;
        }

        
        this.state.switchBeatForm.newBeat = newBeat;
        this.state.switchBeatForm.reason = "";
        this.state.showSwitchBeatModal = true;
    }
    
    closeSwitchBeatModal() {  
        this.state.showSwitchBeatModal = false;
        this.state.switchBeatForm = {
            reason: "",
            newBeat: null,
        };
    }

    selectBeatForSwitch(beatId) { 
        this.state.switchBeatForm.selectedNewBeat = beatId;
    }
    
    async openSwitchBeatSelection() {
        if (this.state.activeVisit) {
            this.notification.add("Please end the current visit before switching beats", { type: "warning" });
            return;
        }

        this.state.switchBeatForm = {
            reason: "",
            newBeat: null,
        };
        this.state.allBeatsForSwap = [];
        this.state.showSwitchBeatModal = true;

        // Load all eligible beats for the swap modal
        await this.loadBeatsForSwap();
    }

    async loadBeatsForSwap() {
        const employeeId = this.getEmployeeId();
        if (!employeeId) return;

        this.state.switchBeatLoading = true;
        try {
            const today = new Date().toISOString().slice(0, 10);

            const beats = await this.orm.searchRead(
                "beat.module",
                [
                    ["employee_id", "=", employeeId],
                    ["status", "in", ["pending", "draft"]],
                    ["id", "!=", this.state.selectedBeat?.id || 0],
                ],
                ["id", "name", "beat_number", "beat_date", "status"]
            );

            for (const beat of beats) {
                const beatLines = await this.orm.searchRead(
                    "beat.line",
                    [["beat_id", "=", beat.id]],
                    ["id", "partner_id", "partner_phone", "partner_mobile", "partner_email", "partner_street", "sequence"],
                    { order: "sequence asc" }
                );
                beat.beatLines = beatLines;
                beat.customerCount = beatLines.length;

                for (const line of beatLines) {
                    const visits = await this.orm.searchRead(
                        "visit.model",
                        [
                            ["beat_line_id", "=", line.id],
                            ["actual_start_time", ">=", today],
                            ["actual_start_time", "<=", today + " 23:59:59"],
                        ],
                        ["id", "status", "actual_start_time", "actual_end_time"]
                    );
                    line.visitStatus = visits.length > 0 ? visits[0] : null;
                }
            }

            this.state.allBeatsForSwap = beats;
        } catch (error) {
            console.error("Error loading beats for swap:", error);
            this.notification.add("Failed to load available beats", { type: "danger" });
        } finally {
            this.state.switchBeatLoading = false;
        }
    }

    selectNewBeat(beat) {
        this.state.switchBeatForm.newBeat = beat;
    }
    

    getAvailableBeatsForSwitch() {

        return (this.state.allBeatsForSwap || []).filter(b => {
            if (b.id === this.state.selectedBeat?.id) return false;

            if (!b.beatLines || b.beatLines.length === 0) return false;
            const hasIncompleteVisits = b.beatLines.some(line =>
                !line.visitStatus || line.visitStatus.status !== 'completed'
            );

            return hasIncompleteVisits;
        });
    }

    async saveSwitchBeat() {
        if (!this.state.switchBeatForm.reason || !this.state.switchBeatForm.reason.trim()) {
            this.notification.add("Please provide a reason for switching the beat", { type: "warning" });
            return;
        }

        if (!this.state.switchBeatForm.newBeat) {
            this.notification.add("No beat selected for switch", { type: "warning" });
            return;
        }

        try {
            const oldBeatId = this.state.selectedBeat.id;
            const newBeatId = this.state.switchBeatForm.newBeat.id;
            const reason = this.state.switchBeatForm.reason;

            console.log("🔄 Starting beat switch...");
            console.log("Old beat:", oldBeatId, this.state.selectedBeat.beat_number);
            console.log("New beat:", newBeatId, this.state.switchBeatForm.newBeat.beat_number);
            console.log("Reason:", reason);

            const result = await this.orm.call(
                "beat.module",
                "action_swap_beat",  
                [[oldBeatId], newBeatId, reason]
            );

            console.log("✅ Switch result:", result);

            if (result.success) {
  
                await this.loadTodayBeats();
                
                const newBeat = this.state.beats.find(b => b.id === newBeatId);
                
                if (newBeat) {
                    this.state.selectedBeat = newBeat;
                    this.state.currentBeatLineIndex = 0;
                    this.state.beatStarted = true; 
                    this.state.currentBeatLine = null;
                    
                    this.notification.add(
                        `Beat switched successfully! Now working on ${newBeat.beat_number} - ${newBeat.name}`,
                        { type: "success" }
                    );

                    this.closeSwitchBeatModal();
                    await this.loadBeatSwitchHistory();
                } else {
                    throw new Error("Could not find the new beat after switch");
                }
            } else {
                throw new Error(result.error || "Failed to switch beat");
            }

        } catch (error) {
            console.error("❌ Error switching beat:", error);
            this.notification.add("Failed to switch beat: " + (error.message || "Unknown error"), { 
                type: "danger" 
            });
        }
    }

    openStartBeatModal(beat) {
        if (!this.state.dayStarted) {
            this.notification.add("Please start your day first", { type: "warning" });
            return;
        }

        if (this.state.beatStarted) {
            this.notification.add("A beat is already active. Please end it first.", { type: "warning" });
            return;
        }

        if (!beat.beatLines || beat.beatLines.length === 0) {
            this.notification.add("No customers found in this beat", { type: "warning" });
            return;
        }

        this.state.selectedBeat = beat;
        this.state.currentBeatLineIndex = 0;
        this.state.showStartBeatModal = true;
    }

    closeStartBeatModal() {
        this.state.showStartBeatModal = false;
    }

    async saveStartBeat() {
        try {
            console.log("🚀 Starting beat:", this.state.selectedBeat.beat_number);
            
            
            const result = await this.orm.call(
                "beat.module",
                "action_start_beat",
                [[this.state.selectedBeat.id]]
            );

            console.log("✅ Beat start result:", result);

            this.state.beatStarted = true;
            this.state.showStartBeatModal = false;
            
            this.notification.add(`Beat ${this.state.selectedBeat.beat_number} started!`, { type: "success" });
            
            await this.loadTodayBeats();
        } catch (error) {
            console.error("Error starting beat:", error);
            this.notification.add("Failed to start beat: " + (error.message || "Unknown error"), { type: "danger" });
        }
    }

    openEndBeatModal() {
        if (!this.state.beatStarted) {
            this.notification.add("No beat is currently active", { type: "warning" });
            return;
        }

        if (this.state.activeVisit) {
            this.notification.add("Please end the current visit first", { type: "warning" });
            return;
        }

        this.state.showEndBeatModal = true;
    }

    closeEndBeatModal() {
        this.state.showEndBeatModal = false;
    }

    async saveEndBeat() {
        try {
            console.log("🛑 Ending beat:", this.state.selectedBeat.beat_number);
            
       
            const result = await this.orm.call(
                "beat.module",
                "action_complete_beat",
                [[this.state.selectedBeat.id]]
            );

            console.log("✅ Beat end result:", result);

            this.state.beatStarted = false;
            this.state.selectedBeat = null;
            this.state.currentBeatLine = null;
            this.state.currentBeatLineIndex = 0;
            this.state.showEndBeatModal = false;

            this.notification.add("Beat ended successfully!", { type: "success" });
            await this.loadTodayBeats();
        } catch (error) {
            console.error("Error ending beat:", error);
            this.notification.add("Failed to end beat: " + (error.message || "Unknown error"), { type: "danger" });
        }
    }
    


    async openEndDayModal() {
        if (this.state.activeVisit) {
            this.notification.add("Please end current visit first", { type: "warning" });
            return;
        }

        if (this.state.beatStarted) {
            this.notification.add("Please end the current beat first", { type: "warning" });
            return;
        }

        if (!this.state.dayStarted) {
            this.notification.add("No day is currently active", { type: "warning" });
            return;
        }

        if (this.state.isProcessing) {
            console.log("⚠️ Already processing end day, ignoring duplicate click");
            return;
        }

        this.state.isProcessing = true;

        try {
            this.notification.add("📍 Capturing location and ending day...", { type: "info" });

            const locationData = await this.captureLocationWithAddress();

            if (!locationData) {
                throw new Error("Failed to capture location");
            }

            let message = `✅ Location captured!\nAccuracy: ±${Math.round(locationData.accuracy)}m`;
            if (locationData.full_address) {
                message += `\n📮 ${locationData.full_address}`;
            }
            this.notification.add(message, { type: "success", sticky: false });

            console.log("=== Starting End Day Process ===");
            console.log("Location data:", locationData);
            console.log("Current attendance ID:", this.state.currentAttendanceId);

            const employeeId = this.getEmployeeId();

            if (!employeeId) {
                throw new Error("Employee ID not found");
            }

            console.log("Employee ID:", employeeId);

            let attendanceId = this.state.currentAttendanceId;
            
            if (!attendanceId) {
                console.log("No attendance ID found, fetching from today's records...");
                
                const attendanceResult = await this.orm.call(
                    "hr.employee",
                    "get_today_attendance",
                    [employeeId]
                );
                
                console.log("Get today attendance result:", attendanceResult);
                
                if (attendanceResult.success && attendanceResult.attendance_id) {
                    attendanceId = attendanceResult.attendance_id;
                    console.log("Found attendance ID:", attendanceId);
                } else {
                    throw new Error("No active attendance found for today");
                }
            }

            console.log("Using attendance ID:", attendanceId);
            console.log("Calling create_attendance_checkout...");

            const result = await this.orm.call(
                "hr.employee",
                "create_attendance_checkout",
                [employeeId, attendanceId, locationData]
            );

            console.log("Checkout result:", result);

            if (result.success) {
                console.log("✅ Checkout successful! Resetting all state...");
                
                this.state.dayStarted = false;
                this.state.dayEnded = true;
                this.state.beatStarted = false;
                this.state.activeVisit = null;
                this.state.selectedBeat = null;
                this.state.currentBeatLine = null;
                this.state.currentBeatLineIndex = 0;
                this.state.currentAttendanceId = null;
                this.state.customerSummary = null;
                this.state.endDayForm = {
                    locationData: null,
                };
                this.state.isCapturingLocation = false;

                this.notification.add(result.message || "Day ended successfully! ✅", { 
                    type: "success",
                    sticky: false
                });

                this.env.bus.trigger('attendance-refresh');

                console.log("Reloading data in background...");
                setTimeout(async () => {
                    await this.loadTodayBeats();
                    await this.checkDayStatus();
                }, 100);
                
                console.log("✅ End Day Complete!");
                
            } else {
                throw new Error(result.error || "Failed to record check-out");
            }

        } catch (error) {
            console.error("❌ Error ending day:", error);
            this.notification.add("Failed to end day: " + (error.message || "Unknown error"), { 
                type: "danger",
                sticky: true 
            });
        } finally {
            this.state.isProcessing = false;
            console.log("=== End Day Process Complete ===");
        }
    }

    getVisitDuration() {
        if (!this.state.activeVisit) return "0:00";
        
        const start = new Date(this.state.activeVisit.actual_start_time.replace(' ', 'T'));
        const now = new Date();
        const diff = Math.floor((now - start) / 1000 / 60);
        const hours = Math.floor(diff / 60);
        const minutes = diff % 60;
        
        return `${hours}:${minutes.toString().padStart(2, "0")}`;
    }

    getBeatProgress(beat) {
        if (!beat.beatLines || beat.beatLines.length === 0) return "0/0";
        
        const completed = beat.beatLines.filter(line => 
            line.visitStatus && line.visitStatus.status === 'completed'
        ).length;
        
        return `${completed}/${beat.beatLines.length}`;
    }

    getCustomerVisitStatus(beatLine) {
        if (!beatLine.visitStatus) {
            return { text: "Pending", badge: "bg-secondary", icon: "fa-hourglass-start" };
        }
        
        const status = beatLine.visitStatus.status;
        
        if (status === 'completed') {
            return { text: "Completed", badge: "bg-success", icon: "fa-check" };
        } else if (status === 'in_progress') {
            return { text: "In Progress", badge: "bg-warning", icon: "fa-clock-o" };
        } else {
            return { text: "Pending", badge: "bg-secondary", icon: "fa-hourglass-start" };
        }
    }

    getBeatStatusBadge(beat) {
        if (!beat || !beat.status) {
            return { text: "Pending", class: "bg-secondary" };
        }

        const statusMap = {
            draft: { text: "Draft", class: "bg-secondary" },
            pending: { text: "Pending", class: "bg-warning" },
            in_progress: { text: "In Progress", class: "bg-primary" },
            completed: { text: "Completed", class: "bg-success bg-opacity-50" },
            swapped: { text: "Switched", class: "bg-info bg-opacity-50" },
        };

        return statusMap[beat.status] || { text: beat.status, class: "bg-secondary" };
    }


    async loadTodayKpi() {
        const employeeId = this.getEmployeeId();
        if (!employeeId) return;

        this.state.kpiLoading = true;
        try {
            const today = new Date().toISOString().slice(0, 10);
            const todayStart = today + ' 00:00:00';
            const todayEnd = today + ' 23:59:59';

            const completedVisits = await this.orm.searchRead(
                "visit.model",
                [
                    ["employee_id", "=", employeeId],
                    ["status", "=", "completed"],
                    ["actual_start_time", ">=", todayStart],
                    ["actual_start_time", "<=", todayEnd],
                ],
                ["id"]
            );

            let empUserId = false;
            let actualOrdersToday = 0;
            try {
                const [emp] = await this.orm.searchRead(
                    "hr.employee",
                    [["id", "=", employeeId]],
                    ["user_id"]
                );
                if (emp && emp.user_id) {
                    empUserId = emp.user_id[0];
                    const orders = await this.orm.searchRead(
                        "sale.order",
                        [
                            ["user_id", "=", empUserId],
                            ["date_order", ">=", todayStart],
                            ["date_order", "<=", todayEnd],
                            ["state", "in", ["sale", "done"]],
                        ],
                        ["id"]
                    );
                    actualOrdersToday = orders.length;
                }
            } catch (e) {
                console.warn("Could not load today's orders for KPI:", e);
            }

            let targetVisits = 0;
            let targetOrders = 0;
            let periodActualVisits = 0;
            let periodActualOrders = 0;
            try {
                const kpiTargets = await this.orm.searchRead(
                    "kpi.target",
                    [["employee_id", "=", employeeId]],
                    ["id", "target_visits", "target_orders", "period_id"],
                    { order: "id desc", limit: 1 }
                );
                if (kpiTargets.length > 0) {
                    targetVisits = kpiTargets[0].target_visits || 0;
                    targetOrders = kpiTargets[0].target_orders || 0;

                    if (kpiTargets[0].period_id) {
                        const periodId = Array.isArray(kpiTargets[0].period_id)
                            ? kpiTargets[0].period_id[0]
                            : kpiTargets[0].period_id;
                        const periods = await this.orm.searchRead(
                            "kpi.target.period",
                            [["id", "=", periodId]],
                            ["date_from", "date_to"]
                        );
                        if (periods.length > 0 && periods[0].date_from && periods[0].date_to) {
                            const periodFrom = periods[0].date_from + ' 00:00:00';
                            const periodTo = periods[0].date_to + ' 23:59:59';

                            const periodVisits = await this.orm.searchRead(
                                "visit.model",
                                [
                                    ["employee_id", "=", employeeId],
                                    ["status", "=", "completed"],
                                    ["actual_start_time", ">=", periodFrom],
                                    ["actual_start_time", "<=", periodTo],
                                ],
                                ["id"]
                            );
                            periodActualVisits = periodVisits.length;

                            if (empUserId) {
                                const periodOrders = await this.orm.searchRead(
                                    "sale.order",
                                    [
                                        ["user_id", "=", empUserId],
                                        ["date_order", ">=", periodFrom],
                                        ["date_order", "<=", periodTo],
                                        ["state", "in", ["sale", "done"]],
                                    ],
                                    ["id"]
                                );
                                periodActualOrders = periodOrders.length;
                            }
                        }
                    }
                }
            } catch (e) {
                console.warn("Could not load KPI targets:", e);
            }

            const actualVisitsToday = completedVisits.length;

            this.state.todayKpi = {
                actualVisitsToday: actualVisitsToday,
                actualOrdersToday: actualOrdersToday,
                targetVisits: targetVisits,
                targetOrders: targetOrders,
                periodActualVisits: periodActualVisits,
                periodActualOrders: periodActualOrders,
                remainingVisits: Math.max(0, targetVisits - periodActualVisits),
                remainingOrders: Math.max(0, targetOrders - periodActualOrders),

                visitPct: targetVisits > 0 ? Math.min(100, Math.round((periodActualVisits / targetVisits) * 100)) : 0,
                orderPct: targetOrders > 0 ? Math.min(100, Math.round((periodActualOrders / targetOrders) * 100)) : 0,
            };
        } catch (error) {
            console.error("Error loading today's KPI:", error);
        } finally {
            this.state.kpiLoading = false;
        }
    }

    async loadBeatSwitchHistory() {
        const employeeId = this.getEmployeeId();
        if (!employeeId) return;
        try {
            const today = new Date().toISOString().slice(0, 10);
            const history = await this.orm.call(
                "beat.switch.history",
                "get_history_for_employee",
                [employeeId, today]
            );
            this.state.beatSwitchHistory = history || [];
        } catch (error) {
            console.error("Error loading beat switch history:", error);
            this.state.beatSwitchHistory = [];
        }
    }

    openSwitchHistoryModal() {
        this.state.showSwitchHistoryModal = true;
    }

    closeSwitchHistoryModal() {
        this.state.showSwitchHistoryModal = false;
    }
}

TodayVisit.template = "employee_dashboard.TodayVisit";
TodayVisit.props = {
    employeeId: { type: Number, optional: true },
    userId: { type: Number, optional: true },
};