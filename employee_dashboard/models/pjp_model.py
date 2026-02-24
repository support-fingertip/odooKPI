# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from collections import OrderedDict
import logging

_logger = logging.getLogger(__name__)


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def rotate_beats_in_month(self, month, year, rotation_frequency):
        """
        Rotate beats within a specific month based on rotation frequency
        
        :param month: Month number (1-12)
        :param year: Year
        :param rotation_frequency: Number of days for one complete rotation cycle
        :return: dict with success status and message
        """
        
        first_day = datetime(year, month, 1).date()
        if month == 12:
            last_day = datetime(year + 1, 1, 1).date() - timedelta(days=1)
        else:
            last_day = datetime(year, month + 1, 1).date() - timedelta(days=1)
        
        today = fields.Date.today()
        
        
        if first_day < today <= last_day:
            
            start_date = today
        elif first_day >= today:
            
            start_date = first_day
        else:
            
            return {
                'success': False,
                'message': f'Cannot rotate beats in past months. Please select current or future month.'
            }
        
        days_in_range = (last_day - start_date).days + 1

        
        beats_with_dates = self.env['beat.module'].search([
            ('employee_id', '=', self.id),
            ('beat_date', '>=', first_day),
            ('beat_date', '<=', last_day),
            ('beat_date', '!=', False)
        ], order='beat_date asc')

        if not beats_with_dates:
            return {
                'success': False,
                'message': f'No beats assigned in {first_day.strftime("%B %Y")}. Please assign beats to dates first.'
            }

        
        beats_dict = OrderedDict()
        for beat in beats_with_dates:
            if beat.id not in beats_dict:
                beats_dict[beat.id] = beat

        beats = list(beats_dict.values())
        total_beats = len(beats)

        
        if rotation_frequency < total_beats:
            return {
                'success': False,
                'message': f'Rotation frequency ({rotation_frequency}) must be at least equal to number of beats ({total_beats}).'
            }

        self.env['beat.module'].search([
            ('employee_id', '=', self.id),
            ('beat_date', '>=', start_date),
            ('beat_date', '<=', last_day)
        ]).write({'beat_date': False})

        current_date = start_date  
        assignments_made = 0
        new_beats_created = 0
        rotation_cycles = 0

        while current_date <= last_day:
            day_in_cycle = assignments_made % rotation_frequency
            
            if day_in_cycle < total_beats:
                beat_index = day_in_cycle
                original_beat = beats[beat_index]
                
                if rotation_cycles == 0:
                    original_beat.write({'beat_date': current_date})
                else:
                    beat_lines = self.env['beat.line'].search([
                        ('beat_id', '=', original_beat.id)
                    ])
                    
                   
                    new_beat = self.env['beat.module'].create({
                        'name': f"{original_beat.name} (Rotation {rotation_cycles + 1})",
                        'employee_id': self.id,
                        'beat_date': current_date,
                        'beat_number': original_beat.beat_number,
                    })
                    
                    
                    for line in beat_lines:
                        self.env['beat.line'].create({
                            'beat_id': new_beat.id,
                            'partner_id': line.partner_id.id,
                            'sequence': line.sequence,
                            'notes': line.notes,
                        })
                    
                    new_beats_created += 1
            
            current_date += timedelta(days=1)
            assignments_made += 1
            
            if assignments_made > 0 and assignments_made % rotation_frequency == 0:
                rotation_cycles += 1

        beats_assigned = assignments_made - (assignments_made // rotation_frequency) * (rotation_frequency - total_beats)
        empty_days = assignments_made - beats_assigned

        return {
            'success': True,
            'message': f'Rotation completed: {total_beats} beats rotated with frequency {rotation_frequency} days. Assigned {beats_assigned} beats, {empty_days} empty days. Created {new_beats_created} new beats.',
            'beats_assigned': beats_assigned,
            'empty_days': empty_days,
            'new_beats_created': new_beats_created,
        }

    def create_pjp_from_calendar(self, start_date, end_date):
        """
        Create ONE PJP with multiple items from calendar beats
        Only includes FUTURE dates (today and onwards)
        Single beat per day - creates NEW beat records for each PJP item
        """
        
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

        
        today = fields.Date.today()

        
        if start_date < today:
            return {
                'success': False,
                'message': f'Start date cannot be in the past. Please select {today} or a future date.'
            }

        if end_date < start_date:
            return {
                'success': False,
                'message': 'End date must be on or after start date.'
            }

        beats_with_dates = self.env['beat.module'].search([
            ('employee_id', '=', self.id),
            ('beat_date', '!=', False),
            ('beat_date', '>=', start_date),
            ('beat_date', '<=', end_date),
            ('beat_date', '>=', today)
        ], order='beat_date asc')

        if not beats_with_dates:
            return {
                'success': False,
                'message': f'No beats found with assigned future dates between {start_date} and {end_date}. Please assign beats to dates in calendar view first.'
            }

        pjp = self.env['pjp.model'].create({
            'name': f'PJP - {self.name} - {start_date} to {end_date}',
            'employee_id': self.id,
            'start_date': start_date,
            'end_date': end_date,
            'state': 'draft',
        })

        pjp_items = []
        sequence = 10
        dates_processed = set()

        for original_beat in beats_with_dates:
            beat_date = original_beat.beat_date

            if beat_date in dates_processed:
                continue

            dates_processed.add(beat_date)

            pjp_items.append({
                'pjp_id': pjp.id,
                'employee_id': self.id,
                'assigned_beat_id': original_beat.id,
                'date': beat_date,
                'sequence': sequence,
                'status': 'draft',
            })
            sequence += 10

        if pjp_items:
            self.env['pjp.item'].create(pjp_items)

        months_span = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month) + 1

        return {
            'success': True,
            'pjp_id': pjp.id,
            'pjp_items_count': len(pjp_items),
            'message': f'PJP created successfully! Total: {len(pjp_items)} items with {len(pjp_items)} new beats across {months_span} month(s)'
        }



class PJPModel(models.Model):
    _name = 'pjp.model'
    _description = 'Permanent Journey Plan'
    _order = 'start_date desc'

    name = fields.Char(string='PJP Name', required=True, compute='_compute_name', store=True, readonly=False)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, index=True)
    start_date = fields.Date(string='Start Date', required=True)
    end_date = fields.Date(string='End Date', required=True)
   
    pjp_item_ids = fields.One2many('pjp.item', 'pjp_id', string='PJP Items')
    pjp_item_count = fields.Integer(string='Total Items', compute='_compute_pjp_item_count')
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', required=True)
    
    notes = fields.Text(string='Notes')

    @api.depends('employee_id')
    def _compute_name(self):
        for record in self:
            if record.employee_id:
                record.name = f"PJP - {record.employee_id.name}"
            else:
                record.name = 'New PJP'
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'name' not in vals or not vals.get('name'):
                employee = self.env['hr.employee'].browse(vals.get('employee_id'))
                if employee:
                    vals['name'] = f"PJP - {employee.name}"
                else:
                    vals['name'] = 'New PJP'
        return super(PJPModel, self).create(vals_list)

    @api.depends('pjp_item_ids')
    def _compute_pjp_item_count(self):
        for record in self:
            record.pjp_item_count = len(record.pjp_item_ids)

    def action_approve(self):
        self.write({'state': 'approved'})
        return True

    def action_activate(self):
        self.write({'state': 'active'})
        return True

    def action_complete(self):
        self.write({'state': 'completed'})
        return True

    def action_cancel(self):
        self.write({'state': 'cancelled'})
        return True


class PJPItem(models.Model):
    _name = 'pjp.item'
    _description = 'PJP Item'
    _order = 'date asc, sequence asc'

    name = fields.Char(string='PJP Item Name', compute='_compute_name', store=True, readonly=False)
    pjp_id = fields.Many2one('pjp.model', string='PJP', required=True, ondelete='cascade', index=True)
    employee_id = fields.Many2one(related='pjp_id.employee_id', string='Employee', store=True, readonly=True)
    
    assigned_beat_id = fields.Many2one('beat.module', string='Assigned Beat', required=True)
    approved_beat_id = fields.Many2one('beat.module', string='Approved Beat')
    
    date = fields.Date(string='Date', required=True, index=True)
    sequence = fields.Integer(string='Sequence', default=10)
    
    status = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', required=True)
    
    notes = fields.Text(string='Notes')
    created_date = fields.Datetime(string='Created Date', default=fields.Datetime.now, readonly=True)

    @api.depends('assigned_beat_id', 'date')
    def _compute_name(self):
        for record in self:
            if record.assigned_beat_id:
                record.name = f"{record.assigned_beat_id.name}"
            else:
                record.name = 'New PJP Item'
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'name' not in vals or not vals.get('name'):
                beat = self.env['beat.module'].browse(vals.get('assigned_beat_id'))
                if beat:
                    vals['name'] = f"{beat.name}"
                else:
                    vals['name'] = 'New PJP Item'
        return super(PJPItem, self).create(vals_list)

    def action_approve(self):
        self.write({
            'status': 'approved',
            'approved_beat_id': self.assigned_beat_id.id
        })
        return True

    def action_complete(self):
        self.write({'status': 'completed'})
        return True

    def action_cancel(self):
        self.write({'status': 'cancelled'})
        return True