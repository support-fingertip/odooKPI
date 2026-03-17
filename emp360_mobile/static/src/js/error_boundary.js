/** @odoo-module **/
/**
 * EMPLOYEE 360 — OWL Screen Error Boundary
 *
 * Wraps individual screen components. If a child component throws during
 * rendering (e.g. due to a stale asset bundle), the error is caught here
 * and a recovery UI is displayed instead of a blank/broken screen.
 *
 * Recovery UI shows a "Clear Cache & Reload" button that hits
 * /emp360/clear-assets to delete the stale ir.attachment bundle,
 * then redirects back to the app with fresh assets.
 */

import { Component, useState } from "@odoo/owl";

export class ScreenErrorBoundary extends Component {
    static template = "employee_mobile.ScreenErrorBoundary";
    static props = { slots: { type: Object } };

    setup() {
        this.state = useState({ error: false, errorMsg: "" });
    }

    handleError(error) {
        console.error("[emp360] Screen render error caught by boundary:", error);
        this.state.errorMsg = (error.cause || error).message || "Unknown error";
        this.state.error = true;
    }
}
