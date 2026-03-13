# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class VisitStockLedger(models.Model):
    """Stock update captured during a customer visit."""
    _name = 'visit.stock.ledger'
    _description = 'Visit Stock Ledger'
    _order = 'visit_id desc, id'

    visit_id = fields.Many2one(
        'visit.model', string='Visit', required=True, ondelete='cascade', index=True)
    partner_id = fields.Many2one(
        related='visit_id.partner_id', string='Customer', store=True, readonly=True)
    employee_id = fields.Many2one(
        related='visit_id.employee_id', string='Employee', store=True, readonly=True)
    date = fields.Date(
        string='Date', default=fields.Date.today, required=True)

    product_id = fields.Many2one(
        'product.product', string='Product', required=True, index=True)
    product_name = fields.Char(
        string='Product Name', compute='_compute_product_name', store=True, readonly=True)

    @api.depends('product_id')
    def _compute_product_name(self):
        """Fetch product name with lang=False to avoid jsonb_path_query_first errors
        when the product.template.name column has not yet been migrated to jsonb."""
        for rec in self:
            if rec.product_id:
                rec.product_name = rec.product_id.with_context(lang=False).name
            else:
                rec.product_name = ''

    opening_stock = fields.Float(string='Opening Stock', default=0.0)
    closing_stock = fields.Float(string='Closing Stock', default=0.0)
    damaged_stock = fields.Float(string='Damaged / Expired', default=0.0)
    suggested_order = fields.Float(
        string='Suggested Order Qty', compute='_compute_suggested_order', store=True)

    notes = fields.Text(string='Notes')

    @api.depends('opening_stock', 'closing_stock', 'damaged_stock')
    def _compute_suggested_order(self):
        for rec in self:
            sold = max(rec.opening_stock - rec.closing_stock - rec.damaged_stock, 0.0)
            rec.suggested_order = sold

    @api.constrains('opening_stock', 'closing_stock', 'damaged_stock')
    def _check_stock_values(self):
        for rec in self:
            if rec.opening_stock < 0 or rec.closing_stock < 0 or rec.damaged_stock < 0:
                raise ValidationError("Stock quantities cannot be negative.")

    @api.model
    def save_stock_from_visit(self, visit_id, stock_lines):
        """
        Save stock update lines for a visit atomically.
        Removes existing lines and creates fresh ones.
        Uses sudo to bypass unlink restrictions on user-level access.

        :param visit_id: int, ID of the visit.model record
        :param stock_lines: list of dicts with keys:
            product_id, opening_stock, closing_stock, damaged_stock
        :return: dict with count of saved lines
        """
        visit = self.env['visit.model'].browse(visit_id)
        if not visit.exists():
            raise UserError("Visit not found.")

        # Use lang=False to bypass Odoo 18 jsonb translation lookup on
        # product.name (avoids "jsonb_path_query_first(varchar, unknown)" error
        # when the DB column type hasn't been migrated to jsonb yet).
        env_notrans = self.sudo().with_context(lang=False)

        # Delete existing stock lines for this visit using sudo
        existing = env_notrans.search([('visit_id', '=', visit_id)])
        if existing:
            existing.sudo().unlink()

        today = fields.Date.today()
        created_count = 0
        vals_list = []
        for line in stock_lines:
            product_id = line.get('product_id')
            if not product_id:
                continue
            vals_list.append({
                'visit_id': visit_id,
                'product_id': int(product_id),
                'date': today,
                'opening_stock': float(line.get('opening_stock', 0.0)),
                'closing_stock': float(line.get('closing_stock', 0.0)),
                'damaged_stock': float(line.get('damaged_stock', 0.0)),
            })

        if vals_list:
            env_notrans.create(vals_list)
            created_count = len(vals_list)

        _logger.info("Saved %d stock line(s) for visit %s", created_count, visit_id)
        return {'saved': created_count}
