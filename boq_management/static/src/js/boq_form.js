/** @odoo-module **/

/**
 * BOQ Form — JavaScript helpers
 *
 * Purpose:
 *   When a user clicks "Add a line" inside a category tab, the new line
 *   must be pre-filled with the correct `category_id`.  Odoo 18 resolves
 *   the `context` expression on the One2many field at render time, but
 *   `_get_category_id()` is a Python-like helper we can't call directly.
 *
 *   Instead we patch the One2many fields' default-get context at the model
 *   level (see boq_boq.py — each field already has a static domain filtering
 *   by category code).  The context `{'default_category_id': <id>}` is
 *   injected via a server-side onchange.
 *
 *   This JS file handles:
 *   1. Visual tab counter badges (live count of lines per tab)
 *   2. Smooth animation when category tags change
 */

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { onWillStart, onMounted, onPatched } from "@odoo/owl";

// ── Tab line-count badges ─────────────────────────────────────────────────
function updateTabBadges(el) {
    if (!el) return;
    const tabMap = {
        electrical: "electrical_line_ids",
        civil:      "civil_line_ids",
        lighting:   "lighting_line_ids",
        plumbing:   "plumbing_line_ids",
        hvac:       "hvac_line_ids",
        finishing:  "finishing_line_ids",
    };
    Object.entries(tabMap).forEach(([tabName, fieldName]) => {
        const tab = el.querySelector(`.nav-link[name="${tabName}"]`);
        if (!tab) return;
        const page = el.querySelector(`.tab-pane[name="${tabName}"]`);
        if (!page) return;
        const rows = page.querySelectorAll(
            `.o_field_widget[name="${fieldName}"] .o_data_row`
        );
        const count = rows.length;
        // Remove existing badge
        const old = tab.querySelector(".boq_tab_badge");
        if (old) old.remove();
        if (count > 0) {
            const badge = document.createElement("span");
            badge.className = "boq_tab_badge badge rounded-pill ms-2";
            badge.style.cssText =
                "font-size:0.7rem;padding:0.2em 0.55em;background:#2563eb;color:#fff;";
            badge.textContent = count;
            tab.appendChild(badge);
        }
    });
}

patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);
        onMounted(() => {
            if (this.model.root.resModel === "boq.boq") {
                updateTabBadges(this.__owl__.bdom?.el?.closest?.(".o_form_view"));
            }
        });
        onPatched(() => {
            if (this.model.root.resModel === "boq.boq") {
                updateTabBadges(this.__owl__.bdom?.el?.closest?.(".o_form_view"));
            }
        });
    },
});
