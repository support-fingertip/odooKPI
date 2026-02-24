# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta

class VisitModel(models.Model):
    _name = 'visit.model'
    _description = 'Customer Visit'
    _order = 'actual_start_time desc'
    _rec_name = 'name'

    name = fields.Char(string='Visit ID', required=True, copy=False, readonly=True, default='New')
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, ondelete='cascade')
    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
    beat_id = fields.Many2one('beat.module', string='Beat')
    beat_line_id = fields.Many2one('beat.line', string='Beat Line')
    

    planned_start_time = fields.Datetime(string='Planned Start Time')
    actual_start_time = fields.Datetime(string='Actual Start Time')
    planned_end_time = fields.Datetime(string='Planned End Time')
    actual_end_time = fields.Datetime(string='Actual End Time')

    visit_for = fields.Selection([
        ('Primary Customer', 'Primary Customer'),
        ('Secondary Customer', 'Secondary Customer'),
        ('Prospect', 'Prospect'),
    ], string='Visit For', default='Secondary Customer')
    
    today_work_plan = fields.Selection([
        ('Customer Visit', 'Customer Visit'),
        ('Conference', 'Conference'),
        ('Training', 'Training'),
        ('Seminar', 'Seminar'),
        ('Enter Odometer Reading', 'Enter Odometer Reading'),
    ], string="Today's Work Plan")
    
    travel_type = fields.Selection([
        ('Headquarters', 'Headquarters'),
        ('Up country', 'Up country'),
        ('Other', 'Other'),
    ], string='Travel Type')
    
    vehicle_used = fields.Selection([
        ('Personal/own', 'Personal/own'),
        ('Office', 'Office'),
        ('Public transport', 'Public transport'),
    ], string='Vehicle Used')

    status = fields.Selection([
        ('planned', 'Planned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='planned', required=True)
    
    is_productive = fields.Boolean(string='Is Productive', default=True)
    productivity_reason = fields.Text(string='Non-Productive Reason')
    
    visit_comments = fields.Text(string='Visit Comments')
    store_image = fields.Binary(string='Store Image', attachment=True)
    store_image_filename = fields.Char(string='Store Image Filename')

    duration = fields.Float(string='Duration (Hours)', compute='_compute_duration', store=True)
    duration_display = fields.Char(string='Duration', compute='_compute_duration_display')
    
    order_ids = fields.One2many('sale.order', 'visit_id', string='Orders')
    order_line_ids = fields.One2many('sale.order.line', 'visit_id', string='Order Lines')
    order_count = fields.Integer(string='Order Count', compute='_compute_order_count')
    total_order_amount = fields.Monetary(string='Total Order Amount', compute='_compute_total_order_amount', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    @api.constrains('status', 'store_image')
    def _check_store_image_required(self):
        for record in self:
            if record.status == 'completed' and not record.store_image:
                raise ValidationError(
                    _('A Store Image (attachment) is required to mark a visit as Completed.')
                )

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('visit.model') or 'New'
        record = super(VisitModel, self).create(vals)
        if vals.get('status') == 'completed':
            record._trigger_kpi_recompute()
        return record

    def write(self, vals):
        result = super(VisitModel, self).write(vals)
        if vals.get('status') == 'completed':
            self._trigger_kpi_recompute()
        return result

    def _trigger_kpi_recompute(self):
        """Invalidate stored KPI actuals so they get recomputed on next access."""
        if 'kpi.target' not in self.env:
            return
        for record in self:
            if not record.employee_id:
                continue
            kpi_targets = self.env['kpi.target'].search([
                ('employee_id', '=', record.employee_id.id),
            ])
            if kpi_targets:
                kpi_targets._compute_actuals()
                kpi_targets._compute_achievements()

    @api.depends('actual_start_time', 'actual_end_time')
    def _compute_duration(self):
        for record in self:
            if record.actual_start_time and record.actual_end_time:
                delta = record.actual_end_time - record.actual_start_time
                record.duration = delta.total_seconds() / 3600.0
            else:
                record.duration = 0.0

    @api.depends('duration')
    def _compute_duration_display(self):
        for record in self:
            if record.duration:
                hours = int(record.duration)
                minutes = int((record.duration - hours) * 60)
                record.duration_display = f"{hours}h {minutes}m"
            else:
                record.duration_display = "0h 0m"

    @api.depends('order_ids')
    def _compute_order_count(self):
        for record in self:
            record.order_count = len(record.order_ids)

    @api.depends('order_line_ids', 'order_line_ids.price_subtotal')
    def _compute_total_order_amount(self):
        for record in self:
            record.total_order_amount = sum(record.order_line_ids.mapped('price_subtotal'))

    def action_view_orders(self):
        self.ensure_one()
        return {
            'name': _('Visit Orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'tree,form',
            'domain': [('visit_id', '=', self.id)],
            'context': {
                'default_partner_id': self.partner_id.id,
                'default_visit_id': self.id,
                'default_user_id': self.employee_id.user_id.id,
            },
        }

    def action_create_order(self):
        self.ensure_one()
        return {
            'name': _('Create Order'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_partner_id': self.partner_id.id,
                'default_visit_id': self.id,
                'default_user_id': self.employee_id.user_id.id,
            },
        }