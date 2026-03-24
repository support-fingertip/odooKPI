# -*- coding: utf-8 -*-
from odoo import models, fields, api


class BoqOrderLine(models.Model):
    """
    Individual line item within a BOQ category tab.
    Captures the product, quantity and type of work.
    """
    _name = 'boq.order.line'
    _description = 'BOQ Order Line'
    _order = 'sequence, id'

    # ── Relationships ────────────────────────────────────────────────────────
    boq_id = fields.Many2one(
        comodel_name='boq.boq',
        string='BOQ',
        required=True,
        ondelete='cascade',
        index=True,
    )
    category_id = fields.Many2one(
        comodel_name='boq.category',
        string='Category',
        required=True,
        ondelete='restrict',
        index=True,
    )

    # ── Core fields ──────────────────────────────────────────────────────────
    sequence = fields.Integer(string='#', default=10)

    product_id = fields.Many2one(
        comodel_name='product.product',
        string='Product / Material',
        required=True,
        domain=[('purchase_ok', '=', True)],
        change_default=True,
    )
    product_name = fields.Char(
        string='Description',
        compute='_compute_product_name',
        store=True,
        readonly=False,
    )
    product_type = fields.Selection(
        selection=[
            ('material', 'Material'),
            ('labour', 'Labour'),
            ('equipment', 'Equipment'),
            ('subcontract', 'Subcontract'),
            ('other', 'Other'),
        ],
        string='Type',
        default='material',
        required=True,
    )
    uom_id = fields.Many2one(
        comodel_name='uom.uom',
        string='Unit',
        related='product_id.uom_id',
        store=True,
        readonly=True,
    )
    qty = fields.Float(
        string='Quantity',
        default=1.0,
        digits='Product Unit of Measure',
    )
    unit_price = fields.Float(
        string='Unit Price',
        digits='Product Price',
        default=0.0,
    )
    subtotal = fields.Float(
        string='Subtotal',
        compute='_compute_subtotal',
        store=True,
        digits='Product Price',
    )
    notes = fields.Char(string='Notes')

    # ── Computes ─────────────────────────────────────────────────────────────
    @api.depends('product_id')
    def _compute_product_name(self):
        for line in self:
            if line.product_id:
                line.product_name = line.product_id.display_name
            else:
                line.product_name = False

    @api.depends('qty', 'unit_price')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.qty * line.unit_price

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.unit_price = self.product_id.standard_price
