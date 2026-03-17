# -*- coding: utf-8 -*-
"""
emp360_mobile — Visit Model PATCH

PURPOSE:
  Override _check_store_image_required so mobile end-visit (context:
  mobile_end_visit=True OR skip_image_check=True) never raises
  "store image required" ValidationError.

  This is an _inherit patch — it ONLY overrides this one constraint.
  All fields and other methods remain from employee_dashboard.visit.model.
"""
from odoo import models, api, _
from odoo.exceptions import ValidationError


class VisitModelMobilePatch(models.Model):
    _inherit = 'visit.model'

    @api.constrains('status', 'store_image')
    def _check_store_image_required(self):
        """
        Store image required UNLESS mobile context bypasses it.

        Context flags that skip the check:
          mobile_end_visit=True              — set by emp360.mobile.end_visit()
          skip_image_check=True              — alternative flag (belt + suspenders)
          no_check_store_image_required=True — final fallback flag
        """
        ctx = self.env.context
        if (ctx.get('mobile_end_visit')
                or ctx.get('skip_image_check')
                or ctx.get('no_check_store_image_required')):
            return

        for record in self:
            if record.status == 'completed' and not record.store_image:
                raise ValidationError(
                    _('A Store Image is required to complete a visit. '
                      'Please upload a store photo before ending the visit.')
                )
