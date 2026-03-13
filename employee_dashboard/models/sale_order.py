# -*- coding: utf-8 -*-
from odoo import models, fields, api


class SchemeMaster(models.Model):
    """Admin-configurable scheme/promotion master."""
    _name = 'scheme.master'
    _description = 'Scheme Master'
    _order = 'date_from desc'

    name = fields.Char(string='Scheme Name', required=True)
    code = fields.Char(string='Code')
    scheme_type = fields.Selection([
        ('discount', 'Discount %'),
        ('free_qty', 'Free Qty (Buy X Get Y)'),
        ('fixed_price', 'Fixed Price'),
        ('cashback', 'Cashback'),
    ], string='Type', required=True, default='discount')
    discount_pct = fields.Float(string='Discount %', digits=(5, 2))
    buy_qty = fields.Float(string='Buy Qty')
    free_qty = fields.Float(string='Free Qty')
    cashback_amount = fields.Monetary(string='Cashback Amount', currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id)
    product_ids = fields.Many2many('product.product', string='Applicable Products')
    date_from = fields.Date(string='Valid From', required=True)
    date_to = fields.Date(string='Valid To', required=True)
    active = fields.Boolean(string='Active', default=True)
    notes = fields.Text(string='Notes')

    def is_active_today(self):
        from datetime import date
        today = date.today()
        return self.active and self.date_from <= today <= self.date_to


class MustSellProduct(models.Model):
    """Admin-configured Must Sell / Focus Sell products."""
    _name = 'must.sell.product'
    _description = 'Must Sell / Focus Sell Product'
    _order = 'sequence, id'

    sequence = fields.Integer(string='Sequence', default=10)
    product_id = fields.Many2one(
        'product.product', string='Product', required=True, index=True)
    tag_type = fields.Selection([
        ('must_sell', 'Must Sell'),
        ('focus_sell', 'Focus Sell'),
    ], string='Tag', required=True, default='must_sell')
    date_from = fields.Date(string='Valid From')
    date_to = fields.Date(string='Valid To')
    active = fields.Boolean(string='Active', default=True)
    notes = fields.Text(string='Notes')

    _sql_constraints = [
        ('unique_product_tag', 'UNIQUE(product_id, tag_type)',
         'A product can only be tagged once per type.')
    ]


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    visit_id = fields.Many2one('visit.model', string='Visit', related='order_id.visit_id', store=True, readonly=True)
    # Must Sell / Focus Sell tagging (auto-populated, overrideable)
    product_tag = fields.Selection([
        ('must_sell', 'Must Sell'),
        ('focus_sell', 'Focus Sell'),
        ('normal', 'Normal'),
    ], string='Product Tag', default='normal')
    # Applied scheme reference
    scheme_id = fields.Many2one('scheme.master', string='Applied Scheme')
    scheme_discount = fields.Float(string='Scheme Discount %', digits=(5, 2))

    @api.onchange('product_id')
    def _onchange_product_tag(self):
        """Auto-tag Must Sell / Focus Sell and apply active scheme on product change."""
        if not self.product_id:
            self.product_tag = 'normal'
            self.scheme_id = False
            self.scheme_discount = 0.0
            return

        # --- Must Sell / Focus Sell tag ---
        from datetime import date
        today = date.today()
        tag_record = self.env['must.sell.product'].sudo().search([
            ('product_id', '=', self.product_id.id),
            ('active', '=', True),
            '|', ('date_from', '=', False), ('date_from', '<=', today),
            '|', ('date_to', '=', False), ('date_to', '>=', today),
        ], limit=1, order='tag_type asc')
        self.product_tag = tag_record.tag_type if tag_record else 'normal'

        # --- Scheme auto-application ---
        scheme = self.env['scheme.master'].sudo().search([
            ('active', '=', True),
            ('scheme_type', '=', 'discount'),
            ('date_from', '<=', today),
            ('date_to', '>=', today),
            ('product_ids', 'in', [self.product_id.id]),
        ], limit=1, order='date_from desc')

        if scheme:
            self.scheme_id = scheme.id
            self.scheme_discount = scheme.discount_pct
            self.discount = scheme.discount_pct
        else:
            self.scheme_id = False
            self.scheme_discount = 0.0


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    visit_id = fields.Many2one('visit.model', string='Visit', ondelete='set null')
    beat_id = fields.Many2one('beat.module', string='Beat', related='visit_id.beat_id', store=True, readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        for order in orders:
            if self._context.get('visit_id') and not order.visit_id:
                order.visit_id = self._context.get('visit_id')
        orders.filtered(lambda o: o.state in ('sale', 'done'))._trigger_kpi_recompute()
        return orders

    def write(self, vals):
        result = super(SaleOrder, self).write(vals)
        if vals.get('state') in ('sale', 'done', 'cancel') or 'user_id' in vals:
            self._trigger_kpi_recompute()
        return result

    def _trigger_kpi_recompute(self):
        """Force recompute of KPI actuals for affected employees."""
        if 'kpi.target' not in self.env:
            return

        # Collect employees via salesperson user_id
        employees = self.env['hr.employee']
        user_ids = self.mapped('user_id').ids
        if user_ids:
            employees |= self.env['hr.employee'].sudo().search([
                ('user_id', 'in', user_ids)
            ])

        # Also collect employees via visit linkage (covers orders where the
        # salesperson is a default/admin user rather than the actual employee)
        visit_employee_ids = self.sudo().mapped('visit_id.employee_id').ids
        if visit_employee_ids:
            employees |= self.env['hr.employee'].sudo().browse(visit_employee_ids)

        if not employees:
            return

        kpi_targets = self.env['kpi.target'].sudo().search([
            ('employee_id', 'in', employees.ids),
        ])
        if not kpi_targets:
            return

        # Directly call compute methods so values are recalculated from live
        # sale.order data and written to DB on transaction flush/commit.
        kpi_targets._compute_actuals()
        kpi_targets.flush_recordset([
            'actual_orders', 'actual_order_amount', 'actual_visits',
            'actual_new_dealers', 'actual_payment_collected', 'actual_complaints_solved',
        ])
        kpi_targets._compute_achievements()
        kpi_targets.flush_recordset([
            'achievement_orders', 'achievement_visits', 'achievement_new_dealers',
            'achievement_payment_collected', 'achievement_complaints_solved',
            'overall_achievement',
        ])
