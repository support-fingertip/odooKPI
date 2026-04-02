# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import format_date


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

    def _auto_init(self):
        """
        Pre-create ALL M2M relation tables declared on boq.boq BEFORE the
        ORM's super()._auto_init() runs — same pattern as boq.order.line.

        Tables pre-created:
          boq_boq_purchase_order_rel — rfq_ids     M2M ↔ purchase.order
          boq_boq_category_rel       — category_ids M2M ↔ boq.category

        This prevents psycopg2.errors.UndefinedTable from bubbling up to the
        JSON-RPC layer and appearing as "Odoo Server Error" on the dashboard
        when get_dashboard_stats() tries to query boq_boq_purchase_order_rel
        on a server that has not been upgraded with -u yet.
        """
        cr = self.env.cr

        # rfq_ids M2M — queried directly in get_dashboard_stats / get_vendor_summary
        cr.execute("""
            CREATE TABLE IF NOT EXISTS boq_boq_purchase_order_rel (
                boq_id      INTEGER NOT NULL,
                purchase_id INTEGER NOT NULL,
                PRIMARY KEY (boq_id, purchase_id)
            )
        """)

        # category_ids M2M — needed by _compute_tab_flags on form load
        cr.execute("""
            CREATE TABLE IF NOT EXISTS boq_boq_category_rel (
                boq_id      INTEGER NOT NULL,
                category_id INTEGER NOT NULL,
                PRIMARY KEY (boq_id, category_id)
            )
        """)

        return super()._auto_init()

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
    # project_id: non-stored computed — uses project_name (existing column) as
    # backing storage so no new DB column is ever required on boq_boq.
    project_id = fields.Many2one(
        comodel_name='project.project',
        string='Project',
        compute='_compute_project_id',
        inverse='_inverse_project_id',
        store=False,
        help='Link this BOQ to an existing Odoo Project. '
             'The project name is persisted in the Project Name field.',
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

    # Per-category reference fields used in view context for default_category_id
    electrical_category_id = fields.Many2one('boq.category', compute='_compute_category_refs')
    civil_category_id      = fields.Many2one('boq.category', compute='_compute_category_refs')
    lighting_category_id   = fields.Many2one('boq.category', compute='_compute_category_refs')
    plumbing_category_id   = fields.Many2one('boq.category', compute='_compute_category_refs')
    hvac_category_id       = fields.Many2one('boq.category', compute='_compute_category_refs')
    finishing_category_id  = fields.Many2one('boq.category', compute='_compute_category_refs')

    @api.depends('project_name')
    def _compute_project_id(self):
        Project = self.env['project.project']
        for rec in self:
            if rec.project_name:
                rec.project_id = Project.search(
                    [('name', '=', rec.project_name)], limit=1
                )
            else:
                rec.project_id = False

    def _inverse_project_id(self):
        for rec in self:
            if rec.project_id:
                rec.project_name = rec.project_id.name

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

    def _compute_category_refs(self):
        cats = {c.code: c for c in self.env['boq.category'].search([])}
        empty = self.env['boq.category']
        for rec in self:
            rec.electrical_category_id = cats.get('electrical', empty)
            rec.civil_category_id      = cats.get('civil',      empty)
            rec.lighting_category_id   = cats.get('lighting',   empty)
            rec.plumbing_category_id   = cats.get('plumbing',   empty)
            rec.hvac_category_id       = cats.get('hvac',       empty)
            rec.finishing_category_id  = cats.get('finishing',  empty)

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
        compute='_compute_totals', store=False,
        currency_field='currency_id',
    )
    civil_total = fields.Monetary(
        compute='_compute_totals', store=False,
        currency_field='currency_id',
    )
    lighting_total = fields.Monetary(
        compute='_compute_totals', store=False,
        currency_field='currency_id',
    )
    plumbing_total = fields.Monetary(
        compute='_compute_totals', store=False,
        currency_field='currency_id',
    )
    hvac_total = fields.Monetary(
        compute='_compute_totals', store=False,
        currency_field='currency_id',
    )
    finishing_total = fields.Monetary(
        compute='_compute_totals', store=False,
        currency_field='currency_id',
    )
    total_amount = fields.Monetary(
        string='Untaxed Amount',
        compute='_compute_totals',
        store=False,
        currency_field='currency_id',
    )
    total_tax = fields.Monetary(
        string='Total Tax',
        compute='_compute_totals',
        store=False,
        currency_field='currency_id',
    )
    grand_total = fields.Monetary(
        string='Grand Total',
        compute='_compute_totals',
        store=False,
        currency_field='currency_id',
    )
    line_count = fields.Integer(
        string='Lines',
        compute='_compute_totals',
        store=False,
    )

    # ── Linked Purchase RFQs ──────────────────────────────────────────────
    rfq_ids = fields.Many2many(
        comodel_name='purchase.order',
        relation='boq_boq_purchase_order_rel',
        column1='boq_id',
        column2='purchase_id',
        string='RFQs / Purchase Orders',
        copy=False,
    )
    rfq_count = fields.Integer(
        string='RFQs',
        compute='_compute_rfq_count',
        store=True,
    )

    @api.depends('rfq_ids')
    def _compute_rfq_count(self):
        for rec in self:
            rec.rfq_count = len(rec.rfq_ids)

    # ── _compute_totals ────────────────────────────────────────────────────
    # IMPORTANT: Only depend on stored `line_ids.*` fields.
    # tax_amount on boq.order.line is store=False — using a non-stored computed
    # field in @api.depends causes Odoo ORM to silently drop ALL triggers in the
    # decorator, making every total show 0.  We therefore compute taxes inline
    # here using tax_ids.compute_all() directly, mirroring _compute_total_value
    # on the line, so no non-stored field is ever accessed through mapped().
    @api.depends('line_ids.subtotal', 'line_ids.tax_ids', 'line_ids.qty',
                 'line_ids.unit_price', 'line_ids.discount', 'line_ids.category_id',
                 'partner_id')
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

            subtotal = sum(lines.mapped('subtotal'))

            # ── Compute taxes inline (avoid non-stored tax_amount) ──────
            # Mirrors _compute_total_value logic on boq.order.line.
            tax_total = 0.0
            for line in lines:
                if line.tax_ids and (line.qty or line.unit_price):
                    price_after_disc = line.unit_price * (
                        1.0 - (line.discount or 0.0) / 100.0
                    )
                    taxes = line.tax_ids.compute_all(
                        price_after_disc,
                        currency=line.currency_id or None,
                        quantity=line.qty,
                        product=line.product_id or None,
                        partner=rec.partner_id or None,
                    )
                    tax_total += (
                        taxes['total_included'] - taxes['total_excluded']
                    )

            rec.total_amount = subtotal
            rec.total_tax    = tax_total
            rec.grand_total  = subtotal + tax_total
            rec.line_count   = len(lines)

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

    # ── Create RFQ ────────────────────────────────────────────────────────
    def action_create_rfq(self):
        """
        Group BOQ lines by vendor and create one RFQ (purchase.order)
        per vendor. Lines with no vendor are skipped.
        After creation, opens the resulting RFQ(s).
        """
        self.ensure_one()

        if not self.line_ids:
            raise UserError(_('Cannot create RFQ: the BOQ has no line items.'))

        # Build vendor → lines mapping
        vendor_lines = {}
        for line in self.line_ids:
            for vendor in line.vendor_ids:
                vendor_lines.setdefault(vendor.id, []).append(line)

        if not vendor_lines:
            raise UserError(_(
                'No vendors mapped on any line item.\n'
                'Please assign at least one Preferred Vendor to a line item first.'
            ))

        PO = self.env['purchase.order']
        POLine = self.env['purchase.order.line']
        today = fields.Datetime.now()
        created_orders = PO

        for vendor_id, lines in vendor_lines.items():
            po = PO.create({
                'partner_id': vendor_id,
                'origin': '%s — %s' % (self.name, self.project_name or '-'),
            })
            for line in lines:
                POLine.create({
                    'order_id': po.id,
                    'product_id': line.product_id.id,
                    'name': line.product_name or line.product_id.display_name,
                    'product_qty': line.qty,
                    'product_uom_id': line.uom_id.id or line.product_id.uom_po_id.id,
                    'price_unit': 0,
                    'date_planned': today,
                })
            created_orders |= po

        # Link newly created RFQs to this BOQ
        self.rfq_ids = [(4, po.id) for po in created_orders]

        # Notify & redirect
        if len(created_orders) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Request for Quotation'),
                'res_model': 'purchase.order',
                'res_id': created_orders.id,
                'view_mode': 'form',
                'target': 'current',
            }
        return {
            'type': 'ir.actions.act_window',
            'name': _('%d RFQs Created') % len(created_orders),
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', created_orders.ids)],
            'target': 'current',
        }

    def action_view_rfqs(self):
        """Open linked RFQs / Purchase Orders from the smart button."""
        self.ensure_one()
        if not self.rfq_count:
            return
        if self.rfq_count == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('RFQ'),
                'res_model': 'purchase.order',
                'res_id': self.rfq_ids.id,
                'view_mode': 'form',
                'target': 'current',
            }
        return {
            'type': 'ir.actions.act_window',
            'name': _('RFQs — %s') % self.name,
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.rfq_ids.ids)],
            'target': 'current',
        }

    # ── Model helper ──────────────────────────────────────────────────────
    @api.model
    def _get_category_id(self, code):
        """Return the ID of the category with the given code."""
        cat = self.env['boq.category'].search(
            [('code', '=', code)], limit=1
        )
        return cat.id if cat else False

    # ═══════════════════════════════════════════════════════════════════════
    # DASHBOARD DATA METHODS  (Task 4)
    # Called via RPC from the BoqDashboard OWL component.
    # ═══════════════════════════════════════════════════════════════════════

    @api.model
    def get_dashboard_stats(self):
        """
        Return top-level aggregate stats for the BOQ dashboard header cards.

        Every section is individually wrapped in try/except so a missing DB
        table or column (e.g. before a module upgrade) NEVER propagates to
        the JSON-RPC layer as "Odoo Server Error".  Instead the dashboard
        loads with zeros / empty data and the user can retry after upgrade.
        """
        # ── BOQ records ──────────────────────────────────────────────────
        try:
            company_domain = [('company_id', '=', self.env.company.id)]
            boqs = self.search(company_domain)
        except Exception:
            boqs = self.env['boq.boq']

        # ── RFQs linked to BOQs (direct M2M SQL — boq_id is non-stored) ─
        rfqs = self.env['purchase.order']
        if boqs.ids:
            try:
                self.env.cr.execute(
                    "SELECT purchase_id FROM boq_boq_purchase_order_rel WHERE boq_id IN %s",
                    (tuple(boqs.ids),)
                )
                rfq_ids = [r[0] for r in self.env.cr.fetchall()]
                if rfq_ids:
                    rfqs = self.env['purchase.order'].browse(rfq_ids)
            except Exception:
                pass

        # ── State breakdown ───────────────────────────────────────────────
        state_counts = {}
        try:
            for state, _label in self._fields['state'].selection:
                state_counts[state] = len(
                    boqs.filtered(lambda b, s=state: b.state == s)
                )
        except Exception:
            state_counts = {}

        # ── BOQ monetary totals (non-stored computed — may fail if M2M
        #    tables not yet created; fall back to zero gracefully) ─────────
        total_value = total_tax = grand_total = 0.0
        try:
            total_value = sum(boqs.mapped('total_amount'))
            total_tax   = sum(boqs.mapped('total_tax'))
            grand_total = sum(boqs.mapped('grand_total'))
        except Exception:
            # Attempt line-by-line fallback (only stored field: subtotal)
            try:
                for boq in boqs:
                    for line in boq.line_ids:
                        total_value += line.subtotal or 0.0
                grand_total = total_value
            except Exception:
                pass

        # ── RFQ totals ────────────────────────────────────────────────────
        rfq_total = rfq_tax = 0.0
        rfq_draft_count = 0
        try:
            rfq_total       = sum(rfqs.mapped('amount_total'))
            rfq_tax         = sum(rfqs.mapped('amount_tax'))
            rfq_draft_count = len(rfqs.filtered(lambda r: r.state in ('draft', 'sent')))
        except Exception:
            pass

        # ── Currency ──────────────────────────────────────────────────────
        try:
            currency_symbol   = self.env.company.currency_id.symbol or '$'
            currency_position = self.env.company.currency_id.position or 'before'
        except Exception:
            currency_symbol   = '$'
            currency_position = 'before'

        return {
            'total_boqs':       len(boqs),
            'total_value':      total_value,
            'total_tax':        total_tax,
            'grand_total':      grand_total,
            'state_counts':     state_counts,
            'total_rfqs':       len(rfqs),
            'rfq_draft':        rfq_draft_count,
            'rfq_total_value':  rfq_total,
            'rfq_total_tax':    rfq_tax,
            'currency_symbol':  currency_symbol,
            'currency_position': currency_position,
        }

    @api.model
    def get_vendor_summary(self):
        """
        Return vendor-wise RFQ summary for dashboard kanban cards.

        Each entry includes:
          • vendor name, email, RFQ count, total value / tax
          • average vendor rating (Task 2 + 3) — batch-fetched in one query
          • margin % computed from BOQ lines
          • project names, BOQ states, RFQ states

        Every section is wrapped in try/except so missing DB tables or columns
        (pre-upgrade state) never crash the dashboard.
        """
        # ── BOQ records ──────────────────────────────────────────────────
        try:
            company_domain = [('company_id', '=', self.env.company.id)]
            boqs = self.search(company_domain)
        except Exception:
            boqs = self.env['boq.boq']

        # ── M2M: boq → purchase.order (non-stored boq_id on PO) ─────────
        rfq_boq_map = {}
        if boqs.ids:
            try:
                self.env.cr.execute(
                    """
                    SELECT purchase_id, boq_id
                      FROM boq_boq_purchase_order_rel
                     WHERE boq_id IN %s
                    """,
                    (tuple(boqs.ids),)
                )
                rfq_boq_map = {row[0]: row[1] for row in self.env.cr.fetchall()}
            except Exception:
                rfq_boq_map = {}

        rfqs = (
            self.env['purchase.order'].browse(list(rfq_boq_map.keys()))
            if rfq_boq_map
            else self.env['purchase.order']
        )

        # ── BOQ project / state info map ─────────────────────────────────
        boq_info = {}
        try:
            for b in boqs:
                boq_info[b.id] = {
                    'project_name': b.project_name or (b.project_id.name if b.project_id else '') or '—',
                    'state': b.state,
                }
        except Exception:
            boq_info = {}

        # ── Build per-vendor aggregates from RFQs ────────────────────────
        _rfq_state_labels = {
            'draft':      'RFQ',
            'sent':       'Sent',
            'to approve': 'To Approve',
            'purchase':   'PO',
            'done':       'Done',
            'cancel':     'Cancelled',
        }

        vendor_map = {}
        try:
            for rfq in rfqs:
                vid = rfq.partner_id.id
                if not vid:
                    continue
                if vid not in vendor_map:
                    partner = rfq.partner_id
                    vendor_map[vid] = {
                        'vendor_id':      vid,
                        'vendor_name':    partner.name or '—',
                        'vendor_email':   partner.email or '',
                        'rfq_count':      0,
                        'total_value':    0.0,
                        'total_tax':      0.0,
                        'states':         [],
                        'project_names':  [],
                        'rfq_states':     [],
                        # Task 2 + 3 — populated in batch-fetch below
                        'avg_rating':     0.0,
                        'rating_count':   0,
                        'rating_display': '—',
                    }
                entry = vendor_map[vid]
                entry['rfq_count']   += 1
                entry['total_value'] += rfq.amount_total or 0.0
                entry['total_tax']   += rfq.amount_tax  or 0.0

                state_label = _rfq_state_labels.get(rfq.state, rfq.state)
                if state_label not in entry['rfq_states']:
                    entry['rfq_states'].append(state_label)

                boq_id_val = rfq_boq_map.get(rfq.id)
                if boq_id_val and boq_id_val in boq_info:
                    bi = boq_info[boq_id_val]
                    if bi['project_name'] not in entry['project_names']:
                        entry['project_names'].append(bi['project_name'])
                    if bi['state'] not in entry['states']:
                        entry['states'].append(bi['state'])
        except Exception:
            pass

        # ── Task 2 + 3: Batch-fetch vendor ratings (one query, no N+1) ───
        #
        # We search purchase.order for ALL rated POs whose vendor is in our
        # vendor map — one round-trip for all vendors.
        # Wrapped in try/except: vendor_rating column may not exist yet on
        # a server that has not been upgraded with -u since the field was added.
        vendor_partner_ids = list(vendor_map.keys())
        if vendor_partner_ids:
            try:
                rated_pos = self.env['purchase.order'].search([
                    ('partner_id', 'in', vendor_partner_ids),
                    ('vendor_rating', '!=', False),
                ])
                rating_buckets = {}
                for rpo in rated_pos:
                    pid = rpo.partner_id.id
                    rating_buckets.setdefault(pid, []).append(int(rpo.vendor_rating))
                for pid, ratings in rating_buckets.items():
                    if pid in vendor_map:
                        avg    = round(sum(ratings) / len(ratings), 2)
                        filled = round(avg)
                        vendor_map[pid]['avg_rating']     = avg
                        vendor_map[pid]['rating_count']   = len(ratings)
                        vendor_map[pid]['rating_display'] = '★' * filled + '☆' * (5 - filled)
            except Exception:
                pass

        # ── Margin computation from BOQ lines (vendor_ids M2M) ───────────
        #
        # cost_price is a non-stored computed field on boq.order.line.
        # vendor_ids is a M2M that requires boq_order_line_vendor_rel.
        # Both accesses are protected by this try/except block.
        vendor_margins = {}
        try:
            for boq in boqs:
                for line in boq.line_ids:
                    for vendor in line.vendor_ids:
                        vid = vendor.id
                        if vid not in vendor_margins:
                            vendor_margins[vid] = {'total_sell': 0.0, 'total_cost': 0.0}
                        sell = (line.unit_price or 0.0) * (line.qty or 0.0) * (
                            1.0 - (line.discount or 0.0) / 100.0
                        )
                        try:
                            cost = (line.cost_price or 0.0) * (line.qty or 0.0)
                        except Exception:
                            cost = 0.0
                        vendor_margins[vid]['total_sell'] += sell
                        vendor_margins[vid]['total_cost'] += cost
        except Exception:
            pass

        # ── Assemble final result list ────────────────────────────────────
        result = []
        for vid, entry in vendor_map.items():
            margin_data = vendor_margins.get(vid, {'total_sell': 0.0, 'total_cost': 0.0})
            sell = margin_data['total_sell']
            cost = margin_data['total_cost']
            entry['margin_percent'] = round(
                ((sell - cost) / sell * 100) if sell > 0 else 0.0, 2
            )
            entry['project_names'] = ', '.join(entry['project_names']) or '—'
            entry['rfq_states']    = ', '.join(entry['rfq_states'])    or '—'
            entry['boq_states']    = ', '.join(entry['states'])        or '—'
            result.append(entry)

        result.sort(key=lambda x: x['total_value'], reverse=True)
        return result

    @api.model
    def get_vendor_boq_lines(self, vendor_id):
        """
        Return all BOQ order lines assigned to vendor_id so the dashboard
        Summary tab can show a line-level breakdown (like the BOQ form view).

        Non-stored computed fields (tax_amount, total_value, margin_percent,
        cost_price) are each individually try/except'd to prevent missing M2M
        tables from crashing this method.
        """
        try:
            partner = self.env['res.partner'].browse(vendor_id)
            if not partner.exists():
                return []
        except Exception:
            return []

        try:
            company_domain = [('company_id', '=', self.env.company.id)]
            boqs = self.search(company_domain)
        except Exception:
            return []

        rows = []
        for boq in boqs:
            try:
                lines = boq.line_ids
            except Exception:
                continue
            for line in lines:
                # Check if this vendor is in the line's vendor_ids M2M
                try:
                    if partner not in line.vendor_ids:
                        continue
                except Exception:
                    continue

                # Safely read non-stored fields individually
                try:
                    cost_price = line.cost_price
                except Exception:
                    cost_price = 0.0
                try:
                    tax_amount = line.tax_amount
                except Exception:
                    tax_amount = 0.0
                try:
                    total_value = line.total_value
                except Exception:
                    total_value = (line.subtotal or 0.0) + tax_amount
                try:
                    margin_pct = round(line.margin_percent, 2)
                except Exception:
                    margin_pct = 0.0
                try:
                    product_name = (
                        line.product_name
                        or (line.product_id.name if line.product_id else '—')
                    )
                except Exception:
                    product_name = '—'

                rows.append({
                    'boq_name':       boq.name or '—',
                    'product_name':   product_name,
                    'qty':            line.qty or 0.0,
                    'unit_price':     line.unit_price or 0.0,
                    'cost_price':     cost_price,
                    'discount':       line.discount or 0.0,
                    'subtotal':       line.subtotal or 0.0,
                    'tax_amount':     tax_amount,
                    'total_value':    total_value,
                    'margin_percent': margin_pct,
                })
        return rows
