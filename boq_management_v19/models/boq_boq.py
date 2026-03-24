# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


# ── Predefined category codes (must match seeded data) ───────────────────────
_CATEGORY_CODES = ['electrical', 'civil', 'lighting', 'plumbing', 'hvac', 'finishing']


class BoqBoq(models.Model):
    """
    Main BOQ (Bill of Quantities) record.

    Key design: `category_ids` (Many2many) drives which notebook tabs
    are visible. A boolean compute field per category is evaluated
    by the view's `invisible` attribute — this is the cleanest approach
    that works in Odoo 19 without JavaScript patches.
    """
    _name = 'boq.boq'
    _description = 'Bill of Quantities'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, name desc'
    _rec_name = 'name'
    _check_company_auto = True

    # ── Identity ──────────────────────────────────────────────────────────
    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default='New',
        tracking=True,
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        related='company_id.currency_id',
        store=True,
    )

    # ── Customer / Project ────────────────────────────────────────────────
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Customer',
        required=True,
        tracking=True,
        index=True,
        domain=[('is_company', '=', True)],
    )
    partner_shipping_id = fields.Many2one(
        comodel_name='res.partner',
        string='Site Contact',
        domain="[('parent_id', '=', partner_id)]",
    )
    project_name = fields.Char(
        string='Project Name',
        tracking=True,
    )
    project_location = fields.Char(string='Site / Location')
    date = fields.Date(
        string='BOQ Date',
        default=fields.Date.context_today,
        tracking=True,
    )
    validity_date = fields.Date(string='Valid Until')
    user_id = fields.Many2one(
        comodel_name='res.users',
        string='Assigned To',
        default=lambda self: self.env.user,
        tracking=True,
        index=True,
    )

    # ── Status ────────────────────────────────────────────────────────────
    state = fields.Selection(
        selection=[
            ('draft',     'Draft'),
            ('submitted', 'Submitted'),
            ('approved',  'Approved'),
            ('rejected',  'Rejected'),
            ('done',      'Done'),
        ],
        string='Status',
        default='draft',
        copy=False,
        tracking=True,
        index=True,
    )
    priority = fields.Selection(
        selection=[('0', 'Normal'), ('1', 'Urgent')],
        string='Priority',
        default='0',
    )
    notes = fields.Html(
        string='Terms & Notes',
        sanitize_overridable=True,
    )

    # ═══════════════════════════════════════════════════════════════════════
    # CATEGORY VISIBILITY CONTROL
    # category_ids drives which notebook tabs appear.
    # One boolean compute field per category enables `invisible` in views.
    # ═══════════════════════════════════════════════════════════════════════
    category_ids = fields.Many2many(
        comodel_name='boq.category',
        relation='boq_boq_category_rel',
        column1='boq_id',
        column2='category_id',
        string='Work Categories',
        help='Select work categories to activate their tabs below. '
             'Unselected categories will be hidden.',
    )

    # Boolean visibility flags (non-stored computes, evaluated in view)
    show_electrical = fields.Boolean(compute='_compute_tab_flags')
    show_civil      = fields.Boolean(compute='_compute_tab_flags')
    show_lighting   = fields.Boolean(compute='_compute_tab_flags')
    show_plumbing   = fields.Boolean(compute='_compute_tab_flags')
    show_hvac       = fields.Boolean(compute='_compute_tab_flags')
    show_finishing  = fields.Boolean(compute='_compute_tab_flags')

    @api.depends('category_ids')
    def _compute_tab_flags(self):
        for rec in self:
            codes = set(rec.category_ids.mapped('code'))
            rec.show_electrical = 'electrical' in codes
            rec.show_civil      = 'civil'      in codes
            rec.show_lighting   = 'lighting'   in codes
            rec.show_plumbing   = 'plumbing'   in codes
            rec.show_hvac       = 'hvac'       in codes
            rec.show_finishing  = 'finishing'  in codes

    # ═══════════════════════════════════════════════════════════════════════
    # ORDER LINES — one domain-filtered O2M per category tab
    # ═══════════════════════════════════════════════════════════════════════
    line_ids = fields.One2many(
        comodel_name='boq.order.line',
        inverse_name='boq_id',
        string='All Lines',
        copy=True,
    )
    electrical_line_ids = fields.One2many(
        'boq.order.line', 'boq_id',
        domain=[('category_id.code', '=', 'electrical')],
        string='Electrical Lines',
    )
    civil_line_ids = fields.One2many(
        'boq.order.line', 'boq_id',
        domain=[('category_id.code', '=', 'civil')],
        string='Civil Lines',
    )
    lighting_line_ids = fields.One2many(
        'boq.order.line', 'boq_id',
        domain=[('category_id.code', '=', 'lighting')],
        string='Lighting Lines',
    )
    plumbing_line_ids = fields.One2many(
        'boq.order.line', 'boq_id',
        domain=[('category_id.code', '=', 'plumbing')],
        string='Plumbing Lines',
    )
    hvac_line_ids = fields.One2many(
        'boq.order.line', 'boq_id',
        domain=[('category_id.code', '=', 'hvac')],
        string='HVAC Lines',
    )
    finishing_line_ids = fields.One2many(
        'boq.order.line', 'boq_id',
        domain=[('category_id.code', '=', 'finishing')],
        string='Finishing Lines',
    )

    # ── Totals ────────────────────────────────────────────────────────────
    electrical_total = fields.Monetary(
        compute='_compute_totals', store=True, precompute=True,
        currency_field='currency_id',
    )
    civil_total = fields.Monetary(
        compute='_compute_totals', store=True, precompute=True,
        currency_field='currency_id',
    )
    lighting_total = fields.Monetary(
        compute='_compute_totals', store=True, precompute=True,
        currency_field='currency_id',
    )
    plumbing_total = fields.Monetary(
        compute='_compute_totals', store=True, precompute=True,
        currency_field='currency_id',
    )
    hvac_total = fields.Monetary(
        compute='_compute_totals', store=True, precompute=True,
        currency_field='currency_id',
    )
    finishing_total = fields.Monetary(
        compute='_compute_totals', store=True, precompute=True,
        currency_field='currency_id',
    )
    total_amount = fields.Monetary(
        string='Grand Total',
        compute='_compute_totals',
        store=True,
        precompute=True,
        currency_field='currency_id',
        tracking=True,
    )
    line_count = fields.Integer(
        string='Lines',
        compute='_compute_totals',
        store=True,
        precompute=True,
    )

    @api.depends('line_ids.subtotal', 'line_ids.category_id')
    def _compute_totals(self):
        for rec in self:
            lines = rec.line_ids
            def cat_sum(code):
                return sum(
                    l.subtotal for l in lines
                    if l.category_id and l.category_id.code == code
                )
            rec.electrical_total = cat_sum('electrical')
            rec.civil_total      = cat_sum('civil')
            rec.lighting_total   = cat_sum('lighting')
            rec.plumbing_total   = cat_sum('plumbing')
            rec.hvac_total       = cat_sum('hvac')
            rec.finishing_total  = cat_sum('finishing')
            rec.total_amount     = sum(lines.mapped('subtotal'))
            rec.line_count       = len(lines)

    # ── Computed label for smart button ───────────────────────────────────
    @api.depends('line_count')
    def _compute_stat_label(self):
        for rec in self:
            rec.stat_label = str(rec.line_count)

    # ── Sequence / Create ─────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('boq.boq') or 'New'
                )
        return super().create(vals_list)

    def copy(self, default=None):
        default = dict(default or {})
        default['name'] = 'New'
        return super().copy(default)

    # ── Workflow actions ──────────────────────────────────────────────────
    def action_submit(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError(_('Cannot submit a BOQ with no lines.'))
        self.write({'state': 'submitted'})

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_reject(self):
        self.write({'state': 'rejected'})

    def action_done(self):
        self.write({'state': 'done'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    # ── Smart button: open all lines ──────────────────────────────────────
    def action_view_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('BOQ Lines — %s') % self.name,
            'res_model': 'boq.order.line',
            'view_mode': 'list,form',
            'domain': [('boq_id', '=', self.id)],
            'context': {'default_boq_id': self.id},
        }

    # ── Model helper ──────────────────────────────────────────────────────
    @api.model
    def _get_category_id(self, code):
        """Return the ID of the category with the given code."""
        cat = self.env['boq.category'].search(
            [('code', '=', code)], limit=1
        )
        return cat.id if cat else False
