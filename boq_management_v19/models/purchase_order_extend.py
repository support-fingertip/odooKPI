# -*- coding: utf-8 -*-
"""
purchase.order extension for BOQ Management (Odoo 19)
======================================================
• BOQ back-link (Task 3 — RFQ inside BOQ)
• Vendor Rating after payment released (Task 1)
  - Rating visible ONLY after PO is confirmed AND all invoices are paid
  - Editable by BOQ Manager group only
  - Collected from the manager (not developer / admin)
  - Auto-stamps rating date + rated-by user on save
• Vendor average rating feeds back to res.partner (Task 2)
• Rating shown on PO form, vendor profile, and BOQ Dashboard (Task 3)
"""
from odoo import models, fields, api, _


# ─── Rating selection ─────────────────────────────────────────────────────────
# '0' = "Not Rated" is the FIRST / empty state.
# With the priority widget this renders exactly 5 clickable star positions
# (priority widget renders N-1 stars for N options; 6 options → 5 stars).
RATING_SELECTION = [
    ('0', 'Not Rated'),
    ('1', '1 Star  — Poor'),
    ('2', '2 Stars — Fair'),
    ('3', '3 Stars — Good'),
    ('4', '4 Stars — Very Good'),
    ('5', '5 Stars — Excellent'),
]


class PurchaseOrderBoqExtend(models.Model):
    """
    Extends purchase.order with:
      1. Back-link to the originating BOQ record (non-stored)
      2. Vendor rating fields (stored) — Task 1
         Rating is locked until payment_released is True.
         Only BOQ Managers can submit/change ratings.
    """
    _inherit = 'purchase.order'

    def _auto_init(self):
        """
        Called during module install / upgrade.
        _register_hook() handles server restarts without -u.
        """
        return super()._auto_init()

    @api.model
    def _register_hook(self):
        """
        Called by Odoo on EVERY server startup when the model registry is built.

        WHY THIS MATTERS:
          _auto_init() only runs during install / upgrade.  When someone pulls
          new code and restarts Odoo without -u, the Python model declares
          vendor_rating as a field but the DB column doesn't exist yet.
          Odoo's ORM immediately starts issuing SELECT queries that include ALL
          declared fields, causing:
            psycopg2.errors.UndefinedColumn:
              column purchase_order.vendor_rating does not exist

          ADD COLUMN IF NOT EXISTS here guarantees columns exist before any ORM
          query is executed — zero migration overhead.
        """
        cr = self.env.cr
        cr.execute("""
            ALTER TABLE purchase_order
                ADD COLUMN IF NOT EXISTS vendor_rating         VARCHAR,
                ADD COLUMN IF NOT EXISTS vendor_rating_comment TEXT,
                ADD COLUMN IF NOT EXISTS vendor_rating_date    DATE,
                ADD COLUMN IF NOT EXISTS vendor_rated_by       INTEGER
        """)
        return super()._register_hook()

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
    # B) Vendor Rating — Task 1
    #    Stored fields; UI locked until payment_released = True.
    #    Only BOQ Managers can write ratings (enforced in the view via groups=).
    # ════════════════════════════════════════════════════════════════════════

    vendor_rating = fields.Selection(
        selection=RATING_SELECTION,
        string='Vendor Rating',
        tracking=True,
        help=(
            'Rate this vendor after payment is released. '
            'Only BOQ Managers can rate. '
            '0 = no rating submitted yet.'
        ),
    )
    vendor_rating_comment = fields.Text(
        string='Rating Comment',
        help='Optional remarks about vendor performance on this PO.',
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

    # ── payment_released — non-stored Boolean ────────────────────────────
    payment_released = fields.Boolean(
        string='Payment Released',
        compute='_compute_payment_released',
        store=False,
        help=(
            'True when the PO is confirmed (state=purchase/done) AND '
            'all linked vendor bills are posted and fully paid. '
            'The vendor rating section is only shown when this is True.'
        ),
    )

    # ── Computed helper: was a real rating (1-5) submitted? ─────────────
    is_rated = fields.Boolean(
        string='Is Rated',
        compute='_compute_is_rated',
        store=False,
        help='True when a 1–5 rating has been submitted (excludes the "0 = not rated" value).',
    )

    @api.depends('vendor_rating')
    def _compute_is_rated(self):
        for rec in self:
            rec.is_rated = bool(rec.vendor_rating) and rec.vendor_rating != '0'

    # ── rating_display — non-stored star string ──────────────────────────
    rating_display = fields.Char(
        string='Rating Stars',
        compute='_compute_rating_display',
        help='Visual star representation of the vendor rating.',
    )

    @api.depends('vendor_rating')
    def _compute_rating_display(self):
        for rec in self:
            val = rec.vendor_rating
            if val and val != '0':
                filled = int(val)
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
        Payment is released when ALL of the following are true:
          1. PO confirmed: state in ('purchase', 'done')
          2. At least one vendor bill exists (move_type='in_invoice')
          3. ALL vendor bills are posted (state='posted') AND fully paid
             (payment_state in ('paid', 'in_payment'))
        """
        for order in self:
            if order.state not in ('purchase', 'done'):
                order.payment_released = False
                continue
            bills = order.invoice_ids.filtered(
                lambda inv: inv.move_type == 'in_invoice'
            )
            if not bills:
                order.payment_released = False
                continue
            all_paid = all(
                inv.state == 'posted'
                and inv.payment_state in ('paid', 'in_payment')
                for inv in bills
            )
            order.payment_released = all_paid

    # ── Override write: auto-stamp rating date + rated_by user ──────────
    def write(self, vals):
        """
        When a real rating (1–5) is being saved:
          • vendor_rating_date  → today        (only if not already set)
          • vendor_rated_by     → current user (only if not already set)

        When the rating is cleared (False / '0'):
          • vendor_rating_date  → False  (force-clear, regardless of setdefault)
          • vendor_rated_by     → False  (force-clear)

        We use direct assignment (not setdefault) for the clear case so that a
        manager who first rated '3', then switches to '0' will have their stamp
        fields actually removed rather than left stale.
        """
        new_rating = vals.get('vendor_rating')
        if new_rating is not None:
            if new_rating and new_rating != '0':
                # Real 1–5 rating: stamp only when not already provided
                vals.setdefault('vendor_rating_date', fields.Date.today())
                vals.setdefault('vendor_rated_by',    self.env.user.id)
            else:
                # Rating cleared or set to '0': always wipe the stamp fields
                vals['vendor_rating_date'] = False
                vals['vendor_rated_by']    = False
        return super().write(vals)
