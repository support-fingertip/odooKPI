# -*- coding: utf-8 -*-
"""
Tradeways Vendor + Rating Models  (Task 4)
==========================================
tradeways.vendor  — directory of trade contacts (subcontractors, suppliers, consultants)
tradeways.rating  — individual rating records per vendor (same logic as vendor PO rating)

Rating is collected by BOQ Manager ONLY.
Average rating auto-recalculates whenever a rating record is added/changed.
"""
from odoo import models, fields, api, _


class TradewaysVendor(models.Model):
    _name = 'tradeways.vendor'
    _description = 'Tradeways Vendor'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'name'

    # ── Identity ──────────────────────────────────────────────────────────
    name = fields.Char(
        string='Company / Trade Name',
        required=True,
        tracking=True,
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Linked Contact',
        domain=[('supplier_rank', '>', 0)],
        help='Optionally link to an existing Odoo vendor contact.',
    )
    trade_type = fields.Selection([
        ('supplier',       'Supplier'),
        ('subcontractor',  'Subcontractor'),
        ('consultant',     'Consultant'),
        ('manufacturer',   'Manufacturer'),
        ('other',          'Other'),
    ], string='Trade Type', default='supplier', required=True, tracking=True)

    contact_name = fields.Char(string='Contact Person')
    phone        = fields.Char(string='Phone')
    email        = fields.Char(string='Email')
    address      = fields.Text(string='Address')
    website      = fields.Char(string='Website')
    notes        = fields.Html(string='Internal Notes')

    state = fields.Selection([
        ('active',   'Active'),
        ('inactive', 'Inactive'),
    ], string='Status', default='active', required=True, tracking=True)

    # ── Rating aggregates (computed + stored) ─────────────────────────────
    rating_ids = fields.One2many(
        comodel_name='tradeways.rating',
        inverse_name='tradeways_id',
        string='Ratings',
    )
    avg_rating = fields.Float(
        string='Average Rating',
        compute='_compute_avg_rating',
        store=True,
        digits=(16, 2),
        help='Average of all individual ratings given to this Tradeways vendor.',
    )
    rating_count = fields.Integer(
        string='Ratings Given',
        compute='_compute_avg_rating',
        store=True,
    )

    @api.depends('rating_ids.rating')
    def _compute_avg_rating(self):
        for rec in self:
            rated = rec.rating_ids.filtered(lambda r: r.rating)
            rec.rating_count = len(rated)
            if rated:
                vals = [int(r.rating) for r in rated]
                rec.avg_rating = round(sum(vals) / len(vals), 2)
            else:
                rec.avg_rating = 0.0

    # ── Display helpers ────────────────────────────────────────────────────
    def _rating_stars_display(self):
        """Return a filled/empty star string for display (e.g. '★★★☆☆')."""
        self.ensure_one()
        filled = round(self.avg_rating)
        return '★' * filled + '☆' * (5 - filled)

    def action_view_vendor_ratings_tw(self):
        """Open rating history list for this Tradeways vendor."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Ratings — %s') % self.name,
            'res_model': 'tradeways.rating',
            'view_mode': 'list,form',
            'domain': [('tradeways_id', '=', self.id)],
            'context': {'default_tradeways_id': self.id},
        }

    def action_open_add_rating(self):
        """Open a new rating form pre-linked to this vendor (popup)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Add Rating — %s') % self.name,
            'res_model': 'tradeways.rating',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_tradeways_id': self.id},
        }

    @api.model
    def get_tradeways_dashboard_stats(self):
        """
        Aggregate stats for the Tradeways Dashboard header cards.
        Called via RPC from TradewysDashboard OWL component.
        """
        vendors = self.search([])
        active   = vendors.filtered(lambda v: v.state == 'active')
        inactive = vendors.filtered(lambda v: v.state == 'inactive')

        all_ratings = self.env['tradeways.rating'].search([])
        rated_vendors = vendors.filtered(lambda v: v.rating_count > 0)

        overall_avg = 0.0
        if rated_vendors:
            overall_avg = round(
                sum(v.avg_rating for v in rated_vendors) / len(rated_vendors), 2
            )

        type_counts = {}
        for sel_val, sel_label in self._fields['trade_type'].selection:
            cnt = len(vendors.filtered(lambda v, sv=sel_val: v.trade_type == sv))
            if cnt:
                type_counts[sel_val] = {'label': sel_label, 'count': cnt}

        return {
            'total_vendors':   len(vendors),
            'active_vendors':  len(active),
            'inactive_vendors': len(inactive),
            'total_ratings':   len(all_ratings),
            'rated_vendors':   len(rated_vendors),
            'overall_avg':     overall_avg,
            'type_counts':     type_counts,
        }

    @api.model
    def get_tradeways_vendor_list(self):
        """
        Return per-vendor summary for the Tradeways Dashboard cards.
        Called via RPC from TradewysDashboard OWL component.
        """
        vendors = self.search([], order='avg_rating desc, name')
        result = []
        for v in vendors:
            filled  = round(v.avg_rating)
            result.append({
                'id':            v.id,
                'name':          v.name,
                'trade_type':    dict(self._fields['trade_type'].selection).get(v.trade_type, v.trade_type),
                'trade_type_key': v.trade_type,
                'contact_name':  v.contact_name or '',
                'phone':         v.phone or '',
                'email':         v.email or '',
                'state':         v.state,
                'avg_rating':    v.avg_rating,
                'rating_count':  v.rating_count,
                'stars_filled':  filled,
                'stars_empty':   5 - filled,
                'recent_comment': v.rating_ids[:1].comment if v.rating_ids else '',
            })
        return result

    @api.model
    def get_tradeways_rating_history(self, vendor_id):
        """
        Return full rating history for one vendor (for notebook detail tab).
        """
        vendor = self.browse(vendor_id)
        if not vendor.exists():
            return []
        result = []
        for r in vendor.rating_ids.sorted('rating_date', reverse=True):
            filled = int(r.rating) if r.rating else 0
            result.append({
                'id':          r.id,
                'rating':      filled,
                'stars':       '★' * filled + '☆' * (5 - filled),
                'comment':     r.comment or '',
                'rated_by':    r.rated_by.name if r.rated_by else '—',
                'rating_date': r.rating_date.strftime('%d %b %Y') if r.rating_date else '—',
                'po_name':     r.purchase_order_id.name if r.purchase_order_id else '—',
            })
        return result


class TradewaysRating(models.Model):
    _name = 'tradeways.rating'
    _description = 'Tradeways Rating'
    _order = 'rating_date desc'

    tradeways_id = fields.Many2one(
        comodel_name='tradeways.vendor',
        string='Tradeways Vendor',
        required=True,
        ondelete='cascade',
        index=True,
    )
    rating = fields.Selection([
        ('1', '1 — Poor'),
        ('2', '2 — Fair'),
        ('3', '3 — Good'),
        ('4', '4 — Very Good'),
        ('5', '5 — Excellent'),
    ], string='Rating', required=True)

    comment      = fields.Text(string='Comment / Remarks')
    rated_by     = fields.Many2one(
        comodel_name='res.users',
        string='Rated By',
        default=lambda self: self.env.user,
        readonly=True,
    )
    rating_date  = fields.Date(
        string='Rating Date',
        default=fields.Date.today,
    )
    purchase_order_id = fields.Many2one(
        comodel_name='purchase.order',
        string='Related PO',
        help='Optionally link this rating to a specific Purchase Order.',
    )

    # ── Rating star display (non-stored) ──────────────────────────────────
    rating_display = fields.Char(
        string='Stars',
        compute='_compute_rating_display',
    )

    @api.depends('rating')
    def _compute_rating_display(self):
        for rec in self:
            if rec.rating:
                filled = int(rec.rating)
                rec.rating_display = '★' * filled + '☆' * (5 - filled)
            else:
                rec.rating_display = '☆☆☆☆☆'
