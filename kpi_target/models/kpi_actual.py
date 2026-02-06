# -*- coding: utf-8 -*-
from odoo import models, fields


class KpiActual(models.Model):
    _name = 'kpi.actual'
    _description = 'KPI Actual'
    _order = 'date desc'

    target_id = fields.Many2one('kpi.target', string='Target', required=True, ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', string='Employee', related='target_id.employee_id', store=True)
    kpi_type = fields.Selection([
        ('sales', 'Sales'),
        ('visits', 'Visits'),
        ('new_dealers', 'New Dealers'),
        ('payment_collected', 'Payment Collected'),
        ('complaints_solved', 'Complaints Solved'),
    ], string='KPI Type', required=True)
    value = fields.Float(string='Value', required=True)
    date = fields.Date(string='Date', required=True, default=fields.Date.context_today)
    notes = fields.Text(string='Notes')
