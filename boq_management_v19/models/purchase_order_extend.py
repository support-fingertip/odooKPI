# -*- coding: utf-8 -*-
"""
purchase.order extension for BOQ Management (Odoo 19)
======================================================
• BOQ back-link (Task 3 — RFQ inside BOQ)
• Vendor Rating after payment released (Task 1)
  - Rating visible ONLY after PO is confirmed AND all invoices are paid
  - Editable by BOQ Manager group only
  - Collected once per PO; auto-stamps date + user
"""
from odoo import models, fields, api, _


# ─── Rating selection shared constant ──────────────────────────────────────────
RATING_SELECTION = [
    ('1', '1 — Poor'),
    ('2', '2 — Fair'),
    ('3', '3 — Good'),
    ('4', '4 — Very Good'),
    ('5', '5 — Excellent'),
]


class PurchaseOrderBoqExtend(models.Model):
    """
    Extends purchase.order with:
      1. Back-link to the originating BOQ record (non-stored)
      2. Vendor rating fields (stored) — Task 1
         Rating is locked until payment_released is True.
    """
    _inherit = 'purchase.order'

    # ════════════════════════════════════════════════════════════════════════
    # A) BOQ Back-link (non-stored — derived from rfq_ids M2M)
    # ════════════════════════════════════════════════════════════════════════

    boq_id = fields.Many2one(
        comodel_name='boq.boq',
        string='BOQ Reference',
        compute='_compute_boq_id',
        store=False,
        help='BOQ that generated this RFQ (read from the BOQ ↔ RFQ M2M link).',
    )

    @api.depends()
    def _compute_boq_id(self):
        if not self.ids:
            return
        self.env.cr.execute(
            """
            SELECT purchase_id, boq_id
              FROM boq_boq_purchase_order_rel
             WHERE purchase_id IN %s
            """,
            (tuple(self.ids),)
        )
        mapping = {row[0]: row[1] for row in self.env.cr.fetchall()}
        for order in self:
            order.boq_id = mapping.get(order.id, False)

    total_tax = fields.Monetary(
        string='Total Tax',
        related='amount_tax',
        store=False,
        currency_field='currency_id',
        help='Total tax on all order lines (alias of amount_tax).',
    )

    boq_description = fields.Text(
        string='BOQ Description',
        compute='_compute_boq_description',
        store=False,
        help='Combines origin and BOQ details for display on RFQ forms.',
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

    # ════════════════════════════════════════════════════════════════════════
    # B) Vendor Rating (Task 1) — stored, locked until payment released
    # ════════════════════════════════════════════════════════════════════════

    vendor_rating = fields.Selection(
        selection=RATING_SELECTION,
        string='Vendor Rating',
        tracking=True,
        help='Rate this vendor after payment is released. Only BOQ Managers can rate.',
    )
    vendor_rating_comment = fields.Text(
        string='Rating Comment',
        help='Optional remarks about the vendor performance on this PO.',
    )
    vendor_rating_date = fields.Date(
        string='Rating Date',
        readonly=True,
        copy=False,
        help='Auto-set to today when a rating is saved.',
    )
    vendor_rated_by = fields.Many2one(
        comodel_name='res.users',
        string='Rated By',
        readonly=True,
        copy=False,
        help='The manager who submitted the rating.',
    )

    # ── payment_released: computed (stored) ──────────────────────────────
    payment_released = fields.Boolean(
        string='Payment Released',
        compute='_compute_payment_released',
        store=False,        # non-stored: no DB column needed, recalculates on read
        help=(
            'True when the PO is confirmed (state=purchase/done) AND '
            'all linked vendor bills are posted and fully paid.'
        ),
    )

    # ── rating_display: non-stored star string ───────────────────────────
    rating_display = fields.Char(
        string='Rating Stars',
        compute='_compute_rating_display',
        help='Visual star representation of the vendor rating.',
    )

    @api.depends('vendor_rating')
    def _compute_rating_display(self):
        for rec in self:
            if rec.vendor_rating:
                filled = int(rec.vendor_rating)
                rec.rating_display = '★' * filled + '☆' * (5 - filled)
            else:
                rec.rating_display = '—'

    @api.depends(
        'state',
        'invoice_ids',
        'invoice_ids.state',
        'invoice_ids.payment_state',
    )
    def _compute_payment_released(self):
        """
        Payment is released when:
        1. PO is in state 'purchase' or 'done'  (confirmed)
        2. At least one vendor bill exists (invoice_ids filtered to vendor bills)
        3. ALL vendor bills are posted (state='posted') AND paid
           (payment_state in ('paid', 'in_payment'))
        """
        for order in self:
            if order.state not in ('purchase', 'done'):
                order.payment_released = False
                continue
            # Filter to vendor bills only (type='in_invoice')
            bills = order.invoice_ids.filtered(
                lambda inv: inv.move_type == 'in_invoice'
            )
            if not bills:
                order.payment_released = False
                continue
            all_paid = all(
                inv.state == 'posted' and inv.payment_state in ('paid', 'in_payment')
                for inv in bills
            )
            order.payment_released = all_paid

    # ── Override write to auto-stamp rating date + user ──────────────────
    def write(self, vals):
        if 'vendor_rating' in vals and vals.get('vendor_rating'):
            vals.setdefault('vendor_rating_date', fields.Date.today())
            vals.setdefault('vendor_rated_by', self.env.user.id)
        return super().write(vals)
