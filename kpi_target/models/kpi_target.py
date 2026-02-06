# -*- coding: utf-8 -*-
from odoo import models, fields, api


class KpiTarget(models.Model):
    _name = 'kpi.target'
    _description = 'KPI Target'
    _sql_constraints = [
        ('unique_employee_period', 'UNIQUE(employee_id, period_id)', 'Each employee can have only one target per period!')
    ]

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    period_id = fields.Many2one('kpi.target.period', string='Period', required=True)
    period_type = fields.Selection(related='period_id.period_type', string='Period Type', store=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
    ], string='State', default='draft')
    item_ids = fields.One2many('kpi.target.item', 'target_id', string='Target Items')
    actual_ids = fields.One2many('kpi.actual', 'target_id', string='Actual Entries')

    # Denormalized target fields (editable)
    target_sales = fields.Float(string='Target Sales', default=0.0)
    target_visits = fields.Float(string='Target Visits', default=0.0)
    target_new_dealers = fields.Float(string='Target New Dealers', default=0.0)
    target_payment_collected = fields.Float(string='Target Payment Collected', default=0.0)
    target_complaints_solved = fields.Float(string='Target Complaints Solved', default=0.0)

    # Computed actual fields (readonly)
    actual_sales = fields.Float(string='Actual Sales', compute='_compute_actuals', store=True)
    actual_visits = fields.Float(string='Actual Visits', compute='_compute_actuals', store=True)
    actual_new_dealers = fields.Float(string='Actual New Dealers', compute='_compute_actuals', store=True)
    actual_payment_collected = fields.Float(string='Actual Payment Collected', compute='_compute_actuals', store=True)
    actual_complaints_solved = fields.Float(string='Actual Complaints Solved', compute='_compute_actuals', store=True)

    # Computed achievement % fields
    achievement_sales = fields.Float(string='Achievement Sales %', compute='_compute_achievements', store=True)
    achievement_visits = fields.Float(string='Achievement Visits %', compute='_compute_achievements', store=True)
    achievement_new_dealers = fields.Float(string='Achievement New Dealers %', compute='_compute_achievements', store=True)
    achievement_payment_collected = fields.Float(string='Achievement Payment Collected %', compute='_compute_achievements', store=True)
    achievement_complaints_solved = fields.Float(string='Achievement Complaints Solved %', compute='_compute_achievements', store=True)
    overall_achievement = fields.Float(string='Overall Achievement %', compute='_compute_achievements', store=True)

    @api.depends('actual_ids', 'actual_ids.kpi_type', 'actual_ids.value')
    def _compute_actuals(self):
        for record in self:
            actuals = {
                'sales': 0.0,
                'visits': 0.0,
                'new_dealers': 0.0,
                'payment_collected': 0.0,
                'complaints_solved': 0.0,
            }
            for actual in record.actual_ids:
                if actual.kpi_type in actuals:
                    actuals[actual.kpi_type] += actual.value
            
            record.actual_sales = actuals['sales']
            record.actual_visits = actuals['visits']
            record.actual_new_dealers = actuals['new_dealers']
            record.actual_payment_collected = actuals['payment_collected']
            record.actual_complaints_solved = actuals['complaints_solved']

    @api.depends(
        'target_sales', 'target_visits', 'target_new_dealers', 
        'target_payment_collected', 'target_complaints_solved',
        'actual_sales', 'actual_visits', 'actual_new_dealers',
        'actual_payment_collected', 'actual_complaints_solved'
    )
    def _compute_achievements(self):
        for record in self:
            # Calculate individual achievements
            record.achievement_sales = (record.actual_sales / record.target_sales * 100) if record.target_sales else 0.0
            record.achievement_visits = (record.actual_visits / record.target_visits * 100) if record.target_visits else 0.0
            record.achievement_new_dealers = (record.actual_new_dealers / record.target_new_dealers * 100) if record.target_new_dealers else 0.0
            record.achievement_payment_collected = (record.actual_payment_collected / record.target_payment_collected * 100) if record.target_payment_collected else 0.0
            record.achievement_complaints_solved = (record.actual_complaints_solved / record.target_complaints_solved * 100) if record.target_complaints_solved else 0.0
            
            # Calculate overall achievement (average of valid achievements)
            achievements = []
            if record.target_sales > 0:
                achievements.append(record.achievement_sales)
            if record.target_visits > 0:
                achievements.append(record.achievement_visits)
            if record.target_new_dealers > 0:
                achievements.append(record.achievement_new_dealers)
            if record.target_payment_collected > 0:
                achievements.append(record.achievement_payment_collected)
            if record.target_complaints_solved > 0:
                achievements.append(record.achievement_complaints_solved)
            
            record.overall_achievement = sum(achievements) / len(achievements) if achievements else 0.0

    def sync_target_items(self):
        """Sync denormalized target fields to kpi.target.item records"""
        for record in self:
            kpi_mapping = {
                'sales': record.target_sales,
                'visits': record.target_visits,
                'new_dealers': record.target_new_dealers,
                'payment_collected': record.target_payment_collected,
                'complaints_solved': record.target_complaints_solved,
            }
            
            for kpi_type, target_value in kpi_mapping.items():
                existing_item = record.item_ids.filtered(lambda i: i.kpi_type == kpi_type)
                if existing_item:
                    existing_item.write({'target_value': target_value})
                else:
                    self.env['kpi.target.item'].create({
                        'target_id': record.id,
                        'kpi_type': kpi_type,
                        'target_value': target_value,
                    })

    @api.model_create_multi
    def create(self, vals_list):
        records = super(KpiTarget, self).create(vals_list)
        records.sync_target_items()
        return records

    def write(self, vals):
        result = super(KpiTarget, self).write(vals)
        # Check if any target fields were updated
        target_fields = ['target_sales', 'target_visits', 'target_new_dealers', 
                        'target_payment_collected', 'target_complaints_solved']
        if any(field in vals for field in target_fields):
            self.sync_target_items()
        return result

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_done(self):
        self.write({'state': 'done'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    @api.model
    def get_kpi_dashboard_data(self, period_id=None):
        """RPC method returning dashboard data"""
        domain = []
        if period_id:
            domain = [('period_id', '=', period_id)]
        
        targets = self.search(domain)
        
        kpi_types = [
            {'key': 'sales', 'label': 'Sales'},
            {'key': 'visits', 'label': 'Visits'},
            {'key': 'new_dealers', 'label': 'New Dealers'},
            {'key': 'payment_collected', 'label': 'Payment Collected'},
            {'key': 'complaints_solved', 'label': 'Complaints Solved'},
        ]
        
        rows = []
        for target in targets:
            row = {
                'id': target.id,
                'employee_id': target.employee_id.id,
                'employee_name': target.employee_id.name,
                'period_id': target.period_id.id,
                'period_name': target.period_id.name,
                'state': target.state,
                'targets': {
                    'sales': target.target_sales,
                    'visits': target.target_visits,
                    'new_dealers': target.target_new_dealers,
                    'payment_collected': target.target_payment_collected,
                    'complaints_solved': target.target_complaints_solved,
                },
                'actuals': {
                    'sales': target.actual_sales,
                    'visits': target.actual_visits,
                    'new_dealers': target.actual_new_dealers,
                    'payment_collected': target.actual_payment_collected,
                    'complaints_solved': target.actual_complaints_solved,
                },
                'achievements': {
                    'sales': target.achievement_sales,
                    'visits': target.achievement_visits,
                    'new_dealers': target.achievement_new_dealers,
                    'payment_collected': target.achievement_payment_collected,
                    'complaints_solved': target.achievement_complaints_solved,
                    'overall': target.overall_achievement,
                },
            }
            rows.append(row)
        
        # Get all periods for the dropdown
        periods = self.env['kpi.target.period'].search([], order='date_from desc')
        period_list = [{'id': p.id, 'name': p.name} for p in periods]
        
        return {
            'rows': rows,
            'kpi_types': kpi_types,
            'periods': period_list,
        }

    @api.model
    def save_target_value(self, target_id, kpi_key, value):
        """RPC method to save a single target value from OWL component"""
        target = self.browse(target_id)
        if not target.exists():
            return {'success': False, 'error': 'Target not found'}
        
        field_name = f'target_{kpi_key}'
        if not hasattr(target, field_name):
            return {'success': False, 'error': 'Invalid KPI key'}
        
        try:
            target.write({field_name: float(value)})
            return {
                'success': True,
                'actual': getattr(target, f'actual_{kpi_key}'),
                'achievement': getattr(target, f'achievement_{kpi_key}'),
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
