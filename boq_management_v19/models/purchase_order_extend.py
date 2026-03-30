# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class PurchaseOrderBoqExtend(models.Model):
    """
    Extends purchase.order with a back-link to the originating BOQ record
    and a convenience `total_tax` field.

    Task 3 — RFQ inside BOQ:
    - boq_id: Many2one link back to boq.boq (set by action_create_rfq)
    - total_tax: Computed monetary field = amount_tax (exposed for views)
    - description field already exists as `notes` on purchase.order
    """
    _inherit = 'purchase.order'

    # ── BOQ Back-link ─────────────────────────────────────────────────────
    boq_id = fields.Many2one(
        comodel_name='boq.boq',
        string='BOQ Reference',
        ondelete='set null',
        copy=False,
        index=True,
        tracking=True,
        help='Bill of Quantities that originated this Request for Quotation.',
    )

    # ── Convenience: expose total tax amount ─────────────────────────────
    # Note: purchase.order already computes `amount_tax` in the base module.
    # We add `total_tax` as a related alias so views can reference it clearly
    # without relying on the base field name which may differ across versions.
    total_tax = fields.Monetary(
        string='Total Tax',
        related='amount_tax',
        store=True,
        currency_field='currency_id',
        help='Total tax amount on all order lines (same as Tax in order totals).',
    )

    # ── RFQ description: computed display field for BOQ context ──────────
    boq_description = fields.Text(
        string='BOQ Description',
        compute='_compute_boq_description',
        store=False,
        help='Combines origin and BOQ details for display on RFQ forms linked to BOQ.',
    )

    @api.depends('origin', 'boq_id', 'boq_id.name', 'boq_id.project_name')
    def _compute_boq_description(self):
        for order in self:
            parts = []
            if order.boq_id:
                parts.append(_('BOQ: %s') % order.boq_id.name)
                if order.boq_id.project_name:
                    parts.append(_('Project: %s') % order.boq_id.project_name)
            if order.origin:
                parts.append(order.origin)
            order.boq_description = '\n'.join(parts) if parts else ''

    def action_open_boq(self):
        """Open the linked BOQ record in form view."""
        self.ensure_one()
        if not self.boq_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': _('BOQ — %s') % self.boq_id.name,
            'res_model': 'boq.boq',
            'res_id': self.boq_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
