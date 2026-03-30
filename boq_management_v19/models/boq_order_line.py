# -*- coding: utf-8 -*-
from odoo import models, fields, api


class BoqOrderLine(models.Model):
    """
    Individual BOQ line item within a work category.
    Captures product, quantity, type and pricing.
    """
    _name = 'boq.order.line'
    _description = 'BOQ Order Line'
    _order = 'sequence asc, id asc'

    # ── Relationships ────────────────────────────────────────────────────
    boq_id = fields.Many2one(
        comodel_name='boq.boq',
        string='BOQ',
        required=True,
        ondelete='cascade',
        index=True,
    )
    category_id = fields.Many2one(
        comodel_name='boq.category',
        string='Work Category',
        required=True,
        ondelete='restrict',
        index=True,
    )
    company_id = fields.Many2one(
        related='boq_id.company_id',
        store=True,
        index=True,
    )

    # ── Sequence / ordering ───────────────────────────────────────────────
    sequence = fields.Integer(string='#', default=10)

    # ── Product ───────────────────────────────────────────────────────────
    product_id = fields.Many2one(
        comodel_name='product.product',
        string='Product / Material',
        required=True,
        change_default=True,
        index=True,
    )
    product_name = fields.Char(
        string='Description',
        compute='_compute_from_product',
        store=True,
        readonly=False,
        precompute=True,
    )
    product_type = fields.Selection(
        selection=[
            ('material',    'Material'),
            ('labour',      'Labour'),
            ('equipment',   'Equipment'),
            ('subcontract', 'Subcontract'),
            ('other',       'Other'),
        ],
        string='Type',
        required=True,
        default='material',
    )

    # ── UoM ───────────────────────────────────────────────────────────────
    uom_id = fields.Many2one(
        comodel_name='uom.uom',
        string='Unit of Measure',
        compute='_compute_from_product',
        store=True,
        readonly=False,
        precompute=True,
    )
    # ── Quantity & Price ──────────────────────────────────────────────────
    qty = fields.Float(
        string='Quantity',
        required=True,
        default=1.0,
        digits='Product Unit of Measure',
    )
    unit_price = fields.Float(
        string='Unit Price',
        digits='Product Price',
        default=0.0,
    )
    discount = fields.Float(
        string='Disc. %',
        digits='Discount',
        default=0.0,
    )
    subtotal = fields.Float(
        string='Subtotal',
        compute='_compute_subtotal',
        store=True,
        digits='Product Price',
        precompute=True,
    )
    currency_id = fields.Many2one(
        related='boq_id.currency_id',
        store=True,
    )

    # ── Preferred Vendors (Many2many → res.partner, filtered to vendors) ──
    vendor_ids = fields.Many2many(
        comodel_name='res.partner',
        relation='boq_order_line_vendor_rel',
        column1='line_id',
        column2='partner_id',
        string='Preferred Vendors',
        domain=[('supplier_rank', '>', 0)],
        help='Select one or more vendors for this line. '
             '"Create RFQ" will generate a purchase RFQ per vendor.',
    )

    # ── Tax / Total / Margin (no DB columns — all non-stored computed) ────
    # tax_ids Many2many removed: its relation table requires a module upgrade.
    # tax_amount = 0 and total_value = subtotal until upgrade is run.
    tax_amount = fields.Float(
        string='Tax Amount',
        compute='_compute_total_value',
        store=False,
        digits='Product Price',
    )
    total_value = fields.Float(
        string='Total (incl. Tax)',
        compute='_compute_total_value',
        store=False,
        digits='Product Price',
        help='Equal to Subtotal until taxes are configured after module upgrade.',
    )

    # ── Cost & Margin ──────────────────────────────────────────────────────
    cost_price = fields.Float(
        string='Cost Price',
        compute='_compute_from_product',
        store=False,
        readonly=False,
        digits='Product Price',
        help='Unit cost from product standard price.',
    )
    margin_percent = fields.Float(
        string='Margin %',
        compute='_compute_margin',
        store=False,
        digits='Discount',
        help='Gross margin percentage: ((Unit Price - Cost) / Unit Price) × 100.',
    )

    # ── Notes ─────────────────────────────────────────────────────────────
    notes = fields.Char(string='Remarks')

    # ── Computes ──────────────────────────────────────────────────────────
    @api.depends('product_id')
    def _compute_from_product(self):
        for line in self:
            if line.product_id:
                line.product_name = line.product_id.display_name
                line.uom_id = line.product_id.uom_id
                line.cost_price = line.product_id.standard_price or 0.0
            else:
                line.product_name = False
                line.uom_id = False
                line.cost_price = 0.0

    @api.depends('qty', 'unit_price', 'discount')
    def _compute_subtotal(self):
        for line in self:
            base = line.qty * line.unit_price
            line.subtotal = base * (1.0 - line.discount / 100.0)

    @api.depends('subtotal')
    def _compute_total_value(self):
        # tax_ids removed (relation table requires module upgrade).
        # total_value mirrors subtotal; tax_amount is 0 until upgrade.
        for line in self:
            line.tax_amount = 0.0
            line.total_value = line.subtotal

    @api.depends('unit_price', 'discount', 'cost_price')
    def _compute_margin(self):
        for line in self:
            selling = line.unit_price * (1.0 - line.discount / 100.0)
            if selling > 0:
                line.margin_percent = ((selling - (line.cost_price or 0.0)) / selling) * 100.0
            else:
                line.margin_percent = 0.0

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.unit_price = self.product_id.lst_price or self.product_id.standard_price
