# -*- coding: utf-8 -*-
from odoo import models, fields, api


class BoqBoq(models.Model):
    """
    Main BOQ (Bill of Quantities) record linked to a Customer.
    The `category_ids` Many2many controls which notebook tabs are visible.
    """
    _name = 'boq.boq'
    _description = 'Bill of Quantities'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    _rec_name = 'name'

    # ── Identity ─────────────────────────────────────────────────────────────
    name = fields.Char(
        string='BOQ Reference',
        required=True,
        copy=False,
        default=lambda self: self.env['ir.sequence'].next_by_code('boq.boq') or 'New',
        tracking=True,
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Customer',
        required=True,
        tracking=True,
        index=True,
    )
    date = fields.Date(
        string='Date',
        default=fields.Date.context_today,
        tracking=True,
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('done', 'Done'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        tracking=True,
        copy=False,
    )
    project_name = fields.Char(string='Project Name', tracking=True)
    project_location = fields.Char(string='Site / Location')
    notes = fields.Html(string='Internal Notes')
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        default=lambda self: self.env.company,
    )

    # ── Category visibility control ──────────────────────────────────────────
    category_ids = fields.Many2many(
        comodel_name='boq.category',
        relation='boq_boq_category_rel',
        column1='boq_id',
        column2='category_id',
        string='Work Categories',
        help='Select the work categories to activate their tabs below.',
    )

    # ── Computed helpers for tab visibility ──────────────────────────────────
    # We store the IDs as a comma-separated list so the view's invisible
    # domain can evaluate: category not in category_ids
    visible_category_ids = fields.Char(
        string='Visible Category IDs',
        compute='_compute_visible_category_ids',
        store=False,
    )

    # ── Order lines per category ─────────────────────────────────────────────
    line_ids = fields.One2many(
        comodel_name='boq.order.line',
        inverse_name='boq_id',
        string='All Lines',
    )

    # Individual domain-filtered One2many per well-known category code
    # (These are used inside each notebook page for a cleaner UX)
    electrical_line_ids = fields.One2many(
        comodel_name='boq.order.line',
        inverse_name='boq_id',
        string='Electrical Lines',
        domain="[('category_id.code', '=', 'electrical')]",
    )
    civil_line_ids = fields.One2many(
        comodel_name='boq.order.line',
        inverse_name='boq_id',
        string='Civil Lines',
        domain="[('category_id.code', '=', 'civil')]",
    )
    lighting_line_ids = fields.One2many(
        comodel_name='boq.order.line',
        inverse_name='boq_id',
        string='Lighting Lines',
        domain="[('category_id.code', '=', 'lighting')]",
    )
    plumbing_line_ids = fields.One2many(
        comodel_name='boq.order.line',
        inverse_name='boq_id',
        string='Plumbing Lines',
        domain="[('category_id.code', '=', 'plumbing')]",
    )
    hvac_line_ids = fields.One2many(
        comodel_name='boq.order.line',
        inverse_name='boq_id',
        string='HVAC Lines',
        domain="[('category_id.code', '=', 'hvac')]",
    )
    finishing_line_ids = fields.One2many(
        comodel_name='boq.order.line',
        inverse_name='boq_id',
        string='Finishing Lines',
        domain="[('category_id.code', '=', 'finishing')]",
    )

    # Boolean helpers — one per built-in category, used by invisible attrs
    show_electrical = fields.Boolean(compute='_compute_tab_visibility', store=False)
    show_civil = fields.Boolean(compute='_compute_tab_visibility', store=False)
    show_lighting = fields.Boolean(compute='_compute_tab_visibility', store=False)
    show_plumbing = fields.Boolean(compute='_compute_tab_visibility', store=False)
    show_hvac = fields.Boolean(compute='_compute_tab_visibility', store=False)
    show_finishing = fields.Boolean(compute='_compute_tab_visibility', store=False)

    # ── Totals ────────────────────────────────────────────────────────────────
    total_amount = fields.Float(
        string='Total Amount',
        compute='_compute_totals',
        store=True,
        digits='Product Price',
        tracking=True,
    )
    electrical_total = fields.Float(compute='_compute_totals', store=True, digits='Product Price')
    civil_total = fields.Float(compute='_compute_totals', store=True, digits='Product Price')
    lighting_total = fields.Float(compute='_compute_totals', store=True, digits='Product Price')
    plumbing_total = fields.Float(compute='_compute_totals', store=True, digits='Product Price')
    hvac_total = fields.Float(compute='_compute_totals', store=True, digits='Product Price')
    finishing_total = fields.Float(compute='_compute_totals', store=True, digits='Product Price')

    # ── Computes ──────────────────────────────────────────────────────────────
    @api.depends('category_ids')
    def _compute_visible_category_ids(self):
        for rec in self:
            rec.visible_category_ids = ','.join(str(c.id) for c in rec.category_ids)

    @api.depends('category_ids')
    def _compute_tab_visibility(self):
        for rec in self:
            codes = rec.category_ids.mapped('code')
            rec.show_electrical = 'electrical' in codes
            rec.show_civil = 'civil' in codes
            rec.show_lighting = 'lighting' in codes
            rec.show_plumbing = 'plumbing' in codes
            rec.show_hvac = 'hvac' in codes
            rec.show_finishing = 'finishing' in codes

    @api.depends('line_ids.subtotal', 'line_ids.category_id')
    def _compute_totals(self):
        for rec in self:
            lines = rec.line_ids
            rec.electrical_total = sum(lines.filtered(lambda l: l.category_id.code == 'electrical').mapped('subtotal'))
            rec.civil_total = sum(lines.filtered(lambda l: l.category_id.code == 'civil').mapped('subtotal'))
            rec.lighting_total = sum(lines.filtered(lambda l: l.category_id.code == 'lighting').mapped('subtotal'))
            rec.plumbing_total = sum(lines.filtered(lambda l: l.category_id.code == 'plumbing').mapped('subtotal'))
            rec.hvac_total = sum(lines.filtered(lambda l: l.category_id.code == 'hvac').mapped('subtotal'))
            rec.finishing_total = sum(lines.filtered(lambda l: l.category_id.code == 'finishing').mapped('subtotal'))
            rec.total_amount = sum(lines.mapped('subtotal'))

    # ── Actions ───────────────────────────────────────────────────────────────
    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_done(self):
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_view_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'BOQ Lines',
            'res_model': 'boq.order.line',
            'view_mode': 'list,form',
            'domain': [('boq_id', '=', self.id)],
            'context': {'default_boq_id': self.id},
        }

    # ── Helper: resolve category id by code (used in context) ────────────
    @api.model
    def get_category_id_by_code(self, code):
        cat = self.env['boq.category'].search([('code', '=', code)], limit=1)
        return cat.id if cat else False

    # ── Sequence ──────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('boq.boq') or 'New'
        return super().create(vals_list)
