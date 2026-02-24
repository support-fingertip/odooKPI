from odoo import api, fields, models, _
from odoo.exceptions import UserError
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import logging

_logger = logging.getLogger(__name__)


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    # Check-in Location
    checkin_latitude = fields.Float('Check-in Latitude', digits=(10, 7), readonly=True)
    checkin_longitude = fields.Float('Check-in Longitude', digits=(10, 7), readonly=True)
    checkin_accuracy = fields.Float('Check-in Accuracy (m)', digits=(10, 2), readonly=True)
    checkin_full_address = fields.Text('Check-in Address', readonly=True)
    checkin_city = fields.Char('Check-in City', readonly=True)
    checkin_state = fields.Char('Check-in State', readonly=True)
    checkin_country = fields.Char('Check-in Country', readonly=True)
    
    # Check-out Location
    checkout_latitude = fields.Float('Check-out Latitude', digits=(10, 7), readonly=True)
    checkout_longitude = fields.Float('Check-out Longitude', digits=(10, 7), readonly=True)
    checkout_accuracy = fields.Float('Check-out Accuracy (m)', digits=(10, 2), readonly=True)
    checkout_full_address = fields.Text('Check-out Address', readonly=True)
    checkout_city = fields.Char('Check-out City', readonly=True)
    checkout_state = fields.Char('Check-out State', readonly=True)
    checkout_country = fields.Char('Check-out Country', readonly=True)

    @api.model
    def reverse_geocode_location(self, latitude, longitude):
        """Reverse geocode coordinates to address"""
        try:
            geolocator = Nominatim(
                user_agent=f"odoo_attendance_{self.env.cr.dbname}",
                timeout=20
            )
            
            location = geolocator.reverse(
                f"{latitude},{longitude}",
                language='en',
                addressdetails=True,
                zoom=18
            )
            
            if not location:
                return None
            
            address = location.raw.get('address', {})
            
            city = (address.get('city') or 
                   address.get('town') or 
                   address.get('village') or 
                   address.get('municipality') or '')
            
            state = address.get('state', '')
            country = address.get('country', '')
            

            address_parts = []
            if address.get('house_number'):
                address_parts.append(address.get('house_number'))
            if address.get('road'):
                address_parts.append(address.get('road'))
            if address.get('suburb'):
                address_parts.append(address.get('suburb'))
            if city:
                address_parts.append(city)
            if state:
                address_parts.append(state)
            if address.get('postcode'):
                address_parts.append(address.get('postcode'))
            if country:
                address_parts.append(country)
            
            full_address = ', '.join(filter(None, address_parts))
            
            return {
                'full_address': full_address or location.raw.get('display_name', ''),
                'city': city,
                'state': state,
                'country': country,
            }
            
        except Exception as e:
            _logger.error(f"Geocoding error: {str(e)}")
            return None

    def action_view_checkin_location(self):
        """View check-in location on Google Maps"""
        self.ensure_one()
        if not self.checkin_latitude or not self.checkin_longitude:
            raise UserError(_('No check-in location available'))
        
        url = f'https://www.google.com/maps?q={self.checkin_latitude},{self.checkin_longitude}&z=18'
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }

    def action_view_checkout_location(self):
        """View check-out location on Google Maps"""
        self.ensure_one()
        if not self.checkout_latitude or not self.checkout_longitude:
            raise UserError(_('No check-out location available'))
        
        url = f'https://www.google.com/maps?q={self.checkout_latitude},{self.checkout_longitude}&z=18'
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }


    @api.model_create_multi
    def create(self, vals_list):
        """Override create to prevent automatic checkout"""
        if self.env.context.get('no_auto_checkout'):
            for vals in vals_list:
                if 'check_out' in vals:
                    del vals['check_out']
        
        return super(HrAttendance, self).create(vals_list)

    def write(self, vals):
        """Override write - allow manual checkout"""
        if 'check_out' in vals:
            if not (self.env.context.get('manual_checkout') or 
                    self.env.context.get('force_write') or 
                    self.env.context.get('tracking_disable')):
                _logger.warning(f"Blocked automatic checkout for attendance {self.ids}")
                vals = {k: v for k, v in vals.items() if k != 'check_out'}
        
        return super(HrAttendance, self).write(vals)
    
    @api.constrains('check_in', 'check_out')
    def _check_validity(self):
        """Override to allow manual checkouts"""
        if self.env.context.get('manual_checkout') or self.env.context.get('force_write'):
            return True
        return super(HrAttendance, self)._check_validity()


class HrAttendanceOvertime(models.Model):
    _inherit = 'hr.attendance.overtime'

    @api.model_create_multi
    def create(self, vals_list):
        """
        Override to prevent duplicate overtime records
        Delete existing record before creating new one
        """
        for vals in vals_list:
            if 'employee_id' in vals and 'date' in vals:
                existing = self.sudo().search([
                    ('employee_id', '=', vals['employee_id']),
                    ('date', '=', vals['date'])
                ])
                
                if existing:
                    _logger.info(f"Deleting existing overtime record for employee {vals['employee_id']} on {vals['date']}")
                    existing.unlink()
        
        return super(HrAttendanceOvertime, self).create(vals_list)