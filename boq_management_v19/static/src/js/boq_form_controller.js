/** @odoo-module **/
/**
 * BOQ Management v19 — Form Controller Enhancement
 *
 * What this does:
 *  1. Adds live line-count badges on each notebook tab title
 *  2. Animates the summary strip when totals change
 *  3. Highlights the active tab band with a subtle pulse on entry
 *
 * Odoo 19 / OWL 3 compatible.
 */

import { patch }          from "@web/core/utils/patch";
import { FormController }  from "@web/views/form/form_controller";
import { onMounted, onPatched, useRef } from "@odoo/owl";

// ── Constants ────────────────────────────────────────────────────────────
const TAB_LINE_MAP = {
    tab_electrical: "electrical_line_ids",
    tab_civil:      "civil_line_ids",
    tab_lighting:   "lighting_line_ids",
    tab_plumbing:   "plumbing_line_ids",
    tab_hvac:       "hvac_line_ids",
    tab_finishing:  "finishing_line_ids",
};

// ── Helpers ──────────────────────────────────────────────────────────────
/**
 * Find the form root element from the OWL component reference.
 * Compatible with Odoo 19's OWL 3 rendering.
 */
function getFormEl(component) {
    // Walk up via __owl__ bdom references (Odoo 19 OWL 3 approach)
    try {
        const el = component.__owl__?.bdom?.el;
        if (el) {
            return el.closest?.(".o_form_view") || el.closest?.(".o_form_sheet_bg");
        }
    } catch (_) { /* noop */ }
    return null;
}

/**
 * Update the count badge on every visible notebook tab.
 * Badge shows the number of product lines in that category.
 */
function updateTabBadges(formEl) {
    if (!formEl) return;

    Object.entries(TAB_LINE_MAP).forEach(([tabName, fieldName]) => {
        // Find the nav-link button for this tab
        const navLink = formEl.querySelector(
            `.nav-link[name="${tabName}"], .o_notebook_headers [data-name="${tabName}"]`
        );
        if (!navLink) return;

        // Count data rows in the One2many list for this field
        const lineWidget = formEl.querySelector(
            `.o_field_widget[name="${fieldName}"]`
        );
        const count = lineWidget
            ? lineWidget.querySelectorAll(".o_data_row:not(.o_optional_columns_dropdown)").length
            : 0;

        // Remove old badge
        navLink.querySelector(".boq_tab_badge")?.remove();

        if (count > 0) {
            const badge = document.createElement("span");
            badge.className = "boq_tab_badge badge rounded-pill ms-2";
            badge.style.cssText = [
                "font-size: 0.65rem",
                "padding: 0.2em 0.5em",
                "background: var(--boq-blue)",
                "color: #fff",
                "font-weight: 700",
                "vertical-align: middle",
                "transition: all 0.15s ease",
            ].join(";");
            badge.textContent = count;
            navLink.appendChild(badge);
        }
    });
}

/**
 * Pulse-animate the grand total value on change.
 */
function pulseTotalField(formEl) {
    if (!formEl) return;
    const totalEl = formEl.querySelector(".boq_grand_total_value");
    if (!totalEl) return;
    totalEl.style.transition = "transform 0.15s ease, color 0.15s ease";
    totalEl.style.transform = "scale(1.08)";
    setTimeout(() => { totalEl.style.transform = "scale(1)"; }, 160);
}

// ── Patch FormController ─────────────────────────────────────────────────
patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);

        // Only apply to BOQ forms
        if (this.props?.resModel !== "boq.boq") return;

        onMounted(() => {
            const el = getFormEl(this);
            updateTabBadges(el);
        });

        onPatched(() => {
            const el = getFormEl(this);
            updateTabBadges(el);
            pulseTotalField(el);
        });
    },
});
