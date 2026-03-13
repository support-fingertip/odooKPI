# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import math
import logging

_logger = logging.getLogger(__name__)


class GeoFenceConfig(models.Model):
    """Admin-configurable geo-fence per customer/partner."""
    _name = 'geo.fence.config'
    _description = 'Geo-Fence Configuration'
    _order = 'partner_id'

    partner_id = fields.Many2one(
        'res.partner', string='Customer / Store', required=True,
        ondelete='cascade', index=True)
    latitude = fields.Float(string='Latitude', digits=(10, 7), required=True)
    longitude = fields.Float(string='Longitude', digits=(10, 7), required=True)
    radius_meters = fields.Integer(
        string='Allowed Radius (meters)', default=200, required=True,
        help='Maximum distance in meters from store location for check-in to be valid')
    active = fields.Boolean(string='Active', default=True)
    notes = fields.Text(string='Notes')

    _sql_constraints = [
        ('unique_partner', 'UNIQUE(partner_id)',
         'Only one geo-fence can be configured per customer.')
    ]

    @api.constrains('radius_meters')
    def _check_radius(self):
        for rec in self:
            if rec.radius_meters < 10:
                raise ValidationError(_("Radius must be at least 10 meters."))

    @api.model
    def validate_checkin(self, partner_id, latitude, longitude):
        """
        Validate check-in coordinates against configured geo-fence.
        Returns dict: {valid: bool, distance: float, allowed_radius: int, message: str}
        """
        fence = self.sudo().search(
            [('partner_id', '=', partner_id), ('active', '=', True)], limit=1)

        if not fence:
            # No geo-fence configured → always allow
            return {'valid': True, 'distance': 0, 'allowed_radius': 0,
                    'message': 'No geo-fence configured for this customer.'}

        distance = self._haversine_distance(
            latitude, longitude, fence.latitude, fence.longitude)

        if distance <= fence.radius_meters:
            return {
                'valid': True,
                'distance': round(distance, 1),
                'allowed_radius': fence.radius_meters,
                'message': f'Check-in valid. You are {round(distance, 0):.0f}m from store.',
            }
        else:
            return {
                'valid': False,
                'distance': round(distance, 1),
                'allowed_radius': fence.radius_meters,
                'message': (
                    f'You are {round(distance, 0):.0f}m away from the store. '
                    f'Allowed radius is {fence.radius_meters}m. '
                    'Please move closer to the store to check-in.'
                ),
            }

    @staticmethod
    def _haversine_distance(lat1, lon1, lat2, lon2):
        """Calculate distance in meters between two GPS coordinates."""
        R = 6371000  # Earth radius in metres
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = (math.sin(dphi / 2) ** 2 +
             math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
