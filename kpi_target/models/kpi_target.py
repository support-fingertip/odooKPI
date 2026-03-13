# -*- coding: utf-8 -*-
from odoo import models, fields, api

KPI_TYPES = [
    ('orders', 'Orders'),
    ('visits', 'Visits'),
    ('new_dealers', 'New Dealers'),
    ('payment_collected', 'Payment Collected'),
    ('complaints_solved', 'Complaints Solved'),
]


class KpiTarget(models.Model):
    _name = 'kpi.target'
    _description = 'KPI Target – Individual'
    _order = 'period_id desc, employee_id'
    _sql_constraints = [
        ('unique_employee_period', 'UNIQUE(employee_id, period_id)',
         'Each employee can have only one target per period!')
    ]

    name = fields.Char(string='Reference', compute='_compute_name', store=True)
    employee_id = fields.Many2one('hr.employee', string='Employee / Executive', required=True, index=True)
    department_id = fields.Many2one(
        'hr.department', related='employee_id.department_id', store=True, string='Department')
    job_id = fields.Many2one(
        'hr.job', related='employee_id.job_id', store=True, string='Job Position')
    period_id = fields.Many2one('kpi.target.period', string='Period', required=True, index=True)
    period_type = fields.Selection(related='period_id.period_type', string='Period Type', store=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
    ], string='Status', default='draft')

    manager_target_id = fields.Many2one(
        'kpi.manager.target', string='Team Target',
        ondelete='cascade', index=True,
        help='Set when this individual target belongs to a manager\'s team target.')

    item_ids = fields.One2many('kpi.target.item', 'target_id', string='Target Items')
    actual_ids = fields.One2many('kpi.actual', 'target_id', string='Actual Entries')

    target_orders = fields.Float(string='Target Orders', default=0.0,
                                 help='Number of orders to be placed in this period')
    target_visits = fields.Float(string='Target Visits', default=0.0,
                                 help='Number of customer visits to complete')
    target_new_dealers = fields.Float(string='Target New Dealers', default=0.0,
                                      help='Number of new dealers to be added')
    target_payment_collected = fields.Float(string='Target Payment Collected', default=0.0,
                                            help='Payment collection target amount')
    target_complaints_solved = fields.Float(string='Target Complaints Solved', default=0.0,
                                            help='Number of complaints to resolve')

    actual_orders = fields.Float(
        string='Actual Orders', compute='_compute_actuals', store=True)
    actual_order_amount = fields.Float(
        string='Actual Order Amount', compute='_compute_actuals', store=True,
        help='Total confirmed sale order amount (sum of amount_total) for the period')
    actual_visits = fields.Float(
        string='Actual Visits', compute='_compute_actuals', store=True)
    actual_new_dealers = fields.Float(
        string='Actual New Dealers', compute='_compute_actuals', store=True)
    actual_payment_collected = fields.Float(
        string='Actual Payment Collected', compute='_compute_actuals', store=True)
    actual_complaints_solved = fields.Float(
        string='Actual Complaints Solved', compute='_compute_actuals', store=True)

    achievement_orders = fields.Float(
        string='Orders Achievement %', compute='_compute_achievements', store=True)
    achievement_visits = fields.Float(
        string='Visits Achievement %', compute='_compute_achievements', store=True)
    achievement_new_dealers = fields.Float(
        string='New Dealers Achievement %', compute='_compute_achievements', store=True)
    achievement_payment_collected = fields.Float(
        string='Payment Achievement %', compute='_compute_achievements', store=True)
    achievement_complaints_solved = fields.Float(
        string='Complaints Achievement %', compute='_compute_achievements', store=True)
    overall_achievement = fields.Float(
        string='Overall Achievement %', compute='_compute_achievements', store=True)

    @api.depends('employee_id', 'period_id')
    def _compute_name(self):
        for rec in self:
            parts = [rec.employee_id.name or '', rec.period_id.name or '']
            rec.name = ' / '.join(p for p in parts if p) or 'New Target'


    @api.depends('actual_ids', 'actual_ids.kpi_type', 'actual_ids.value',
                 'employee_id', 'period_id')
    def _compute_actuals(self):
        for record in self:
            manual = {
                'orders': 0.0,
                'visits': 0.0,
                'new_dealers': 0.0,
                'payment_collected': 0.0,
                'complaints_solved': 0.0,
            }
            for entry in record.actual_ids:
                if entry.kpi_type in manual:
                    manual[entry.kpi_type] += entry.value

            employee = record.employee_id
            period = record.period_id

            sys_visits = 0.0
            sys_orders = 0.0
            sys_order_amount = 0.0

            if employee and period and period.date_from and period.date_to:
                date_from = str(period.date_from) + ' 00:00:00'
                date_to = str(period.date_to) + ' 23:59:59'

                if 'visit.model' in self.env:
                    try:
                        completed_visits = self.env['visit.model'].sudo().search([
                            ('employee_id', '=', employee.id),
                            ('status', '=', 'completed'),
                            ('actual_start_time', '>=', date_from),
                            ('actual_start_time', '<=', date_to),
                        ])
                        sys_visits = float(len(completed_visits))
                    except Exception:
                        pass

                if 'sale.order' in self.env:
                    try:
                        if employee.user_id:
                            order_domain = [
                                '|',
                                ('user_id', '=', employee.user_id.id),
                                ('visit_id.employee_id', '=', employee.id),
                            ]
                        else:
                            order_domain = [
                                ('visit_id.employee_id', '=', employee.id),
                            ]
                        sale_orders = self.env['sale.order'].sudo().search(
                            order_domain + [
                                ('date_order', '>=', date_from),
                                ('date_order', '<=', date_to),
                                ('state', 'in', ['sale', 'done']),
                            ]
                        )
                        sys_orders = float(len(sale_orders))
                        sys_order_amount = sum(sale_orders.mapped('amount_total'))
                    except Exception:
                        pass

            record.actual_visits = max(sys_visits, manual['visits'])
            record.actual_orders = max(sys_orders, manual['orders'])
            record.actual_order_amount = sys_order_amount
            record.actual_new_dealers = manual['new_dealers']
            record.actual_payment_collected = manual['payment_collected']
            record.actual_complaints_solved = manual['complaints_solved']

    @api.depends(
        'target_orders', 'target_visits', 'target_new_dealers',
        'target_payment_collected', 'target_complaints_solved',
        'actual_orders', 'actual_visits', 'actual_new_dealers',
        'actual_payment_collected', 'actual_complaints_solved',
    )
    def _compute_achievements(self):
        for record in self:
            def pct(actual, target):
                return round(actual / target * 100, 2) if target else 0.0

            record.achievement_orders = pct(record.actual_orders, record.target_orders)
            record.achievement_visits = pct(record.actual_visits, record.target_visits)
            record.achievement_new_dealers = pct(record.actual_new_dealers, record.target_new_dealers)
            record.achievement_payment_collected = pct(
                record.actual_payment_collected, record.target_payment_collected)
            record.achievement_complaints_solved = pct(
                record.actual_complaints_solved, record.target_complaints_solved)

            achieved = [
                a for t, a in [
                    (record.target_orders, record.achievement_orders),
                    (record.target_visits, record.achievement_visits),
                    (record.target_new_dealers, record.achievement_new_dealers),
                    (record.target_payment_collected, record.achievement_payment_collected),
                    (record.target_complaints_solved, record.achievement_complaints_solved),
                ] if t > 0
            ]
            record.overall_achievement = round(
                sum(achieved) / len(achieved), 2) if achieved else 0.0


    def sync_target_items(self):
        for record in self:
            kpi_mapping = {
                'orders': record.target_orders,
                'visits': record.target_visits,
                'new_dealers': record.target_new_dealers,
                'payment_collected': record.target_payment_collected,
                'complaints_solved': record.target_complaints_solved,
            }
            for kpi_type, target_value in kpi_mapping.items():
                existing = record.item_ids.filtered(lambda i: i.kpi_type == kpi_type)
                if existing:
                    existing.write({'target_value': target_value})
                else:
                    self.env['kpi.target.item'].create({
                        'target_id': record.id,
                        'kpi_type': kpi_type,
                        'target_value': target_value,
                    })

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.sync_target_items()
        return records

    def write(self, vals):
        result = super().write(vals)
        target_fields = [
            'target_orders', 'target_visits', 'target_new_dealers',
            'target_payment_collected', 'target_complaints_solved',
        ]
        if any(f in vals for f in target_fields):
            self.sync_target_items()
        return result

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_done(self):
        self.write({'state': 'done'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

 
    def _get_live_actuals(self, employee, period):
        """Compute visits, order count, and order amount live from source records.

        This ensures the dashboard always reflects real-time data even when
        stored computed fields haven't been invalidated yet (e.g. after a
        visit is completed or a new sale order is placed).
        """
        sys_visits = 0.0
        sys_orders = 0.0
        sys_order_amount = 0.0
        if employee and period and period.date_from and period.date_to:
            date_from = str(period.date_from) + ' 00:00:00'
            date_to = str(period.date_to) + ' 23:59:59'
            if 'visit.model' in self.env:
                try:
                    sys_visits = float(self.env['visit.model'].sudo().search_count([
                        ('employee_id', '=', employee.id),
                        ('status', '=', 'completed'),
                        ('actual_start_time', '>=', date_from),
                        ('actual_start_time', '<=', date_to),
                    ]))
                except Exception:
                    pass
            if 'sale.order' in self.env:
                try:
                    if employee.user_id:
                        order_domain = [
                            '|',
                            ('user_id', '=', employee.user_id.id),
                            ('visit_id.employee_id', '=', employee.id),
                        ]
                    else:
                        order_domain = [
                            ('visit_id.employee_id', '=', employee.id),
                        ]
                    live_orders = self.env['sale.order'].sudo().search(
                        order_domain + [
                            ('date_order', '>=', date_from),
                            ('date_order', '<=', date_to),
                            ('state', 'in', ['sale', 'done']),
                        ]
                    )
                    sys_orders = float(len(live_orders))
                    sys_order_amount = sum(live_orders.mapped('amount_total'))
                except Exception:
                    pass
        return sys_visits, sys_orders, sys_order_amount

    @api.model
    def get_kpi_dashboard_data(self, period_id=None):
        """Return dashboard data for both individual and team targets."""
        domain = [('period_id', '=', period_id)] if period_id else []
        targets = self.sudo().search(domain, order='employee_id')

        kpi_types = [
            {'key': 'orders', 'label': 'Orders'},
            {'key': 'visits', 'label': 'Visits'},
            {'key': 'new_dealers', 'label': 'New Dealers'},
            {'key': 'payment_collected', 'label': 'Payment'},
            {'key': 'complaints_solved', 'label': 'Complaints'},
        ]

        rows = []
        for target in targets:
            live_visits, live_orders, live_order_amount = self._get_live_actuals(
                target.employee_id, target.period_id)

            actual_visits = max(live_visits, target.actual_visits)
            actual_orders = max(live_orders, target.actual_orders)
            actual_order_amount = max(live_order_amount, target.actual_order_amount)
            actual_new_dealers = target.actual_new_dealers
            actual_payment = target.actual_payment_collected
            actual_complaints = target.actual_complaints_solved

            def pct(actual, target_val):
                return round(actual / target_val * 100, 2) if target_val else 0.0

            rows.append({
                'id': target.id,
                'employee_id': target.employee_id.id,
                'employee_name': target.employee_id.name,
                'department': target.department_id.name or '',
                'period_id': target.period_id.id,
                'period_name': target.period_id.name,
                'state': target.state,
                'is_team_member': bool(target.manager_target_id),
                'manager_target_id': target.manager_target_id.id or False,
                'manager_name': target.manager_target_id.manager_id.name if target.manager_target_id else '',
                'targets': {
                    'orders': target.target_orders,
                    'visits': target.target_visits,
                    'new_dealers': target.target_new_dealers,
                    'payment_collected': target.target_payment_collected,
                    'complaints_solved': target.target_complaints_solved,
                },
                'actuals': {
                    'orders': actual_orders,
                    'order_amount': actual_order_amount,
                    'visits': actual_visits,
                    'new_dealers': actual_new_dealers,
                    'payment_collected': actual_payment,
                    'complaints_solved': actual_complaints,
                },
                'achievements': {
                    'orders': pct(actual_orders, target.target_orders),
                    'visits': pct(actual_visits, target.target_visits),
                    'new_dealers': pct(actual_new_dealers, target.target_new_dealers),
                    'payment_collected': pct(actual_payment, target.target_payment_collected),
                    'complaints_solved': pct(actual_complaints, target.target_complaints_solved),
                    'overall': target.overall_achievement,
                },
            })

        team_domain = [('period_id', '=', period_id)] if period_id else []
        team_targets = self.env['kpi.manager.target'].sudo().search(team_domain, order='manager_id')
        team_rows = []
        for tt in team_targets:
            team_rows.append({
                'id': tt.id,
                'manager_name': tt.manager_id.name,
                'department': tt.department_id.name or '',
                'period_name': tt.period_id.name,
                'assignment_mode': tt.assignment_mode,
                'member_count': tt.member_count,
                'state': tt.state,
                'is_fully_allocated': tt.is_fully_allocated,
                'total_targets': {
                    'orders': tt.total_target_orders,
                    'visits': tt.total_target_visits,
                    'new_dealers': tt.total_target_new_dealers,
                    'payment_collected': tt.total_target_payment_collected,
                    'complaints_solved': tt.total_target_complaints_solved,
                },
                'team_actuals': {
                    'orders': tt.team_actual_orders,
                    'visits': tt.team_actual_visits,
                    'new_dealers': tt.team_actual_new_dealers,
                    'payment_collected': tt.team_actual_payment_collected,
                    'complaints_solved': tt.team_actual_complaints_solved,
                },
                'team_achievement': tt.team_overall_achievement,
            })

        periods = self.env['kpi.target.period'].sudo().search([], order='date_from desc')
        return {
            'rows': rows,
            'team_rows': team_rows,
            'kpi_types': kpi_types,
            'periods': [{'id': p.id, 'name': p.name} for p in periods],
        }

    @api.model
    def save_target_value(self, target_id, kpi_key, value):
        """RPC: save a single target value from the OWL dashboard."""
        target = self.sudo().browse(target_id)
        if not target.exists():
            return {'success': False, 'error': 'Target not found'}
        field_name = f'target_{kpi_key}'
        if not hasattr(target, field_name):
            return {'success': False, 'error': 'Invalid KPI key'}
        try:
            target.write({field_name: float(value)})
            return {
                'success': True,
                'actual': getattr(target, f'actual_{kpi_key}', 0.0),
                'achievement': getattr(target, f'achievement_{kpi_key}', 0.0),
                'overall': target.overall_achievement,
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
