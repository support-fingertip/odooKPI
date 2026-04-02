# -*- coding: utf-8 -*-
"""
res.partner extension for BOQ Management
=========================================
• BOQ smart button (existing)
• Vendor average rating computed from all rated POs (Task 2)
  - vendor_avg_rating   : non-stored Float — recomputes on each read
  - vendor_rating_count : non-stored Integer — count of rated POs (1–5 only)
  - vendor_rating_display: non-stored Char — star string, e.g. ★★★☆☆

Rules:
  • Only POs with vendor_rating IN ('1','2','3','4','5') count toward the average.
  • POs with vendor_rating = '0' (not rated) or vendor_rating = False are excluded.
  • auto-recalculates whenever a PO rating is written (store=False + empty @api.depends).
"""
from odoo import models, fields, api, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # ── BOQ link (existing) ───────────────────────────────────────────────
    boq_ids = fields.One2many(
        comodel_name='boq.boq',
        inverse_name='partner_id',
        string='Bills of Quantities',
    )
    boq_count = fields.Integer(
        string='BOQ Count',
        compute='_compute_boq_count',
    )

    @api.depends('boq_ids')
    def _compute_boq_count(self):
        for partner in self:
            partner.boq_count = len(partner.boq_ids)

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

    # ════════════════════════════════════════════════════════════════════════
    # Vendor Rating aggregates — Task 2 + Task 3
    # ════════════════════════════════════════════════════════════════════════

    vendor_avg_rating = fields.Float(
        string='Average Vendor Rating',
        compute='_compute_vendor_avg_rating',
        store=False,
        digits=(16, 2),
        help=(
            'Average of all PO vendor ratings (1–5) for this vendor. '
            'Recomputes on each read from the database.'
        ),
    )
    vendor_rating_count = fields.Integer(
        string='Rated POs',
        compute='_compute_vendor_avg_rating',
        store=False,
        help='Number of Purchase Orders that carry a real 1–5 rating for this vendor.',
    )
    vendor_rating_display = fields.Char(
        string='Rating Stars',
        compute='_compute_vendor_rating_display',
        help='Visual star display of the average rating, e.g. ★★★☆☆.',
    )

    @api.depends()
    def _compute_vendor_avg_rating(self):
        """
        Aggregate vendor_rating from purchase.order for each partner.

        IMPORTANT — only counts ratings in ('1','2','3','4','5').
        '0' means "the rating section appeared but no real rating was submitted."
        An empty/False means the manager never opened the rating section.
        Both are excluded so the average reflects only genuine scores.

        Empty @api.depends() → recomputes fresh on every read (no DB column
        needed) and avoids dependency on non-declared purchase_order_ids.
        """
        for partner in self:
            rated_pos = self.env['purchase.order'].search([
                ('partner_id', '=', partner.id),
                ('vendor_rating', 'in', ['1', '2', '3', '4', '5']),
            ])
            partner.vendor_rating_count = len(rated_pos)
            if rated_pos:
                total = sum(int(po.vendor_rating) for po in rated_pos)
                partner.vendor_avg_rating = round(total / len(rated_pos), 2)
            else:
                partner.vendor_avg_rating = 0.0

    @api.depends('vendor_avg_rating')
    def _compute_vendor_rating_display(self):
        for partner in self:
            filled = round(partner.vendor_avg_rating)
            if filled > 0:
                partner.vendor_rating_display = '★' * filled + '☆' * (5 - filled)
            else:
                partner.vendor_rating_display = 'Not rated yet'

    def action_view_vendor_ratings(self):
        """Open list of rated POs for this vendor (Task 3 — Vendor profile button)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vendor Ratings — %s') % self.name,
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [
                ('partner_id', '=', self.id),
                ('vendor_rating', 'in', ['1', '2', '3', '4', '5']),
            ],
            'context': {'default_partner_id': self.id},
        }
