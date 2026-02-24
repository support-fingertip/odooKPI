from odoo import http
from odoo.http import request, Response
import json

class BeatCalendar(http.Controller):
    @http.route('/beatcalendar', auth='user')
    def beat_calendar(self, employee_id=None, **kwargs):
        return http.Response(f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <meta charset="utf-8">
                        <title>Beat Calendar</title>

                        <link href="/employee_dashboard/static/lib/fullcalendar/main.min.css" rel="stylesheet">

                        <style>
                            body {{ font-family: Arial; margin: 0; padding: 0; background: #f4f6f9; }}
                            header {{ background: #0057d8; color: white; padding: 20px; font-size: 15px; }}
                            #calendar-container {{ padding: 10px; }}
                            #calendar {{ background: white; padding: 10px; border-radius: 10px; }}
                        </style>
                    </head>

                    <body>

                    <script>
                        var EMPLOYEE_ID = {employee_id};
                    </script>

                    <header>Beat Calendar</header>

                    <div id="calendar-container">
                        <div id="calendar"></div>
                    </div>

                    <script src="/employee_dashboard/static/lib/fullcalendar/main.min.js"></script>

                    <script>
                        document.addEventListener("DOMContentLoaded", function () {{
                            var calendarEl = document.getElementById("calendar");
                            var calendar = new FullCalendar.Calendar(calendarEl, {{
                                initialView: "dayGridMonth",
                                height: "auto",
                                events: {{
                                    url: "/beatcalendar/events",
                                    method: "GET",
                                    extraParams: {{
                                        emp_id: EMPLOYEE_ID
                                    }},
                                }},
                            }});

                            calendar.render();
                        }});
                    </script>

                    </body>
                    </html>
                """, status=200, mimetype='text/html')

    @http.route('/beatcalendar/events', type='http', csrf=False)
    def beat_calendar_events(self, emp_id=0, **kwargs):
        records = request.env['beat.module'].sudo().search([('employee_id', '=', int(emp_id))], order='beat_date asc')
        events = []
        for rec in records:
            if not rec.beat_date:
                continue
            try:
                start_date = rec.beat_date.strftime('%Y-%m-%d')
            except Exception:
                start_date = str(rec.beat_date)[:10]

            events.append({
                "id": int(rec.id),
                "title": rec.beat_number or rec.name,
                "start": start_date,
                "allDay": True,
            })

        body = json.dumps(events)
        return Response(body, content_type='application/json;charset=utf-8')