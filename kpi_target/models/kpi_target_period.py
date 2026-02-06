# -*- coding: utf-8 -*-
from odoo import models, fields, api


class KpiTargetPeriod(models.Model):
    _name = 'kpi.target.period'
    _description = 'KPI Target Period'
    _order = 'date_from desc'

    name = fields.Char(string='Period Name', required=True)
    period_type = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
    ], string='Period Type', required=True, default='monthly')
    date_from = fields.Date(string='Start Date', required=True)
    date_to = fields.Date(string='End Date', required=True)
    active = fields.Boolean(string='Active', default=True)
    target_ids = fields.One2many('kpi.target', 'period_id', string='Targets')
    target_count = fields.Integer(string='Target Count', compute='_compute_target_count')

    @api.depends('target_ids')
    def _compute_target_count(self):
        for record in self:
            record.target_count = len(record.target_ids)

    def action_view_targets(self):
        self.ensure_one()
        return {
            'name': 'KPI Targets',
            'type': 'ir.actions.act_window',
            'res_model': 'kpi.target',
            'view_mode': 'tree,form',
            'domain': [('period_id', '=', self.id)],
            'context': {'default_period_id': self.id},
        }
