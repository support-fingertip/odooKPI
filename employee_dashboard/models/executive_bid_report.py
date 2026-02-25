# -*- coding: utf-8 -*-
from odoo import api, fields, models
import pytz
import logging

_logger = logging.getLogger(__name__)


class ExecutiveBeatReportWizard(models.TransientModel):
    _name = 'executive.beat.report.wizard'
    _description = 'Executive Beat Report'

    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.today,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Executive (Optional)',
        help='Leave empty to show all executives who attended on the selected date.',
    )
    line_ids = fields.One2many(
        'executive.beat.report.line',
        'wizard_id',
        string='Report Lines',
        readonly=True,
    )

    def action_generate(self):
        """Generate report lines for the selected date (and optionally a specific executive)."""
        self.line_ids.unlink()

        # Build attendance domain
        date_start = fields.Datetime.from_string(str(self.date) + ' 00:00:00')
        date_end = fields.Datetime.from_string(str(self.date) + ' 23:59:59')

        att_domain = [
            ('check_in', '>=', date_start),
            ('check_in', '<=', date_end),
        ]
        if self.employee_id:
            att_domain.append(('employee_id', '=', self.employee_id.id))

        attendances = self.env['hr.attendance'].sudo().search(att_domain, order='employee_id asc')

        # Deduplicate by employee (take the first check-in per employee for the day)
        seen_employees = {}
        for att in attendances:
            if att.employee_id.id not in seen_employees:
                seen_employees[att.employee_id.id] = att

        lines_to_create = []

        for employee_id, attendance in seen_employees.items():
            employee = attendance.employee_id

            # Fetch all beat switch history for this employee on this date (ordered by time)
            switches = self.env['beat.switch.history'].sudo().search([
                ('employee_id', '=', employee.id),
                ('switch_date', '=', self.date),
            ], order='switch_time asc')

            # Determine the starting beat
            if switches:
                # The first switch record tells us what beat was active at the beginning
                starting_beat = switches[0].start_beat_id
            else:
                # No switches: find the beat assigned to the employee for this date that is
                # not in 'swapped' status (only one such beat can exist per day by constraint)
                starting_beat = self.env['beat.module'].sudo().search([
                    ('employee_id', '=', employee.id),
                    ('beat_date', '=', self.date),
                    ('status', 'not in', ['swapped']),
                ], order='id asc', limit=1)

            # Build switch detail lines
            switch_details = []
            for sw in switches:
                switch_details.append((0, 0, {
                    'switch_time': sw.switch_time,
                    'from_beat_id': sw.start_beat_id.id,
                    'to_beat_id': sw.switched_beat_id.id,
                    'reason': sw.reason or '',
                }))

            lines_to_create.append({
                'wizard_id': self.id,
                'employee_id': employee.id,
                'check_in': attendance.check_in,
                'check_out': attendance.check_out,
                'starting_beat_id': starting_beat.id if starting_beat else False,
                'switch_count': len(switches),
                'switch_detail_ids': switch_details,
            })

        if lines_to_create:
            self.env['executive.beat.report.line'].create(lines_to_create)

        # Return same form view refreshed to display the generated lines
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'executive.beat.report.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
            'context': self.env.context,
        }

    def action_export_pdf(self):
        """Trigger the QWeb PDF report."""
        self.ensure_one()
        return self.env.ref(
            'employee_dashboard.action_report_executive_beat'
        ).report_action(self)


class ExecutiveBeatReportLine(models.TransientModel):
    _name = 'executive.beat.report.line'
    _description = 'Executive Beat Report Line'
    _order = 'employee_id asc'

    wizard_id = fields.Many2one(
        'executive.beat.report.wizard',
        required=True,
        ondelete='cascade',
    )
    employee_id = fields.Many2one('hr.employee', string='Executive', readonly=True)
    check_in = fields.Datetime(string='Check In', readonly=True)
    check_out = fields.Datetime(string='Check Out', readonly=True)
    starting_beat_id = fields.Many2one('beat.module', string='Assigned Beat (Start)', readonly=True)
    starting_beat_number = fields.Char(
        string='Beat No.',
        related='starting_beat_id.beat_number',
        readonly=True,
    )
    switch_count = fields.Integer(string='No. of Switches', readonly=True)
    switch_detail_ids = fields.One2many(
        'executive.beat.switch.detail',
        'line_id',
        string='Switch Details',
        readonly=True,
    )

    def action_view_switch_details(self):
        """Open a popup showing all switch details for this line."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Switch Details – {self.employee_id.name}',
            'res_model': 'executive.beat.report.line',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'dialog_size': 'large'},
        }


class ExecutiveBeatSwitchDetail(models.TransientModel):
    _name = 'executive.beat.switch.detail'
    _description = 'Executive Beat Switch Detail'
    _order = 'switch_time asc'

    line_id = fields.Many2one(
        'executive.beat.report.line',
        required=True,
        ondelete='cascade',
    )
    switch_time = fields.Datetime(string='Switch Time', readonly=True)
    from_beat_id = fields.Many2one('beat.module', string='From Beat', readonly=True)
    from_beat_number = fields.Char(
        string='From Beat No.',
        related='from_beat_id.beat_number',
        readonly=True,
    )
    to_beat_id = fields.Many2one('beat.module', string='To Beat', readonly=True)
    to_beat_number = fields.Char(
        string='To Beat No.',
        related='to_beat_id.beat_number',
        readonly=True,
    )
    reason = fields.Text(string='Reason', readonly=True)
