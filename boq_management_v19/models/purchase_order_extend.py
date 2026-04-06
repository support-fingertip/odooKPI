# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class PurchaseOrderBoqExtend(models.Model):
    """
    Extends purchase.order with a back-link to the originating BOQ record
    and a convenience total_tax field.

    Task 3 — RFQ inside BOQ.

    IMPORTANT — no stored fields on purchase.order:
    Both boq_id and total_tax are non-stored so they never need a DB column
    and no module upgrade / ALTER TABLE is required on purchase_order.

    boq_id   — computed from the existing boq_boq_purchase_order_rel M2M table
                that is created by boq.boq.rfq_ids (already exists after install).
    total_tax — non-stored related alias of amount_tax (reads live, no column).
    """
    _inherit = 'purchase.order'

    # ── BOQ Back-link (non-stored — derived from rfq_ids M2M) ────────────
    boq_id = fields.Many2one(
        comodel_name='boq.boq',
        string='BOQ Reference',
        compute='_compute_boq_id',
        store=False,          # No DB column on purchase_order table
        help='BOQ that generated this RFQ (read from the BOQ ↔ RFQ M2M link).',
    )

    @api.depends()
    def _compute_boq_id(self):
        """
        Derive boq_id by querying the boq_boq_purchase_order_rel table
        which is owned by boq.boq.rfq_ids (Many2many, already exists).
        Single batch query — no N+1 problem.
        """
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

    # ── Total Tax (non-stored related — reads live from amount_tax) ───────
    total_tax = fields.Monetary(
        string='Total Tax',
        related='amount_tax',
        store=False,          # No DB column on purchase_order table
        currency_field='currency_id',
        help='Total tax on all order lines (alias of amount_tax).',
    )

    # ── BOQ description (non-stored computed display field) ───────────────
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

    # ── Vendor Rating (Task 1) ───────────────────────────────────────
    vendor_rating_id = fields.Many2one(
        comodel_name='vendor.po.rating',
        string='Vendor Rating',
        compute='_compute_vendor_rating_id',
        store=False,
    )
    vendor_rating_value = fields.Integer(
        string='Rating',
        related='vendor_rating_id.rating_value',
        store=False,
    )
    vendor_payment_released = fields.Boolean(
        string='Payment Released',
        compute='_compute_vendor_payment_released',
        store=False,
        help='True when all vendor bills for this PO are fully paid.',
    )
    can_rate_vendor = fields.Boolean(
        string='Can Rate Vendor',
        compute='_compute_can_rate_vendor',
        store=False,
    )

    def _compute_vendor_rating_id(self):
        ratings = self.env['vendor.po.rating'].search([
            ('purchase_order_id', 'in', self.ids)
        ])
        rating_map = {r.purchase_order_id.id: r for r in ratings}
        for order in self:
            order.vendor_rating_id = rating_map.get(order.id, False)

    def _compute_vendor_payment_released(self):
        """
        Payment is considered released when:
        - PO state is 'purchase' or 'done'
        - All related vendor bills exist and are in 'paid' state
        """
        for order in self:
            if order.state not in ('purchase', 'done'):
                order.vendor_payment_released = False
                continue
            invoices = order.invoice_ids.filtered(
                lambda inv: inv.move_type == 'in_invoice'
            )
            if not invoices:
                order.vendor_payment_released = False
                continue
            order.vendor_payment_released = all(
                inv.payment_state in ('paid', 'in_payment', 'reversed')
                for inv in invoices
            )

    def _compute_can_rate_vendor(self):
        """
        Rating is allowed only when:
        1. PO is confirmed (purchase/done)
        2. Payment is released (all invoices paid)
        3. No rating exists yet for this PO
        4. Current user is a BOQ Manager
        """
        is_manager = self.env.user.has_group('boq_management_v19.group_boq_manager')
        for order in self:
            order.can_rate_vendor = (
                is_manager
                and order.vendor_payment_released
                and not order.vendor_rating_id
            )

    def action_rate_vendor(self):
        """Open the vendor rating wizard for this PO."""
        self.ensure_one()
        if not self.can_rate_vendor:
            from odoo.exceptions import UserError
            raise UserError(_(
                'Cannot rate vendor. Ensure:\n'
                '1. Purchase Order is confirmed\n'
                '2. All vendor bills are paid\n'
                '3. No rating exists yet\n'
                '4. You are a BOQ Manager'
            ))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Rate Vendor — %s') % self.partner_id.name,
            'res_model': 'vendor.po.rating',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_purchase_order_id': self.id,
                'default_vendor_id': self.partner_id.id,
            },
        }

    def action_view_rating(self):
        """Open existing rating for this PO."""
        self.ensure_one()
        if not self.vendor_rating_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vendor Rating — %s') % self.partner_id.name,
            'res_model': 'vendor.po.rating',
            'res_id': self.vendor_rating_id.id,
            'view_mode': 'form',
            'target': 'new',
        }

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
