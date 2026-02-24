# -*- coding: utf-8 -*-
from odoo import models, fields, api

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    visit_id = fields.Many2one('visit.model', string='Visit', related='order_id.visit_id', store=True, readonly=True)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    visit_id = fields.Many2one('visit.model', string='Visit', ondelete='set null')
    beat_id = fields.Many2one('beat.module', string='Beat', related='visit_id.beat_id', store=True, readonly=True)

    @api.model
    def create(self, vals):
        order = super(SaleOrder, self).create(vals)
       
        if self._context.get('visit_id') and not order.visit_id:
            order.visit_id = self._context.get('visit_id')
        return order

    def write(self, vals):
        result = super(SaleOrder, self).write(vals)
        if vals.get('state') in ('sale', 'done'):
            self._trigger_kpi_recompute()
        return result

    def _trigger_kpi_recompute(self):
        """Invalidate stored KPI actuals so they get recomputed on next access."""
        if 'kpi.target' not in self.env:
            return
        for order in self:
            if not order.user_id:
                continue
            employee = self.env['hr.employee'].search([
                ('user_id', '=', order.user_id.id)
            ], limit=1)
            if not employee:
                continue
            kpi_targets = self.env['kpi.target'].search([
                ('employee_id', '=', employee.id),
            ])
            if kpi_targets:
                kpi_targets._compute_actuals()
                kpi_targets._compute_achievements()