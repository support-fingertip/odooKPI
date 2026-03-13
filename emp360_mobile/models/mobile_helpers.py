"""
emp360_mobile — Mobile App Helper Model
Provides server-side helpers called by the OWL mobile components.
"""
from odoo import models, api, fields


class MobileAppHelpers(models.AbstractModel):
    """
    Abstract helper model for the Employee 360 Mobile App.
    All methods are stateless RPC helpers — no database records are created.
    """
    _name = "emp360.mobile"
    _description = "Employee 360 Mobile App Helpers"

    # ── Access / Role helpers ────────────────────────────────────────────────

    @api.model
    def get_user_access_info(self):
        """
        Returns the current user's employee ID and role.
        Called once on mobile app startup.
        """
        user = self.env.user
        employee = self.env["hr.employee"].search(
            [("user_id", "=", user.id)], limit=1
        )
        is_manager = user.has_group(
            "employee_dashboard.group_employee_dashboard_manager"
        )
        return {
            "user_id":     user.id,
            "user_name":   user.name,
            "employee_id": employee.id if employee else False,
            "is_manager":  is_manager,
        }

    @api.model
    def get_accessible_employees(self):
        """
        Returns all employees accessible to the current user.
        Managers see their entire department/subordinates; users see only themselves.
        """
        user = self.env.user
        is_manager = user.has_group(
            "employee_dashboard.group_employee_dashboard_manager"
        )
        if is_manager:
            employees = self.env["hr.employee"].search(
                [("active", "=", True)],
                order="name asc",
                limit=200,
            )
        else:
            employees = self.env["hr.employee"].search(
                [("user_id", "=", user.id)], limit=1
            )
        return employees.read(["id", "name", "job_title", "department_id", "job_id"])
