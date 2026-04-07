# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    boq_ids = fields.One2many(
        comodel_name='boq.boq',
        inverse_name='partner_id',
        string='Bills of Quantities',
    )
    boq_count = fields.Integer(
        string='BOQ Count',
        compute='_compute_boq_count',
    )

    # ── Vendor Rating (Task 2 — average of all PO ratings) ────────────
    vendor_rating_ids = fields.One2many(
        comodel_name='vendor.po.rating',
        inverse_name='vendor_id',
        string='PO Ratings',
    )
    vendor_rating_avg = fields.Float(
        string='Average Rating',
        compute='_compute_vendor_rating',
        store=True,
        digits=(3, 2),
        help='Average vendor rating across all rated Purchase Orders.',
    )
    vendor_rating_count = fields.Integer(
        string='Rating Count',
        compute='_compute_vendor_rating',
        store=True,
    )
    vendor_rating_status = fields.Selection(
        selection=[
            ('none', 'No Rating'),
            ('low', 'Low (1-2)'),
            ('average', 'Average (3)'),
            ('good', 'Good (4)'),
            ('excellent', 'Excellent (5)'),
        ],
        string='Rating Status',
        compute='_compute_vendor_rating_status',
        store=True,
    )

    # ── Vendor Dashboard Fields (PO aggregates) ───────────────────────
    vendor_po_count = fields.Integer(
        string='Purchase Orders',
        compute='_compute_vendor_po_stats',
        store=False,
    )
    vendor_po_total = fields.Float(
        string='PO Total Value',
        compute='_compute_vendor_po_stats',
        store=False,
        digits=(16, 2),
    )
    vendor_po_paid_count = fields.Integer(
        string='Paid POs',
        compute='_compute_vendor_po_stats',
        store=False,
    )
    vendor_po_pending_count = fields.Integer(
        string='Pending POs',
        compute='_compute_vendor_po_stats',
        store=False,
    )

    # ── Trade/Category-wise fields (which BOQ trades vendor works in) ─
    vendor_trade_names = fields.Char(
        string='Trades',
        compute='_compute_vendor_trades',
        store=False,
        help='BOQ work categories this vendor is assigned to.',
    )
    vendor_boq_line_count = fields.Integer(
        string='BOQ Line Items',
        compute='_compute_vendor_trades',
        store=False,
    )
    vendor_boq_line_total = fields.Float(
        string='BOQ Lines Value',
        compute='_compute_vendor_trades',
        store=False,
        digits=(16, 2),
    )
    vendor_margin_percent = fields.Float(
        string='Margin %',
        compute='_compute_vendor_trades',
        store=False,
        digits=(6, 2),
    )

    # ── Quality sub-ratings (average across POs) ──────────────────────
    vendor_quality_avg = fields.Float(
        string='Avg Quality',
        compute='_compute_vendor_sub_ratings',
        store=True,
        digits=(3, 2),
    )
    vendor_delivery_avg = fields.Float(
        string='Avg Delivery',
        compute='_compute_vendor_sub_ratings',
        store=True,
        digits=(3, 2),
    )
    vendor_pricing_avg = fields.Float(
        string='Avg Pricing',
        compute='_compute_vendor_sub_ratings',
        store=True,
        digits=(3, 2),
    )
    vendor_communication_avg = fields.Float(
        string='Avg Communication',
        compute='_compute_vendor_sub_ratings',
        store=True,
        digits=(3, 2),
    )

    # ═══════════════════════════════════════════════════════════════════
    # COMPUTE METHODS
    # ═══════════════════════════════════════════════════════════════════

    @api.depends('boq_ids')
    def _compute_boq_count(self):
        for partner in self:
            partner.boq_count = len(partner.boq_ids)

    @api.depends('vendor_rating_ids', 'vendor_rating_ids.rating_value')
    def _compute_vendor_rating(self):
        for partner in self:
            ratings = partner.vendor_rating_ids
            if ratings:
                values = ratings.mapped('rating_value')
                partner.vendor_rating_avg = sum(values) / len(values)
                partner.vendor_rating_count = len(values)
            else:
                partner.vendor_rating_avg = 0.0
                partner.vendor_rating_count = 0

    @api.depends('vendor_rating_avg', 'vendor_rating_count')
    def _compute_vendor_rating_status(self):
        for partner in self:
            avg = partner.vendor_rating_avg
            if partner.vendor_rating_count == 0:
                partner.vendor_rating_status = 'none'
            elif avg >= 4.5:
                partner.vendor_rating_status = 'excellent'
            elif avg >= 3.5:
                partner.vendor_rating_status = 'good'
            elif avg >= 2.5:
                partner.vendor_rating_status = 'average'
            else:
                partner.vendor_rating_status = 'low'

    @api.depends(
        'vendor_rating_ids', 'vendor_rating_ids.quality_rating',
        'vendor_rating_ids.delivery_rating', 'vendor_rating_ids.pricing_rating',
        'vendor_rating_ids.communication_rating',
    )
    def _compute_vendor_sub_ratings(self):
        for partner in self:
            ratings = partner.vendor_rating_ids
            if not ratings:
                partner.vendor_quality_avg = 0.0
                partner.vendor_delivery_avg = 0.0
                partner.vendor_pricing_avg = 0.0
                partner.vendor_communication_avg = 0.0
                continue

            def _avg(field_name):
                vals = [int(getattr(r, field_name)) for r in ratings if getattr(r, field_name)]
                return sum(vals) / len(vals) if vals else 0.0

            partner.vendor_quality_avg = _avg('quality_rating')
            partner.vendor_delivery_avg = _avg('delivery_rating')
            partner.vendor_pricing_avg = _avg('pricing_rating')
            partner.vendor_communication_avg = _avg('communication_rating')

    def _compute_vendor_po_stats(self):
        PO = self.env['purchase.order']
        for partner in self:
            pos = PO.search([
                ('partner_id', '=', partner.id),
                ('state', 'in', ('purchase', 'done')),
            ])
            partner.vendor_po_count = len(pos)
            partner.vendor_po_total = sum(pos.mapped('amount_total'))

            paid = 0
            pending = 0
            for po in pos:
                invoices = po.invoice_ids.filtered(
                    lambda inv: inv.move_type == 'in_invoice'
                )
                if invoices and all(
                    inv.payment_state in ('paid', 'in_payment')
                    for inv in invoices
                ):
                    paid += 1
                else:
                    pending += 1
            partner.vendor_po_paid_count = paid
            partner.vendor_po_pending_count = pending

    def _compute_vendor_trades(self):
        """Compute trade/category-wise data from BOQ order lines."""
        for partner in self:
            # Find all BOQ lines where this vendor is assigned
            lines = self.env['boq.order.line'].search([
                ('vendor_ids', 'in', partner.id),
            ])
            if not lines:
                partner.vendor_trade_names = ''
                partner.vendor_boq_line_count = 0
                partner.vendor_boq_line_total = 0.0
                partner.vendor_margin_percent = 0.0
                continue

            # Trade names (unique categories)
            categories = lines.mapped('category_id')
            trade_names = sorted(set(c.name for c in categories if c.name))
            partner.vendor_trade_names = ', '.join(trade_names) if trade_names else 'General'

            # Line counts and totals
            partner.vendor_boq_line_count = len(lines)
            total_sell = sum(
                l.unit_price * l.qty * (1.0 - (l.discount or 0.0) / 100.0)
                for l in lines
            )
            total_cost = sum((l.cost_price or 0.0) * l.qty for l in lines)
            partner.vendor_boq_line_total = total_sell

            # Margin
            if total_sell > 0:
                partner.vendor_margin_percent = round(
                    ((total_sell - total_cost) / total_sell) * 100, 2
                )
            else:
                partner.vendor_margin_percent = 0.0

    # ═══════════════════════════════════════════════════════════════════
    # ACTIONS
    # ═══════════════════════════════════════════════════════════════════

    def action_view_boqs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bills of Quantities'),
            'res_model': 'boq.boq',
            'view_mode': 'list,kanban,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }

    def action_view_vendor_ratings(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vendor Ratings — %s') % self.name,
            'res_model': 'vendor.po.rating',
            'view_mode': 'list,form',
            'domain': [('vendor_id', '=', self.id)],
            'context': {'default_vendor_id': self.id},
        }

    def action_view_vendor_pos(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Orders — %s') % self.name,
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [
                ('partner_id', '=', self.id),
                ('state', 'in', ('purchase', 'done')),
            ],
            'target': 'current',
        }

    def action_view_vendor_boq_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('BOQ Lines — %s') % self.name,
            'res_model': 'boq.order.line',
            'view_mode': 'list,form',
            'domain': [('vendor_ids', 'in', self.id)],
            'target': 'current',
        }
