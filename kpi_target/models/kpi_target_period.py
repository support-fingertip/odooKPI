# -*- coding: utf-8 -*-
from odoo import models, fields, api
from dateutil.relativedelta import relativedelta


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

    target_ids = fields.One2many('kpi.target', 'period_id', string='Individual Targets')
    manager_target_ids = fields.One2many('kpi.manager.target', 'period_id', string='Team Targets')

    target_count = fields.Integer(string='Individual Targets', compute='_compute_counts', store=True)
    team_target_count = fields.Integer(string='Team Targets', compute='_compute_counts', store=True)

    @api.depends('target_ids', 'manager_target_ids')
    def _compute_counts(self):
        for record in self:
            record.target_count = len(record.target_ids)
            record.team_target_count = len(record.manager_target_ids)

    @api.onchange('period_type', 'date_from')
    def _onchange_auto_fill(self):
        """Auto-generate period name (if empty) and end date based on type and start date."""
        if self.period_type and self.date_from:
            if self.period_type == 'monthly':
                if not self.name:
                    self.name = self.date_from.strftime('%B %Y')
                self.date_to = self.date_from + relativedelta(months=1, days=-1)
            elif self.period_type == 'quarterly':
                if not self.name:
                    q = (self.date_from.month - 1) // 3 + 1
                    self.name = f'Q{q} {self.date_from.year}'
                self.date_to = self.date_from + relativedelta(months=3, days=-1)
            elif self.period_type == 'yearly':
                if not self.name:
                    self.name = str(self.date_from.year)
                self.date_to = self.date_from + relativedelta(years=1, days=-1)

    def action_view_targets(self):
        self.ensure_one()
        return {
            'name': f'Individual Targets – {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'kpi.target',
            'view_mode': 'list,form',
            'domain': [('period_id', '=', self.id)],
            'context': {'default_period_id': self.id},
        }

    def action_view_team_targets(self):
        self.ensure_one()
        return {
            'name': f'Team Targets – {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'kpi.manager.target',
            'view_mode': 'list,form',
            'domain': [('period_id', '=', self.id)],
            'context': {'default_period_id': self.id},
        }
