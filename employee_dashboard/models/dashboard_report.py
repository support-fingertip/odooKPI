# -*- coding: utf-8 -*-
from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class DashboardReport(models.AbstractModel):
    """
    Abstract model that provides aggregated data for the
    all-in-one Dashboard Report component.

    All methods are @api.model so they can be called via
    orm.call('dashboard.report', 'method_name', [...]) from OWL.
    """
    _name = 'dashboard.report'
    _description = 'Dashboard Report – Data Provider'

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @api.model
    def get_dashboard_data(self, date_from=None, date_to=None,
                           employee_id=None, department_id=None):
        """
        Return a single dict with all data needed by the dashboard:
          kpi              – headline counters
          visit_status     – pie chart  (status distribution)
          monthly_visits   – multi-line (trend last N months)
          employee_visits  – bar chart  (top 10 employees by visit count)
          attendance       – bar chart  (top 10 employees by worked hours)
          monthly_attendance – bar chart (worked hours by month)
          beat_coverage    – pie chart  (beat status distribution)
          employee_switches– bar chart  (top 10 employees by switch count)
          pjp_status       – pie chart  (PJP state distribution)
          recent_visits         – list  (last 10 visits)
          recent_beat_reports   – list  (last 10 beat reports)
          recent_switch_history – list  (last 10 switch events)
        """
        today = fields.Date.today()

        # ── resolve dates ──────────────────────────────────────────────
        if not date_from:
            date_from = today.replace(day=1)        # first of current month
        if not date_to:
            date_to = today

        # String versions for ORM domain comparisons
        dt_from = str(date_from) + ' 00:00:00'
        dt_to   = str(date_to)   + ' 23:59:59'

        # ── optional employee filter ───────────────────────────────────
        emp_filter     = [('employee_id', '=', employee_id)]   if employee_id else []
        dept_filter_hr = [('department_id', '=', department_id)] if department_id else []

        # When dept_filter applies, collect employee ids in that dept
        dept_emp_filter = []
        if department_id and not employee_id:
            dept_emps = self.env['hr.employee'].sudo().search(
                [('department_id', '=', department_id)])
            if dept_emps:
                dept_emp_filter = [('employee_id', 'in', dept_emps.ids)]

        eff_emp_filter = emp_filter or dept_emp_filter  # effective employee filter

        # ------------------------------------------------------------------
        # 1.  VISIT data
        # ------------------------------------------------------------------
        visit_domain = [
            ('actual_start_time', '>=', dt_from),
            ('actual_start_time', '<=', dt_to),
        ] + eff_emp_filter

        Visit = self.env['visit.model'].sudo()
        all_visits = Visit.search(visit_domain)

        completed_visits  = all_visits.filtered(lambda v: v.status == 'completed')
        productive_visits = all_visits.filtered(lambda v: v.is_productive)
        total_order_amount = sum(completed_visits.mapped('total_order_amount'))

        # Visit status distribution
        visit_status_map = {}
        for v in all_visits:
            s = dict(v._fields['status'].selection).get(v.status, v.status or 'Unknown')
            visit_status_map[s] = visit_status_map.get(s, 0) + 1

        # Monthly visit trend (by actual_start_time)
        monthly_visits_map = {}
        for v in all_visits:
            if v.actual_start_time:
                mk = v.actual_start_time.strftime('%b %Y')
                if mk not in monthly_visits_map:
                    monthly_visits_map[mk] = {
                        'completed': 0, 'planned': 0,
                        'in_progress': 0, 'cancelled': 0,
                    }
                st = v.status or 'planned'
                monthly_visits_map[mk][st] = monthly_visits_map[mk].get(st, 0) + 1

        mv_labels = list(monthly_visits_map.keys())

        # Top 10 employees by visit count
        emp_visit_map = {}
        for v in all_visits:
            name = v.employee_id.name if v.employee_id else 'Unknown'
            if name not in emp_visit_map:
                emp_visit_map[name] = {'count': 0, 'amount': 0.0}
            emp_visit_map[name]['count'] += 1
            emp_visit_map[name]['amount'] += v.total_order_amount or 0.0

        top_emp_visits = sorted(
            emp_visit_map.items(), key=lambda x: x[1]['count'], reverse=True)[:10]

        # Visit productivity rate
        visit_productivity_map = {
            'Productive': len(productive_visits),
            'Non-Productive': len(all_visits) - len(productive_visits),
        }

        # ------------------------------------------------------------------
        # 2.  ATTENDANCE data
        # ------------------------------------------------------------------
        att_domain = [
            ('check_in', '>=', dt_from),
            ('check_in', '<=', dt_to),
        ] + eff_emp_filter

        Attendance = self.env['hr.attendance'].sudo()
        attendances = Attendance.search(att_domain)
        total_worked_hours = sum(attendances.mapped('worked_hours'))

        emp_att_map = {}
        for a in attendances:
            name = a.employee_id.name if a.employee_id else 'Unknown'
            emp_att_map[name] = emp_att_map.get(name, 0.0) + (a.worked_hours or 0.0)

        top_attendance = sorted(
            emp_att_map.items(), key=lambda x: x[1], reverse=True)[:10]

        monthly_att_map = {}
        for a in attendances:
            if a.check_in:
                mk = a.check_in.strftime('%b %Y')
                monthly_att_map[mk] = monthly_att_map.get(mk, 0.0) + (a.worked_hours or 0.0)

        # ------------------------------------------------------------------
        # 3.  EXECUTIVE BEAT REPORT data
        # ------------------------------------------------------------------
        beat_rep_domain = [
            ('date', '>=', str(date_from)),
            ('date', '<=', str(date_to)),
        ] + eff_emp_filter

        BeatReport = self.env['executive.beat.report'].sudo()
        beat_reports = BeatReport.search(beat_rep_domain)
        total_switches = sum(beat_reports.mapped('switch_count'))

        beat_switch_map = {
            'With Switches': len(beat_reports.filtered(lambda r: r.switch_count > 0)),
            'No Switches':   len(beat_reports.filtered(lambda r: r.switch_count == 0)),
        }

        emp_switch_map = {}
        for br in beat_reports:
            name = br.employee_id.name if br.employee_id else 'Unknown'
            emp_switch_map[name] = emp_switch_map.get(name, 0) + (br.switch_count or 0)

        top_switches = sorted(
            emp_switch_map.items(), key=lambda x: x[1], reverse=True)[:10]

        # Beat coverage (beat.module status distribution)
        beat_cov_domain = [
            ('beat_date', '>=', str(date_from)),
            ('beat_date', '<=', str(date_to)),
        ] + eff_emp_filter
        Beat = self.env['beat.module'].sudo()
        all_beats = Beat.search(beat_cov_domain)

        beat_status_map = {}
        for b in all_beats:
            label = dict(b._fields['status'].selection).get(b.status, b.status or 'Unknown')
            beat_status_map[label] = beat_status_map.get(label, 0) + 1

        # ------------------------------------------------------------------
        # 4.  BEAT SWITCH HISTORY data
        # ------------------------------------------------------------------
        sw_hist_domain = [
            ('switch_date', '>=', str(date_from)),
            ('switch_date', '<=', str(date_to)),
        ] + eff_emp_filter

        SwitchHistory = self.env['beat.switch.history'].sudo()
        switch_histories = SwitchHistory.search(sw_hist_domain)

        # ------------------------------------------------------------------
        # 5.  PJP data
        # ------------------------------------------------------------------
        pjp_domain = [
            ('start_date', '<=', str(date_to)),
            ('end_date', '>=', str(date_from)),
        ] + eff_emp_filter

        PJP = self.env['pjp.model'].sudo()
        pjps = PJP.search(pjp_domain)

        pjp_status_map = {}
        for p in pjps:
            label = dict(p._fields['state'].selection).get(p.state, p.state or 'Unknown')
            pjp_status_map[label] = pjp_status_map.get(label, 0) + 1

        # ------------------------------------------------------------------
        # 6.  Recent activity lists (latest 10 each)
        # ------------------------------------------------------------------
        recent_visits = []
        sorted_visits = sorted(
            all_visits,
            key=lambda v: v.actual_start_time or v.planned_start_time,
            reverse=True,
        )
        for v in sorted_visits[:10]:
            recent_visits.append({
                'name':     v.name or '',
                'employee': v.employee_id.name if v.employee_id else '',
                'customer': v.partner_id.name  if v.partner_id  else '',
                'status':   dict(v._fields['status'].selection).get(v.status, v.status or ''),
                'date':     v.actual_start_time.strftime('%d/%m/%Y') if v.actual_start_time else '',
                'amount':   round(v.total_order_amount or 0.0, 2),
            })

        recent_beat_reports = []
        for br in beat_reports.sorted(key=lambda r: r.date, reverse=True)[:10]:
            recent_beat_reports.append({
                'employee':      br.employee_id.name if br.employee_id else '',
                'department':    br.department_id.name if br.department_id else '',
                'date':          str(br.date),
                'assigned_beat': br.assigned_beat_number or '',
                'current_beat':  br.current_beat_number or '',
                'switches':      br.switch_count or 0,
                'worked_hours':  round(br.worked_hours or 0.0, 2),
            })

        recent_switch_history = []
        for sh in switch_histories.sorted(key=lambda r: r.switch_time, reverse=True)[:10]:
            recent_switch_history.append({
                'employee':  sh.employee_id.name if sh.employee_id else '',
                'date':      str(sh.switch_date),
                'time':      sh.switch_time.strftime('%H:%M') if sh.switch_time else '',
                'from_beat': sh.start_beat_id.beat_number   if sh.start_beat_id     else '',
                'to_beat':   sh.switched_beat_id.beat_number if sh.switched_beat_id  else '',
                'reason':    sh.reason or '',
            })

        currency_symbol = self.env.company.currency_id.symbol or '$'

        # ------------------------------------------------------------------
        # 7.  Assemble & return
        # ------------------------------------------------------------------
        return {
            'kpi': {
                'total_visits':          len(all_visits),
                'completed_visits':      len(completed_visits),
                'productive_visits':     len(productive_visits),
                'total_order_amount':    round(total_order_amount, 2),
                'currency_symbol':       currency_symbol,
                'total_worked_hours':    round(total_worked_hours, 2),
                'total_attendance':      len(attendances),
                'total_pjp':             len(pjps),
                'approved_pjp':          len(pjps.filtered(lambda p: p.state == 'approved')),
                'active_pjp':            len(pjps.filtered(lambda p: p.state == 'active')),
                'total_beat_reports':    len(beat_reports),
                'total_switches':        total_switches,
                'total_switch_history':  len(switch_histories),
                'total_beats':           len(all_beats),
            },
            'visit_status': {
                'labels': list(visit_status_map.keys()),
                'data':   list(visit_status_map.values()),
            },
            'visit_productivity': {
                'labels': list(visit_productivity_map.keys()),
                'data':   list(visit_productivity_map.values()),
            },
            'monthly_visits': {
                'labels':      mv_labels,
                'completed':   [monthly_visits_map[m].get('completed',   0) for m in mv_labels],
                'planned':     [monthly_visits_map[m].get('planned',     0) for m in mv_labels],
                'in_progress': [monthly_visits_map[m].get('in_progress', 0) for m in mv_labels],
                'cancelled':   [monthly_visits_map[m].get('cancelled',   0) for m in mv_labels],
            },
            'employee_visits': {
                'labels':  [x[0] for x in top_emp_visits],
                'counts':  [x[1]['count']  for x in top_emp_visits],
                'amounts': [round(x[1]['amount'], 2) for x in top_emp_visits],
            },
            'attendance': {
                'labels': [x[0]            for x in top_attendance],
                'hours':  [round(x[1], 2)  for x in top_attendance],
            },
            'monthly_attendance': {
                'labels': list(monthly_att_map.keys()),
                'hours':  [round(v, 2) for v in monthly_att_map.values()],
            },
            'beat_switch_dist': {
                'labels': list(beat_switch_map.keys()),
                'data':   list(beat_switch_map.values()),
            },
            'beat_coverage': {
                'labels': list(beat_status_map.keys()),
                'data':   list(beat_status_map.values()),
            },
            'employee_switches': {
                'labels': [x[0] for x in top_switches],
                'counts': [x[1] for x in top_switches],
            },
            'pjp_status': {
                'labels': list(pjp_status_map.keys()),
                'data':   list(pjp_status_map.values()),
            },
            'recent_visits':         recent_visits,
            'recent_beat_reports':   recent_beat_reports,
            'recent_switch_history': recent_switch_history,
        }

    @api.model
    def get_filter_options(self):
        """Return employees and departments for filter dropdowns."""
        employees   = self.env['hr.employee'].sudo().search([], order='name asc')
        departments = self.env['hr.department'].sudo().search([], order='name asc')
        return {
            'employees':   [{'id': e.id, 'name': e.name} for e in employees],
            'departments': [{'id': d.id, 'name': d.name} for d in departments],
        }
