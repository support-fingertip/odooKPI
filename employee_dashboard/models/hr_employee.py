# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
import pytz
import logging

_logger = logging.getLogger(__name__)

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    joining_date = fields.Date(string='Joining Date')
    relieving_date = fields.Date(string='Relieving Date')
    pan_number = fields.Char(string='PAN Number')
    aadhar_number = fields.Char(string='Aadhar Number')

    def _get_user_timezone(self):
        """Get user's timezone or default to UTC"""
        return self.env.user.tz or 'UTC'

    @api.model
    def create_attendance_checkin(self, employee_id, work_plan, travel_type, vehicle_used, location_data=None):
        """Create attendance check-in with location - handles existing open attendance"""
        try:
            employee = self.browse(employee_id)
            
            if not employee.exists():
                return {'success': False, 'error': 'Employee not found'}

            HrAttendance = self.env['hr.attendance'].sudo()

            existing_attendance = HrAttendance.search([
                ('employee_id', '=', employee_id),
                ('check_out', '=', False)
            ], limit=1, order='check_in desc')

            if existing_attendance:
                _logger.info(f"Found existing open attendance {existing_attendance.id} for employee {employee_id}")
                
                
                user_tz = self._get_user_timezone()
                user_timezone = pytz.timezone(user_tz)
                
                check_in_utc = pytz.UTC.localize(existing_attendance.check_in)
                check_in_local = check_in_utc.astimezone(user_timezone)
                
                now_local = datetime.now(user_timezone)
                check_in_date = check_in_local.date()
                today_date = now_local.date()
                
                if check_in_date == today_date:
                    _logger.info(f"Existing attendance is from today, returning it")
                    return {
                        'success': True,
                        'attendance_id': existing_attendance.id,
                        'message': f'Day already started at {check_in_local.strftime("%I:%M %p")}',
                        'check_in': check_in_local.strftime('%Y-%m-%d %H:%M:%S')
                    }
                else:
                    _logger.warning(f"Found old open attendance from {check_in_date}, auto-closing it")
                    
                    old_checkout_time = check_in_local.replace(hour=23, minute=59, second=59)
                    old_checkout_utc = old_checkout_time.astimezone(pytz.UTC).replace(tzinfo=None)
                    
                    worked_seconds = (old_checkout_utc - existing_attendance.check_in).total_seconds()
                    worked_hours = worked_seconds / 3600.0
                    
                    self.env.cr.execute("""
                        UPDATE hr_attendance
                        SET check_out = %s,
                            worked_hours = %s,
                            write_date = NOW(),
                            write_uid = %s
                        WHERE id = %s
                    """, (old_checkout_utc, worked_hours, self.env.uid, existing_attendance.id))
                    
                    self.env.cr.commit()
                    _logger.info(f"Auto-closed old attendance {existing_attendance.id}")
                    
                    
            current_utc = datetime.now(pytz.UTC).replace(tzinfo=None)
            
            attendance_vals = {
                'employee_id': employee_id,
                'check_in': current_utc,
            }

            if location_data:
                attendance_vals.update({
                    'checkin_latitude': location_data.get('latitude'),
                    'checkin_longitude': location_data.get('longitude'),
                    'checkin_accuracy': location_data.get('accuracy'),
                    'checkin_full_address': location_data.get('full_address'),
                    'checkin_city': location_data.get('city'),
                    'checkin_state': location_data.get('state'),
                    'checkin_country': location_data.get('country'),
                })

            attendance = HrAttendance.with_context(no_auto_checkout=True).create(attendance_vals)
            
            user_tz = self._get_user_timezone()
            user_timezone = pytz.timezone(user_tz)
            check_in_utc = pytz.UTC.localize(attendance.check_in)
            check_in_local = check_in_utc.astimezone(user_timezone)
            
            _logger.info(f"Created new attendance check-in {attendance.id} for employee {employee_id}")

            return {
                'success': True,
                'attendance_id': attendance.id,
                'check_in': check_in_local.strftime('%Y-%m-%d %H:%M:%S'),
                'message': f'Day started at {check_in_local.strftime("%I:%M %p")}'
            }

        except Exception as e:
            _logger.error(f"Error in check-in: {str(e)}", exc_info=True)
            return {'success': False, 'error': str(e)}


    @api.model
    def create_attendance_checkout(self, employee_id, attendance_id, location_data=None):
        """Create attendance check-out with location"""
        try:
            HrAttendance = self.env['hr.attendance'].sudo()
            
           
            attendance = None
            if attendance_id:
                attendance = HrAttendance.browse(attendance_id)
                if not attendance.exists():
                    return {'success': False, 'error': f'Attendance record {attendance_id} not found'}
                if attendance.employee_id.id != employee_id:
                    return {'success': False, 'error': 'Attendance record does not belong to this employee'}
            else:
                user_tz = self._get_user_timezone()
                user_timezone = pytz.timezone(user_tz)
                now_user = datetime.now(user_timezone)
                today_start_local = now_user.replace(hour=0, minute=0, second=0, microsecond=0)
                today_end_local = today_start_local + timedelta(days=1)
                
                today_start_utc = today_start_local.astimezone(pytz.UTC).replace(tzinfo=None)
                today_end_utc = today_end_local.astimezone(pytz.UTC).replace(tzinfo=None)
                
                attendance = HrAttendance.search([
                    ('employee_id', '=', employee_id),
                    ('check_in', '>=', today_start_utc),
                    ('check_in', '<', today_end_utc),
                    ('check_out', '=', False)
                ], limit=1, order='check_in desc')
            
            if not attendance:
                return {'success': False, 'error': 'No open attendance found. Please start your day first.'}
            
            
            if attendance.check_out:
                user_tz = self._get_user_timezone()
                user_timezone = pytz.timezone(user_tz)
                check_out_utc = pytz.UTC.localize(attendance.check_out)
                check_out_local = check_out_utc.astimezone(user_timezone)
                
                return {
                    'success': True,
                    'attendance_id': attendance.id,
                    'message': f'Already checked out at {check_out_local.strftime("%I:%M %p")}',
                    'check_out': check_out_local.strftime('%Y-%m-%d %H:%M:%S'),
                    'worked_hours': attendance.worked_hours or 0.0
                }
            
            checkout_time_utc = datetime.now(pytz.UTC).replace(tzinfo=None)
            
            _logger.info(f"Attempting to checkout attendance {attendance.id} using direct SQL")
            
            try:
                
                today_date = checkout_time_utc.date()
                
                self.env.cr.execute("""
                    DELETE FROM hr_attendance_overtime
                    WHERE employee_id = %s AND date = %s
                """, (employee_id, today_date))
                
                deleted_count = self.env.cr.rowcount
                if deleted_count > 0:
                    _logger.info(f"Deleted {deleted_count} existing overtime records")
                
                
                check_in_time = attendance.check_in
                worked_seconds = (checkout_time_utc - check_in_time).total_seconds()
                worked_hours = worked_seconds / 3600.0
                
                
                update_vals = {
                    'check_out': checkout_time_utc,
                    'worked_hours': worked_hours,
                }
                
                
                if location_data:
                    update_vals.update({
                        'checkout_latitude': location_data.get('latitude'),
                        'checkout_longitude': location_data.get('longitude'),
                        'checkout_accuracy': location_data.get('accuracy'),
                        'checkout_full_address': location_data.get('full_address'),
                        'checkout_city': location_data.get('city'),
                        'checkout_state': location_data.get('state'),
                        'checkout_country': location_data.get('country'),
                    })
                
                
                set_parts = []
                values = []
                
                for key, value in update_vals.items():
                    set_parts.append(f"{key} = %s")
                    values.append(value)
                
                set_parts.append("write_date = NOW()")
                set_parts.append("write_uid = %s")
                values.append(self.env.uid)
                values.append(attendance.id)
                
                sql = f"""
                    UPDATE hr_attendance
                    SET {', '.join(set_parts)}
                    WHERE id = %s
                """
                
                self.env.cr.execute(sql, values)
                
                
                self.env.cr.commit()
                
                _logger.info(f"✓ Successfully checked out via SQL: attendance {attendance.id}, worked_hours: {worked_hours:.2f}")
                
                
                attendance.invalidate_recordset()
                self.env.cr.execute("""
                    SELECT check_out, worked_hours
                    FROM hr_attendance
                    WHERE id = %s
                """, (attendance.id,))
                
                result = self.env.cr.fetchone()
                if not result or not result[0]:
                    raise Exception("SQL update failed - check_out is still null")
                
                actual_checkout = result[0]
                actual_worked_hours = result[1] or 0.0
                
                _logger.info(f"Verified: check_out={actual_checkout}, worked_hours={actual_worked_hours}")
                
            except Exception as e:
                _logger.error(f"Checkout failed: {e}", exc_info=True)
                self.env.cr.rollback()
                return {
                    'success': False,
                    'error': f'Failed to record checkout: {str(e)}'
                }
            
            
            user_tz = self._get_user_timezone()
            user_timezone = pytz.timezone(user_tz)
            check_out_utc = pytz.UTC.localize(checkout_time_utc)
            check_out_local = check_out_utc.astimezone(user_timezone)
            
            return {
                'success': True,
                'attendance_id': attendance.id,
                'check_out': check_out_local.strftime('%Y-%m-%d %H:%M:%S'),
                'worked_hours': worked_hours,
                'message': f'Day ended at {check_out_local.strftime("%I:%M %p")} ({worked_hours:.2f} hours worked)'
            }
            
        except Exception as e:
            _logger.error(f"Error in create_attendance_checkout: {e}", exc_info=True)
            try:
                self.env.cr.rollback()
            except:
                pass
            return {'success': False, 'error': f'Unexpected error: {str(e)}'}

    @api.model
    def get_today_attendance(self, employee_id):
        """Get today's attendance record for employee"""
        try:
            if 'hr.attendance' not in self.env:
                return {'success': False, 'error': 'Attendance module not installed'}
            
            user_tz = self._get_user_timezone()
            user_timezone = pytz.timezone(user_tz)
            
            now_user = datetime.now(user_timezone)
            today_start_local = now_user.replace(hour=0, minute=0, second=0, microsecond=0)
            today_end_local = today_start_local + timedelta(days=1)
            
            today_start_utc = today_start_local.astimezone(pytz.UTC).replace(tzinfo=None)
            today_end_utc = today_end_local.astimezone(pytz.UTC).replace(tzinfo=None)
            
            HrAttendance = self.env['hr.attendance'].sudo()
            
            attendance = HrAttendance.search([
                ('employee_id', '=', employee_id),
                ('check_in', '>=', today_start_utc),
                ('check_in', '<', today_end_utc),
            ], limit=1, order='check_in desc')
            
            if attendance:
                check_in_utc = pytz.UTC.localize(attendance.check_in)
                check_in_local = check_in_utc.astimezone(user_timezone)
                
                result = {
                    'success': True,
                    'attendance_id': attendance.id,
                    'check_in': check_in_local.strftime('%Y-%m-%d %H:%M:%S'),
                    'worked_hours': attendance.worked_hours or 0.0,
                    'is_checked_in': not attendance.check_out
                }
                
                if attendance.check_out:
                    check_out_utc = pytz.UTC.localize(attendance.check_out)
                    check_out_local = check_out_utc.astimezone(user_timezone)
                    result['check_out'] = check_out_local.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    result['check_out'] = None
                
                return result
            else:
                return {'success': True, 'attendance_id': None, 'is_checked_in': False}
                
        except Exception as e:
            _logger.error(f"Error in get_today_attendance: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}



class EmployeeDashboard(models.Model):
    _name = 'employee.dashboard'
    _description = 'Employee Dashboard Helper'

    @api.model
    def get_user_access_info(self):
        """Get current user's access information"""
        user = self.env.user
        
        is_manager = user.has_group('employee_dashboard.group_employee_dashboard_manager')
        employee = self.env['hr.employee'].search([('user_id', '=', user.id)], limit=1)
        
        return {
            'is_manager': is_manager,
            'employee_id': employee.id if employee else False,
            'user_id': user.id,
        }
    
    @api.model
    def get_accessible_employees(self):
        """Get list of employees accessible to current user"""
        user = self.env.user
        is_manager = user.has_group('employee_dashboard.group_employee_dashboard_manager')
        
        domain = []
        if not is_manager:
            employee = self.env['hr.employee'].search([('user_id', '=', user.id)], limit=1)
            if employee:
                domain = [('id', '=', employee.id)]
            else:
                domain = [('id', '=', False)]  
        
        employees = self.env['hr.employee'].search_read(
            domain,
            ['name', 'work_email', 'work_phone', 'user_id']
        )
        
        return employees