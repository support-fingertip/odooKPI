# -*- coding: utf-8 -*-
"""
res.partner extension for BOQ Management
=========================================
• BOQ smart button (existing)
• Vendor average rating computed from all rated POs (Task 2)
  - vendor_avg_rating  : stored Float — auto-recalculates on any PO rating change
  - vendor_rating_count: stored Integer — number of rated POs
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
    # Vendor Rating aggregates (Task 2 + Task 3)
    # ════════════════════════════════════════════════════════════════════════

    vendor_avg_rating = fields.Float(
        string='Average Vendor Rating',
        compute='_compute_vendor_avg_rating',
        store=False,        # non-stored: no DB column needed, safe on all Odoo versions
        digits=(16, 2),
        help=(
            'Average of all PO vendor ratings given to this vendor. '
            'Recalculates on each read.'
        ),
    )
    vendor_rating_count = fields.Integer(
        string='Rated POs',
        compute='_compute_vendor_avg_rating',
        store=False,        # non-stored: no DB column needed
        help='Number of Purchase Orders that have been rated for this vendor.',
    )
    vendor_rating_display = fields.Char(
        string='Rating Stars',
        compute='_compute_vendor_rating_display',
        help='Visual star display of the average rating (e.g. ★★★☆☆).',
    )

    @api.depends('purchase_order_ids.vendor_rating')
    def _compute_vendor_avg_rating(self):
        """
        Recalculate average rating whenever any PO for this vendor gets rated.
        Uses purchase_order_ids (standard Odoo field on res.partner for POs
        where partner_id = self).
        """
        for partner in self:
            rated_pos = partner.purchase_order_ids.filtered(
                lambda po: po.vendor_rating
            )
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
        """Open list of rated POs for this vendor."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Rated POs — %s') % self.name,
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [
                ('partner_id', '=', self.id),
                ('vendor_rating', '!=', False),
            ],
            'context': {'default_partner_id': self.id},
        }
