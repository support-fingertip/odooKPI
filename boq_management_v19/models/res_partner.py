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
        """Open all PO ratings for this vendor."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Vendor Ratings — %s') % self.name,
            'res_model': 'vendor.po.rating',
            'view_mode': 'list,form',
            'domain': [('vendor_id', '=', self.id)],
            'context': {'default_vendor_id': self.id},
        }
