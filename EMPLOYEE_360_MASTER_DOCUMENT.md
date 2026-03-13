# Employee 360 — Project Document

**Document Classification:** Internal Technical Reference
**Platform:** Odoo 18 Community
**Prepared For:** Development Team
**Date:** March 2026

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Architecture Overview](#2-system-architecture-overview)
3. [Module Inventory](#3-module-inventory)
4. [Module 1: Beat Module (`beat_module`)](#4-module-1-beat-module)
5. [Module 2: Employee Dashboard (`employee_dashboard`)](#5-module-2-employee-dashboard)
6. [Module 3: KPI Target Tracker (`kpi_target`)](#6-module-3-kpi-target-tracker)
7. [Complete Data Model & Relationship Map](#7-complete-data-model--relationship-map)
8. [Step-by-Step Functional Workflows](#8-step-by-step-functional-workflows)
9. [Frontend Architecture (OWL Components)](#9-frontend-architecture-owl-components)
10. [API & RPC Endpoints Reference](#10-api--rpc-endpoints-reference)
11. [KPI Computation Pipeline](#11-kpi-computation-pipeline)
12. [Security & Access Control](#12-security--access-control)
13. [Third-Party Libraries & Dependencies](#13-third-party-libraries--dependencies)
14. [Git History & Change Summary](#14-git-history--change-summary)
15. [Deployment Checklist](#15-deployment-checklist)

---

## 1. Executive Summary

**Employee 360** is a field-force management platform built as a set of three custom Odoo 18 modules. It enables organizations to plan, track, and evaluate the complete daily field activity of sales executives — from the moment they start their workday through every customer visit, sales order, beat plan, and finally the end of day — while continuously feeding live data into a KPI performance dashboard visible to managers.

### Business Problem Solved

| Pain Point | Solution Delivered |
|---|---|
| No visibility into field executive daily movement | Beat planning + PJP calendar with drag-and-drop |
| Manual attendance without location proof | GPS check-in/check-out recorded against `hr.attendance` |
| Sales orders not linked to field visits | `sale.order.visit_id` field creates a hard link |
| No structured customer visit lifecycle | `visit.model` with Start → End → Photo proof |
| KPI targets set but never measured in real-time | OWL KPI Dashboard auto-computes actuals from live data |
| Manager unable to see beat switch patterns | Executive Beat Report with full switch history |

### Key Numbers (from codebase)

- **3 Odoo modules** installed as a single solution
- **17 custom database models** (new or inherited)
- **5 KPI types** tracked per employee per period
- **8 OWL frontend components** built with the Odoo 18 OWL framework
- **2 HTTP controller routes** for the FullCalendar beat calendar view
- **2 user security groups** (User / Manager) with data isolation

---

## 2. System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         ODOO 18 COMMUNITY                               │
│                                                                         │
│  ┌──────────────┐   ┌──────────────────────┐   ┌────────────────────┐  │
│  │ beat_module  │   │  employee_dashboard   │   │    kpi_target      │  │
│  │  v1.1.0      │◄──│       v1.0            │──►│    v18.0.2.0.0     │  │
│  │              │   │                      │   │                    │  │
│  │ beat.module  │   │ visit.model          │   │ kpi.target         │  │
│  │ beat.line    │   │ pjp.model            │   │ kpi.target.period  │  │
│  │ beat.switch  │   │ pjp.item             │   │ kpi.manager.target │  │
│  │  .history    │   │ employee.dashboard   │   │ kpi.actual         │  │
│  │ res.partner* │   │ hr.employee*         │   │ kpi.target.item    │  │
│  │              │   │ hr.attendance*       │   │                    │  │
│  │              │   │ sale.order*          │   │                    │  │
│  │              │   │ sale.order.line*     │   │                    │  │
│  │              │   │ executive.beat.      │   │                    │  │
│  │              │   │   report (wizard)    │   │                    │  │
│  └──────────────┘   └──────────────────────┘   └────────────────────┘  │
│         │                     │                          │              │
│         └─────────────────────┼──────────────────────────┘              │
│                               ▼                                         │
│              ┌─────────────────────────────────────┐                   │
│              │   Odoo Core Models (dependencies)    │                   │
│              │   hr, hr_timesheet, base, contacts,  │                   │
│              │   sale, web                          │                   │
│              └─────────────────────────────────────┘                   │
└─────────────────────────────────────────────────────────────────────────┘

* = inherited / extended model
```

### Technology Stack

| Layer | Technology |
|---|---|
| Backend Framework | Odoo 18 Community (Python 3.x) |
| Frontend Framework | OWL (Odoo Web Library) — reactive component framework |
| Database | PostgreSQL |
| Calendar UI | FullCalendar.js v5 |
| Charting | Chart.js |
| Maps / Geocoding | Leaflet.js + geopy (Nominatim) |
| Data Tables | DataTables.js |
| Location Reverse Geocoding | OpenStreetMap Nominatim API |

---

## 3. Module Inventory

### 3.1 Dependency Graph

```
beat_module
  └── depends: base, contacts, hr

employee_dashboard
  └── depends: hr, hr_timesheet
       └── (uses beat_module models at runtime)

kpi_target
  └── depends: base, hr, web
       └── (uses visit.model and sale.order at runtime)
```

### 3.2 Module Summary Table

| Module | Technical Name | Version | Type | Purpose |
|---|---|---|---|---|
| Beat Module | `beat_module` | 1.1.0 | Application | Beat planning, customer-to-beat assignment, beat swap |
| Employee Dashboard | `employee_dashboard` | 1.0 | Add-on | Visit tracking, PJP planning, attendance, daily cycle |
| KPI Target Tracker | `kpi_target` | 18.0.2.0.0 | Application | Target setting, actual tracking, OWL KPI dashboard |

---

## 4. Module 1: Beat Module

### 4.1 Purpose

A **Beat** is a pre-planned route/area containing a list of customers that a sales executive is scheduled to visit on a specific date. The Beat Module manages the master list of beats, assigns customers to beats, enforces a "one beat per employee per day" rule, and records beat switch history when an executive changes from one beat to another mid-day.

### 4.2 Data Models

#### 4.2.1 `beat.module` — Beat Master

```python
# beat_module/models/beat.py

class BeatModule(models.Model):
    _name = 'beat.module'
    _description = 'Beat Module'
    _order = 'beat_number'

    beat_number  = fields.Char(string='Beat Number', readonly=True, default='New')
    name         = fields.Char(string='Name', required=True)
    employee_id  = fields.Many2one('hr.employee', required=True)
    beat_date    = fields.Date(string='Assigned Date')
    beat_line_ids = fields.One2many('beat.line', 'beat_id', string='Beat Lines')
    customer_count = fields.Integer(compute='_compute_customer_count', store=True)

    status = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('swapped', 'Swapped'),
    ], default='pending')

    # Swap tracking fields
    swap_reason         = fields.Text()
    swapped_date        = fields.Datetime()
    swapped_to_beat_id   = fields.Many2one('beat.module')
    swapped_from_beat_id = fields.Many2one('beat.module')
```

**Key Business Constraint — One Beat Per Day:**

```python
@api.constrains('beat_date', 'employee_id')
def _check_one_beat_per_day(self):
    """
    Enforce ONE DAY ONE BEAT rule.
    Swapped beats are excluded so the replacement beat can be assigned
    to the same date as the original.
    """
    for record in self:
        if record.status == 'swapped':
            continue                          # swapped beats bypass the rule
        if record.beat_date and record.employee_id:
            existing_beats = self.search([
                ('id', '!=', record.id),
                ('employee_id', '=', record.employee_id.id),
                ('beat_date', '=', record.beat_date),
                ('status', '!=', 'swapped'),
            ])
            if existing_beats:
                raise ValidationError(
                    f"Only one beat can be assigned per day!\n\n"
                    f"Employee '{record.employee_id.name}' already has "
                    f"beat '{existing_beats[0].beat_number}' assigned on {record.beat_date}."
                )
```

**Auto Beat Number via IR Sequence:**

```python
@api.model
def create(self, vals):
    if not vals.get('beat_number') or vals.get('beat_number') == 'New':
        vals['beat_number'] = self.env['ir.sequence'].next_by_code(
            'beat.module.sequence') or 'New'
    record = super(BeatModule, self).create(vals)
    record._check_one_beat_per_day()
    return record
```

#### 4.2.2 `beat.line` — Customer-to-Beat Assignment

```python
class BeatLine(models.Model):
    _name = 'beat.line'
    _order = 'sequence, id'

    beat_id      = fields.Many2one('beat.module', ondelete='cascade')
    sequence     = fields.Integer(default=10)
    partner_id   = fields.Many2one('res.partner', required=True)

    # Denormalized contact fields (stored=True for quick reporting)
    partner_phone   = fields.Char(related='partner_id.phone',   store=True, readonly=True)
    partner_mobile  = fields.Char(related='partner_id.mobile',  store=True, readonly=True)
    partner_email   = fields.Char(related='partner_id.email',   store=True, readonly=True)
    partner_street  = fields.Char(related='partner_id.street',  store=True, readonly=True)
    notes           = fields.Text()

    _sql_constraints = [
        ('unique_partner_beat', 'unique(beat_id, partner_id)',
         'This customer is already assigned to this beat!')
    ]
```

#### 4.2.3 `beat.switch.history` — Audit Trail of Beat Changes

```python
class BeatSwitchHistory(models.Model):
    _name = 'beat.switch.history'
    _order = 'switch_time desc'

    employee_id      = fields.Many2one('hr.employee',  required=True, index=True)
    switch_date      = fields.Date(required=True)
    switch_time      = fields.Datetime(required=True)
    start_beat_id    = fields.Many2one('beat.module', required=True)
    switched_beat_id = fields.Many2one('beat.module', required=True)
    reason           = fields.Text(required=True)
```

#### 4.2.4 `res.partner` (Extended)

The `res.partner` model is extended to show how many beats a customer appears in:

```python
class ResPartner(models.Model):
    _inherit = "res.partner"

    beat_line_ids = fields.One2many('beat.line', 'partner_id', string="Beat Assignments")
    beat_count    = fields.Integer(compute='_compute_beat_count')
```

### 4.3 Beat Swap Workflow

When a field executive needs to switch from their assigned beat to a different beat mid-day, the system executes this logic:

```python
def action_swap_beat(self, new_beat_id, reason):
    """
    Workflow:
    1. Mark the current (original) beat as 'swapped'
    2. Record swap reason, timestamp, and linked beat reference
    3. Set the new beat to 'in_progress' and assign today's date
    4. Write an audit record to beat.switch.history
    """
    self.write({
        'status': 'swapped',
        'swap_reason': reason,
        'swapped_date': fields.Datetime.now(),
        'swapped_to_beat_id': new_beat.id,
    })
    new_beat.write({
        'status': 'in_progress',
        'swapped_from_beat_id': self.id,
        'beat_date': today_date,
    })
    self.env['beat.switch.history'].create({
        'employee_id': self.employee_id.id,
        'switch_date': fields.Date.today(),
        'switch_time': fields.Datetime.now(),
        'start_beat_id': self.id,
        'switched_beat_id': new_beat.id,
        'reason': reason,
    })
```

### 4.4 Drag-and-Drop Beat Copy (Calendar)

When a user drags a beat to a new date in the PJP calendar, a **new beat is created** (not moved), preserving history:

```python
def copy_to_date(self, target_date):
    """Create a new beat by copying this beat to a different date.
    All beat lines (customers) are explicitly copied to the new beat.
    """
    beat_lines = [(0, 0, {
        'partner_id': line.partner_id.id,
        'sequence': line.sequence,
        'notes': line.notes,
    }) for line in self.beat_line_ids]

    new_beat = self.env['beat.module'].create({
        'name': self.name,
        'employee_id': self.employee_id.id,
        'beat_date': target_date,
        'status': 'pending',
        'beat_line_ids': beat_lines,
    })
    return {'id': new_beat.id, 'beat_number': new_beat.beat_number, ...}
```

### 4.5 Beat Rotation (Monthly Planning)

The system supports automatic beat rotation — assigning beats to dates across a month according to a configurable rotation frequency:

```python
def rotate_beats_in_month(self, month, year, rotation_frequency):
    """
    Algorithm:
    - Collect all beats assigned in the target month.
    - Walk day-by-day from start_date to end_of_month.
    - On day N: beat_index = (day_count % rotation_frequency)
    - If beat_index < total_beats: assign that beat to the date.
    - For repeat rotations beyond the first cycle, CREATE new beat records
      with '(Rotation N)' suffix — so history is never overwritten.

    Example: 3 beats, rotation_frequency=5
      Day 1 → Beat A
      Day 2 → Beat B
      Day 3 → Beat C
      Day 4 → (empty)
      Day 5 → (empty)
      Day 6 → Beat A (Rotation 2 — new record created)
    """
```

---

## 5. Module 2: Employee Dashboard

### 5.1 Purpose

The Employee Dashboard is the operational heart of the system. It provides:

1. A **multi-tab Odoo backend client action** for viewing employee data (details, visits, PJP, orders, attendance, invoices, expenses)
2. The **Today's Visit** real-time panel — the mobile-friendly UI used by field executives throughout their day
3. The **Permanent Journey Plan (PJP)** planner — a full-calendar drag-and-drop interface for assigning beats to future dates
4. **Attendance with GPS** — check-in/check-out that captures coordinates and reverse-geocodes them to a human-readable address
5. The **Executive Beat Report** — a management report showing each executive's check-in times, assigned beats, and beat switch history per day

### 5.2 Data Models

#### 5.2.1 `visit.model` — Customer Visit Record

```python
class VisitModel(models.Model):
    _name = 'visit.model'
    _description = 'Customer Visit'
    _order = 'actual_start_time desc'

    name              = fields.Char(default='New', readonly=True)  # auto-sequence VISIT/YYYYMM/XXXXX
    employee_id       = fields.Many2one('hr.employee', required=True)
    partner_id        = fields.Many2one('res.partner', required=True)
    beat_id           = fields.Many2one('beat.module')
    beat_line_id      = fields.Many2one('beat.line')

    # Timing
    planned_start_time  = fields.Datetime()
    actual_start_time   = fields.Datetime()
    planned_end_time    = fields.Datetime()
    actual_end_time     = fields.Datetime()
    duration            = fields.Float(compute='_compute_duration', store=True)

    # Classification
    visit_for = fields.Selection([
        ('Primary Customer', 'Primary Customer'),
        ('Secondary Customer', 'Secondary Customer'),
        ('Prospect', 'Prospect'),
    ])
    today_work_plan = fields.Selection([
        ('Customer Visit', 'Customer Visit'),
        ('Conference', 'Conference'),
        ('Training', 'Training'),
        ('Seminar', 'Seminar'),
        ('Enter Odometer Reading', 'Enter Odometer Reading'),
    ])
    travel_type   = fields.Selection(['Headquarters', 'Up country', 'Other'])
    vehicle_used  = fields.Selection(['Personal/own', 'Office', 'Public transport'])

    status = fields.Selection([
        ('planned', 'Planned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], default='planned')

    is_productive     = fields.Boolean(default=True)
    visit_comments    = fields.Text()
    store_image       = fields.Binary(attachment=True)     # REQUIRED to complete visit

    # Sales integration
    order_ids            = fields.One2many('sale.order', 'visit_id')
    order_count          = fields.Integer(compute='_compute_order_count', store=True)
    total_order_amount   = fields.Monetary(compute='_compute_total_order_amount', store=True)
```

**Store Image Constraint:**

```python
@api.constrains('status', 'store_image')
def _check_store_image_required(self):
    """A store photo is mandatory before a visit can be marked Completed."""
    for record in self:
        if record.status == 'completed' and not record.store_image:
            raise ValidationError(
                _('A Store Image (attachment) is required to mark a visit as Completed.')
            )
```

**KPI Recompute Trigger:**

```python
def write(self, vals):
    result = super(VisitModel, self).write(vals)
    if vals.get('status') == 'completed':
        self._trigger_kpi_recompute()   # notifies kpi_target module
    return result

def _trigger_kpi_recompute(self):
    """
    When a visit is completed, find all KPI targets for the employee
    and force recalculation of actuals and achievement percentages
    so the manager dashboard reflects the change immediately.
    """
    kpi_targets = self.env['kpi.target'].sudo().search([
        ('employee_id', '=', record.employee_id.id),
    ])
    kpi_targets._compute_actuals()
    kpi_targets.flush_recordset([...])
    kpi_targets._compute_achievements()
    kpi_targets.flush_recordset([...])
```

#### 5.2.2 `pjp.model` — Permanent Journey Plan Header

```python
class PJPModel(models.Model):
    _name = 'pjp.model'
    _description = 'Permanent Journey Plan'
    _order = 'start_date desc'

    name         = fields.Char(compute='_compute_name', store=True)
    employee_id  = fields.Many2one('hr.employee', required=True)
    start_date   = fields.Date(required=True)
    end_date     = fields.Date(required=True)
    pjp_item_ids = fields.One2many('pjp.item', 'pjp_id')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], default='draft')
```

#### 5.2.3 `pjp.item` — Individual Day in a PJP

```python
class PJPItem(models.Model):
    _name = 'pjp.item'
    _order = 'date asc, sequence asc'

    pjp_id           = fields.Many2one('pjp.model', ondelete='cascade')
    employee_id      = fields.Many2one(related='pjp_id.employee_id', store=True)
    assigned_beat_id = fields.Many2one('beat.module', required=True)
    approved_beat_id = fields.Many2one('beat.module')
    date             = fields.Date(required=True)
    sequence         = fields.Integer(default=10)

    status = fields.Selection([
        ('draft', 'Draft'), ('approved', 'Approved'),
        ('completed', 'Completed'), ('cancelled', 'Cancelled'),
    ], default='draft')
```

#### 5.2.4 `hr.employee` (Extended — Two Separate Inheritance Classes)

The `hr.employee` model is extended in **two files** for different responsibilities:

**File 1: `hr_employee.py`** — adds personal fields and PJP/rotation methods

```python
class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    joining_date   = fields.Date()
    relieving_date = fields.Date()
    pan_number     = fields.Char()
    aadhar_number  = fields.Char()

    def rotate_beats_in_month(self, month, year, rotation_frequency): ...
    def create_pjp_from_calendar(self, start_date, end_date): ...
```

**File 2: `pjp_model.py`** — adds attendance methods and dashboard helper

```python
class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def create_attendance_checkin(self, employee_id, work_plan, travel_type,
                                   vehicle_used, location_data=None): ...
    def create_attendance_checkout(self, employee_id, attendance_id,
                                    location_data=None): ...
    def get_today_attendance(self, employee_id): ...
```

#### 5.2.5 `hr.attendance` (Extended)

GPS location fields are added to the standard Odoo attendance record:

```python
class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    # Check-in Location
    checkin_latitude       = fields.Float(digits=(10, 7), readonly=True)
    checkin_longitude      = fields.Float(digits=(10, 7), readonly=True)
    checkin_accuracy       = fields.Float(digits=(10, 2), readonly=True)   # metres
    checkin_full_address   = fields.Text(readonly=True)
    checkin_city           = fields.Char(readonly=True)
    checkin_state          = fields.Char(readonly=True)
    checkin_country        = fields.Char(readonly=True)

    # Check-out Location (same set of fields)
    checkout_latitude      = fields.Float(digits=(10, 7), readonly=True)
    # ... (same pattern as check-in)
```

**Reverse Geocoding:**

```python
@api.model
def reverse_geocode_location(self, latitude, longitude):
    """
    Uses geopy (Nominatim / OpenStreetMap) to convert GPS coordinates
    to a structured address: house_number, road, suburb, city, state,
    postcode, country.
    Returns: {'full_address': '...', 'city': '...', 'state': '...', 'country': '...'}
    """
    geolocator = Nominatim(
        user_agent=f"odoo_attendance_{self.env.cr.dbname}",
        timeout=20
    )
    location = geolocator.reverse(f"{latitude},{longitude}", ...)
```

#### 5.2.6 `sale.order` and `sale.order.line` (Extended)

```python
class SaleOrder(models.Model):
    _inherit = 'sale.order'

    visit_id = fields.Many2one('visit.model', ondelete='set null')
    beat_id  = fields.Many2one('beat.module', related='visit_id.beat_id', store=True)

    def write(self, vals):
        result = super().write(vals)
        # When order is confirmed/done/cancelled, update KPI actuals immediately
        if vals.get('state') in ('sale', 'done', 'cancel') or 'user_id' in vals:
            self._trigger_kpi_recompute()
        return result

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    visit_id = fields.Many2one('visit.model',
        related='order_id.visit_id', store=True, readonly=True)
```

#### 5.2.7 `executive.beat.report` — Daily Beat Audit Report

```python
class ExecutiveBeatReport(models.Model):
    _name = 'executive.beat.report'
    _order = 'date desc, employee_id asc'

    employee_id       = fields.Many2one('hr.employee', readonly=True)
    date              = fields.Date(readonly=True)
    check_in          = fields.Datetime(readonly=True)
    check_out         = fields.Datetime(readonly=True)
    worked_hours      = fields.Float(compute='_compute_worked_hours', store=True)
    assigned_beat_id  = fields.Many2one('beat.module')   # starting beat
    current_beat_id   = fields.Many2one('beat.module')   # last beat of the day
    switch_count      = fields.Integer(default=0)
    switch_ids        = fields.One2many('executive.beat.report.switch', 'report_id')

    _sql_constraints = [
        ('unique_employee_date', 'UNIQUE(employee_id, date)',
         'Only one report per executive per day.'),
    ]
```

### 5.3 HTTP Controllers

#### Route 1: Beat Calendar View

```python
@http.route('/beatcalendar', auth='user')
def beat_calendar(self, employee_id=None, **kwargs):
    """
    Returns a standalone HTML page embedding FullCalendar.js.
    The calendar fetches beat events via /beatcalendar/events.
    EMPLOYEE_ID is injected as a JavaScript variable.
    """
```

#### Route 2: Beat Calendar Events Feed

```python
@http.route('/beatcalendar/events', type='http', csrf=False)
def beat_calendar_events(self, emp_id=0, **kwargs):
    """
    Returns a JSON array of FullCalendar event objects:
    [
        {
            "id": 42,
            "title": "BT/2024/0001",
            "start": "2024-11-15",
            "allDay": true
        },
        ...
    ]
    """
    records = request.env['beat.module'].sudo().search(
        [('employee_id', '=', int(emp_id))], order='beat_date asc')
```

---

## 6. Module 3: KPI Target Tracker

### 6.1 Purpose

The KPI Target Tracker allows managers to set structured performance targets for employees (or whole teams) for a defined time period, then automatically computes how much of each target has been achieved in real time — sourcing actual data directly from `visit.model` and `sale.order`.

### 6.2 Data Models

#### 6.2.1 `kpi.target.period` — Reporting Period

```python
class KpiTargetPeriod(models.Model):
    _name = 'kpi.target.period'
    _order = 'date_from desc'

    name        = fields.Char(required=True)
    period_type = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
    ], default='monthly')
    date_from = fields.Date(required=True)
    date_to   = fields.Date(required=True)
    active    = fields.Boolean(default=True)

    @api.onchange('period_type', 'date_from')
    def _onchange_auto_fill(self):
        """
        Auto-generates period name and end date:
        - Monthly:   name='November 2024'  date_to = date_from + 1 month - 1 day
        - Quarterly: name='Q4 2024'        date_to = date_from + 3 months - 1 day
        - Yearly:    name='2024'           date_to = date_from + 1 year - 1 day
        """
```

#### 6.2.2 `kpi.target` — Individual Employee Target

```python
# Supported KPI types
KPI_TYPES = [
    ('orders',              'Orders'),
    ('visits',              'Visits'),
    ('new_dealers',         'New Dealers'),
    ('payment_collected',   'Payment Collected'),
    ('complaints_solved',   'Complaints Solved'),
]

class KpiTarget(models.Model):
    _name = 'kpi.target'
    _sql_constraints = [
        ('unique_employee_period', 'UNIQUE(employee_id, period_id)',
         'Each employee can have only one target per period!')
    ]

    employee_id   = fields.Many2one('hr.employee', required=True)
    period_id     = fields.Many2one('kpi.target.period', required=True)
    manager_target_id = fields.Many2one('kpi.manager.target')  # set if part of a team target

    state = fields.Selection([('draft','Draft'),('confirmed','Confirmed'),('done','Done')])

    # Target fields (set by manager)
    target_orders              = fields.Float()
    target_visits              = fields.Float()
    target_new_dealers         = fields.Float()
    target_payment_collected   = fields.Float()
    target_complaints_solved   = fields.Float()

    # Actual fields (auto-computed from live data)
    actual_orders              = fields.Float(compute='_compute_actuals', store=True)
    actual_order_amount        = fields.Float(compute='_compute_actuals', store=True)
    actual_visits              = fields.Float(compute='_compute_actuals', store=True)
    actual_new_dealers         = fields.Float(compute='_compute_actuals', store=True)
    actual_payment_collected   = fields.Float(compute='_compute_actuals', store=True)
    actual_complaints_solved   = fields.Float(compute='_compute_actuals', store=True)

    # Achievement percentages (computed from actuals vs targets)
    achievement_orders         = fields.Float(compute='_compute_achievements', store=True)
    achievement_visits         = fields.Float(compute='_compute_achievements', store=True)
    achievement_new_dealers    = fields.Float(compute='_compute_achievements', store=True)
    achievement_payment_collected = fields.Float(compute='_compute_achievements', store=True)
    achievement_complaints_solved = fields.Float(compute='_compute_achievements', store=True)
    overall_achievement        = fields.Float(compute='_compute_achievements', store=True)
```

#### 6.2.3 `kpi.manager.target` — Team Target

```python
class KpiManagerTarget(models.Model):
    _name = 'kpi.manager.target'
    _sql_constraints = [
        ('unique_manager_period', 'UNIQUE(manager_id, period_id)',
         'A manager can have only one team target per period!')
    ]

    manager_id      = fields.Many2one('hr.employee', required=True)
    period_id       = fields.Many2one('kpi.target.period', required=True)

    assignment_mode = fields.Selection([
        ('distribute', 'Distribute Total Among Members'),
        ('individual', 'Assign Individually Per Member'),
    ], default='distribute')

    # Team-level target totals
    total_target_orders            = fields.Float()
    total_target_visits            = fields.Float()
    total_target_new_dealers       = fields.Float()
    total_target_payment_collected = fields.Float()
    total_target_complaints_solved = fields.Float()

    member_target_ids = fields.One2many('kpi.target', 'manager_target_id')

    # Computed: sum of member allocations vs total targets
    team_allocated_orders   = fields.Float(compute='_compute_team_totals', store=True)
    unallocated_orders      = fields.Float(compute='_compute_unallocated', store=True)
    is_fully_allocated      = fields.Boolean(compute='_compute_unallocated', store=True)

    # Computed: sum of all member actuals
    team_actual_orders      = fields.Float(compute='_compute_team_actuals', store=True)
    team_overall_achievement = fields.Float(compute='_compute_team_achievement', store=True)
```

**Equal Distribution Action:**

```python
def action_distribute_equally(self):
    """Divide total targets equally among all team members."""
    count = len(self.member_target_ids)
    vals = {
        'target_orders':            round(self.total_target_orders / count, 2),
        'target_visits':            round(self.total_target_visits / count, 2),
        'target_new_dealers':       round(self.total_target_new_dealers / count, 2),
        'target_payment_collected': round(self.total_target_payment_collected / count, 2),
        'target_complaints_solved': round(self.total_target_complaints_solved / count, 2),
    }
    self.member_target_ids.write(vals)
```

#### 6.2.4 `kpi.actual` — Manual Actual Entry

For KPI types that cannot be auto-sourced from Odoo data (e.g., `new_dealers`, `payment_collected`, `complaints_solved`), managers or executives enter manual values:

```python
class KpiActual(models.Model):
    _name = 'kpi.actual'
    _order = 'date desc'

    target_id  = fields.Many2one('kpi.target', required=True, ondelete='cascade')
    kpi_type   = fields.Selection(KPI_TYPE_SELECTION, required=True)
    value      = fields.Float(required=True)
    date       = fields.Date(default=fields.Date.context_today)
    notes      = fields.Text()
```

#### 6.2.5 `kpi.target.item` — KPI Line Item

When a `kpi.target` is created or its target fields are changed, `sync_target_items()` is called to maintain a set of `kpi.target.item` records — one per KPI type — that can be displayed in form views with individual target/actual/achievement columns.

---

## 7. Complete Data Model & Relationship Map

```
res.partner (Odoo Core — extended)
    │
    └──[beat_line_ids]──► beat.line ◄──[beat_id]── beat.module
                                                        │
                                                 [employee_id]
                                                        │
                                                  hr.employee (Core — extended)
                                                        │
                               ┌────────────────────────┼──────────────────────────┐
                               │                        │                          │
                          [employee_id]           [employee_id]             [employee_id]
                               │                        │                          │
                         hr.attendance            visit.model               kpi.target
                         (extended)               (Custom)                  (Custom)
                               │                        │                          │
                      GPS fields added           [beat_id]                [period_id]
                               │                 [partner_id]                      │
                               │                 [order_ids]             kpi.target.period
                               │                        │
                               │                  sale.order (extended)
                               │                  [visit_id] → visit.model
                               │                  [beat_id]  → beat.module
                               │
                         beat.switch.history
                         [employee_id]
                         [start_beat_id]
                         [switched_beat_id]
                               │
                         executive.beat.report
                         [employee_id]
                         [assigned_beat_id]
                         [current_beat_id]
                               │
                         executive.beat.report.switch
                         [from_beat_id]
                         [to_beat_id]

pjp.model
    │
    └──[pjp_item_ids]──► pjp.item
                            │
                       [assigned_beat_id] → beat.module
                       [employee_id]      → hr.employee

kpi.manager.target
    │
    └──[member_target_ids]──► kpi.target
                                  │
                            [actual_ids]──► kpi.actual
                            [item_ids]───► kpi.target.item
```

---

## 8. Step-by-Step Functional Workflows

### 8.1 Complete Daily Field Executive Cycle

This is the most important workflow — it describes everything a field executive does from morning to evening, and how each action flows through the system.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 DAILY FIELD EXECUTIVE WORKFLOW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 [Morning]
    │
    ▼
 STEP 1: START DAY
    │  User clicks "Start Day" in Today's Visit panel
    │
    │  OWL → calls hr.employee.create_attendance_checkin(
    │            employee_id, work_plan, travel_type, vehicle_used,
    │            location_data = {latitude, longitude, accuracy, ...}
    │         )
    │
    │  Backend:
    │    ├─ Check for existing open hr.attendance (same day) → return it
    │    ├─ Check for old open hr.attendance (previous day) → auto-close at 23:59
    │    ├─ Create new hr.attendance { check_in=NOW() }
    │    ├─ Reverse-geocode GPS coords via Nominatim
    │    └─ Store checkin_latitude, checkin_longitude, checkin_city, checkin_full_address
    │
    │  State: dayStarted=true, currentAttendanceId=<id>
    │
    ▼
 STEP 2: START BEAT
    │  User selects today's assigned beat and clicks "Start Beat"
    │
    │  OWL → loads beat.module records for today's date & employee
    │       → calls beat.module.action_start_beat()
    │
    │  Backend:
    │    └─ beat.status changes: pending/draft → in_progress
    │
    │  State: beatStarted=true, selectedBeat=<beat_record>
    │
    ▼
 STEP 3: START CUSTOMER VISIT  [repeated for each customer in beat.line_ids]
    │  User selects next customer in beat and clicks "Start Visit"
    │
    │  OWL → calls orm.create('visit.model', {
    │            employee_id, partner_id, beat_id, beat_line_id,
    │            actual_start_time=NOW(), status='in_progress',
    │            visit_for, today_work_plan, travel_type, vehicle_used
    │         })
    │
    │  Database:
    │    └─ New visit.model record created with auto-sequence name (VISIT/...)
    │
    │  State: activeVisit=<visit_record>
    │
    ▼
 STEP 4: PLACE ORDER (optional, within a visit)
    │  User taps "Quick Order" or creates a sale.order
    │
    │  OWL → calls orm.create('sale.order', {
    │            partner_id, visit_id=<active_visit_id>,
    │            order_line=[{product_id, product_uom_qty, price_unit}]
    │         })
    │       → calls sale.order.action_confirm() to confirm the order
    │
    │  Backend:
    │    ├─ sale.order.visit_id is set → linked to the current visit
    │    ├─ sale.order.beat_id  is computed from visit_id.beat_id (stored)
    │    └─ sale.order._trigger_kpi_recompute() → KPI actuals update immediately
    │
    ▼
 STEP 5: END CUSTOMER VISIT
    │  User captures a store photo and clicks "End Visit"
    │
    │  OWL → calls orm.write('visit.model', visit_id, {
    │            actual_end_time=NOW(),
    │            status='completed',
    │            store_image=<base64_image>,
    │            visit_comments='...',
    │            is_productive=True/False
    │         })
    │
    │  Backend constraints:
    │    ├─ _check_store_image_required: raises ValidationError if store_image is missing
    │    └─ write() → _trigger_kpi_recompute() → KPI actuals for employee updated
    │
    │  The system then advances to the next customer in beat_line_ids.
    │
    ▼
 STEP 6: (Optional) SWITCH BEAT
    │  If executive needs to change to a different beat mid-day:
    │  User selects a replacement beat and provides a reason
    │
    │  OWL → calls beat.module.action_swap_beat(new_beat_id, reason)
    │
    │  Backend:
    │    ├─ Original beat.status → 'swapped'
    │    ├─ New beat.status     → 'in_progress'
    │    └─ beat.switch.history record created with audit trail
    │
    ▼
 STEP 7: END BEAT
    │  User clicks "End Beat" after all customers in the beat are visited
    │  OWL → calls beat.module.action_complete_beat()
    │
    │  Backend:
    │    └─ beat.status: in_progress → completed
    │
    ▼
 STEP 8: END DAY  [Evening]
    │  User clicks "End Day"
    │
    │  OWL → calls hr.employee.create_attendance_checkout(
    │            employee_id, attendance_id,
    │            location_data={latitude, longitude, ...}
    │         )
    │
    │  Backend (via direct SQL to bypass Odoo overtime auto-compute issues):
    │    ├─ DELETE hr_attendance_overtime WHERE employee_id=X AND date=today
    │    ├─ UPDATE hr_attendance SET
    │    │       check_out=NOW(),
    │    │       worked_hours=(check_out - check_in).total_seconds()/3600,
    │    │       checkout_latitude=..., checkout_city=..., etc.
    │    └─ COMMIT
    │
    │  State: dayEnded=true
    │
 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 8.2 PJP (Permanent Journey Plan) Creation Workflow

```
STEP 1: Manager opens PJP tab in Employee Dashboard
         │
STEP 2: Beat Assignment via Drag-and-Drop Calendar
         │  Calendar shows all months with days as columns
         │  Manager drags a beat card onto a date cell
         │
         │  OWL → calls beat.module.copy_to_date(target_date)
         │  Backend → creates NEW beat record with same customers but new date
         │
STEP 3: Beat Rotation (optional bulk assignment)
         │  Manager enters rotation_frequency (e.g., 5 days)
         │  OWL → calls hr.employee.rotate_beats_in_month(month, year, frequency)
         │
         │  Backend algorithm:
         │    - Find all beats with assigned dates in the month
         │    - Walk every calendar day from today to end of month
         │    - day_in_cycle = day_count % rotation_frequency
         │    - if day_in_cycle < total_beats: assign beats[day_in_cycle] to that date
         │    - For repeat cycles (>0): CREATE new beat with '(Rotation N)' suffix
         │
STEP 4: Create PJP from Calendar
         │  Manager selects date range (start_date, end_date) — must be future
         │  OWL → calls hr.employee.create_pjp_from_calendar(start_date, end_date)
         │
         │  Backend:
         │    ├─ Validate start_date >= today
         │    ├─ Find all beats with beat_date in [start_date, end_date] for employee
         │    ├─ Create ONE pjp.model header record
         │    └─ Create one pjp.item per unique date with assigned_beat_id
         │
STEP 5: PJP Approval Workflow
         │
         │  draft → action_approve() → approved
         │          action_activate() → active
         │          action_complete() → completed
         │          action_cancel()   → cancelled
```

### 8.3 KPI Target Setting Workflow (Manager)

```
STEP 1: Create a Period (kpi.target.period)
         │  Settings > KPI > Periods > New
         │  Set period_type (monthly/quarterly/yearly) + date_from
         │  _onchange_auto_fill() auto-calculates name and date_to
         │
STEP 2a: Individual Target Mode
         │  KPI > Individual Targets > New
         │  Select employee, period
         │  Enter: target_orders, target_visits, target_new_dealers,
         │         target_payment_collected, target_complaints_solved
         │  action_confirm() → state = 'confirmed'
         │
STEP 2b: Team Target Mode (kpi.manager.target)
         │  KPI > Team Targets > New
         │  Select manager, period, assignment_mode
         │
         │  Mode 1 — 'distribute':
         │    Enter total team targets
         │    Add team members via action_add_member_target()
         │    Either: manually set each member's allocation
         │    Or: action_distribute_equally() → divides total by member count
         │
         │  Mode 2 — 'individual':
         │    Set separate targets per member directly
         │    is_fully_allocated always = True in this mode
         │
STEP 3: Actuals are auto-computed
         │  _compute_actuals() sources:
         │    visits → COUNT(visit.model WHERE status='completed' AND date in period)
         │    orders → COUNT(sale.order WHERE state in ['sale','done'] AND date in period)
         │    order_amount → SUM(sale.order.amount_total)
         │    new_dealers, payment_collected, complaints_solved → FROM kpi.actual (manual)
         │
STEP 4: Achievement percentages auto-calculated
         │  achievement_X = round(actual_X / target_X * 100, 2) if target_X else 0.0
         │  overall_achievement = average of all active KPI achievements
         │
STEP 5: OWL Dashboard provides inline editing
         │  Manager clicks a target cell in the dashboard table
         │  save_target_value(target_id, kpi_key, value) RPC call
         │  Returns updated actual + achievement immediately
```

### 8.4 Executive Beat Report Generation

```
STEP 1: Manager opens Executive Beat Reports
STEP 2: Opens the "Generate" wizard
STEP 3: Enters date_from, date_to (and optionally a specific executive)
         │
STEP 4: action_generate() iterates each day in the range:
         │  For each day:
         │    1. Search hr.attendance for check-ins on that day
         │    2. Deduplicate — keep only FIRST check-in per employee per day
         │    3. For each employee:
         │       a. Search beat.switch.history for switches that day
         │       b. Determine starting beat (first switch's start_beat_id,
         │          or beat assigned for the day)
         │       c. Determine current beat (last switched_beat_id, or starting beat)
         │       d. Build switch detail lines (sequence, from_beat, to_beat, reason, time)
         │       e. Create executive.beat.report record (or regenerate if exists)
         │
STEP 5: Returns to filtered list showing all generated report records
         │  Each record shows: Employee | Date | Check-In | Check-Out |
         │                     Assigned Beat | Last Beat | Switch Count
         │  Drill down to see full switch detail lines
```

---

## 9. Frontend Architecture (OWL Components)

All frontend components use Odoo's **OWL (Odoo Web Library)** reactive component system. They communicate with the backend exclusively through the `orm` service (RPC) and the Odoo action service.

### 9.1 Component Tree

```
EmployeeComponent  (employee_dashboard.EmployeeComponent)
│  Registered as client action: "employee_dashboard_component"
│  Manages: employee selector, active tab, user access level
│
├── InvoiceList      — lists vendor/customer invoices for selected employee
├── OrdersList       — lists sale orders with amounts
├── PJPList          — full PJP calendar + drag-and-drop beat planner
├── ExpenseList      — lists expense records
├── AttendanceList   — lists attendance records with location info
├── VisitList        — read-only historical visit list with filters
└── TodayVisit       — MAIN OPERATIONAL COMPONENT (full daily workflow)

KpiTargetDashboard  (kpi_target.KpiDashboard)
│  Registered as client action in kpi_target module
│  Manages: period selector, tab (individual/team), inline edit, summary stats
```

### 9.2 `TodayVisit` Component — Key State Machine

```javascript
// employee_dashboard/static/src/component/js/today_visit.js

this.state = useState({
    // Day lifecycle
    dayStarted: false,
    dayEnded: false,
    beatStarted: false,
    currentAttendanceId: null,

    // Beat data
    beats: [],                // today's beats for this employee
    allBeatsToday: [],        // all beats for swap modal
    selectedBeat: null,
    currentBeatLine: null,    // current customer being visited
    currentBeatLineIndex: 0,

    // Active visit
    activeVisit: null,

    // Modal visibility flags (8 modals)
    showStartDayModal: false,
    showStartBeatModal: false,
    showStartVisitModal: false,
    showEndVisitModal: false,
    showEndBeatModal: false,
    showEndDayModal: false,
    showSwitchBeatModal: false,
    showVisitCommentsModal: false,

    // Sales panels
    showSalesOrderListModal: false,
    showQuickOrder: false,
    salesOrderListData: [],
    allProducts: [],
    filteredProducts: [],
    productCategories: [],

    // KPI summary for the day
    kpiStats: {
        planned_visits: 0,
        completed_visits: 0,
        total_orders: 0,
        total_order_amount: 0,
    },

    // Processing / loading guards
    isProcessing: false,
    isCapturingLocation: false,
});
```

### 9.3 `PJPList` Component — Calendar State

```javascript
// employee_dashboard/static/src/component/js/pjp_list.js

this.state = useState({
    // Calendar navigation
    currentMonth: new Date().getMonth(),
    currentYear: new Date().getFullYear(),
    calendarDates: [],   // array of date objects for the rendered month grid
    beatsByDate: {},     // { 'YYYY-MM-DD': [beat1, beat2, ...] }

    // Drag-and-drop
    draggedBeat: null,

    // Beat creation / cloning
    cloneBeatForm: { show: false, selectedBeatId: null, newBeatName: "" },

    // Rotation
    rotationFrequency: 1,

    // PJP creation
    createPJPForm: { startDate: "", endDate: "" },
    showCreatePJPModal: false,

    // Customer selection for beats
    showCustomerSelection: false,
    selectedCustomers: [],
    allCustomers: [],
    filteredCustomers: [],
    searchByArea: "",
    searchByCity: "",
    searchByCategory: "",
});
```

### 9.4 `KpiTargetDashboard` Component

```javascript
// kpi_target/static/src/components/kpi_dashboard/kpi_dashboard.js

this.state = useState({
    rows: [],       // individual target rows from get_kpi_dashboard_data()
    teamRows: [],   // team target rows
    kpiTypes: [],   // [{key: 'orders', label: 'Orders'}, ...]
    periods: [],    // available periods for the selector

    selectedPeriodId: undefined,  // undefined = auto-select most recent
    loading: true,
    activeTab: "individual",

    // Inline edit
    editingCell: null,   // { rowId, kpiKey }
    editValue: "",

    // Summary strip
    summary: {
        totalIndividual: 0,
        avgAchievement: 0,
        achievedCount: 0,
        teamCount: 0,
    },
});
```

---

## 10. API & RPC Endpoints Reference

All backend methods called via Odoo ORM RPC (`this.orm.call(model, method, args)`):

### 10.1 `employee.dashboard` Model Methods

| Method | Arguments | Returns | Description |
|---|---|---|---|
| `get_user_access_info` | — | `{is_manager, employee_id, user_id}` | Determines dashboard access level |
| `get_accessible_employees` | — | `[{id, name, work_email, ...}]` | Returns employees visible to current user |
| `get_employee_order_stats` | `employee_id, today_start, today_end, period_from, period_to` | `{orders_today, orders_period, amount_today, amount_period}` | Order counts and amounts |

### 10.2 `hr.employee` Model Methods

| Method | Arguments | Returns | Description |
|---|---|---|---|
| `create_attendance_checkin` | `employee_id, work_plan, travel_type, vehicle_used, location_data` | `{success, attendance_id, check_in, message}` | GPS check-in |
| `create_attendance_checkout` | `employee_id, attendance_id, location_data` | `{success, attendance_id, check_out, worked_hours}` | GPS check-out |
| `get_today_attendance` | `employee_id` | `{success, attendance_id, check_in, check_out, is_checked_in}` | Today's attendance status |
| `rotate_beats_in_month` | `month, year, rotation_frequency` | `{success, message, beats_assigned, new_beats_created}` | Auto-rotate beats |
| `create_pjp_from_calendar` | `start_date, end_date` | `{success, pjp_id, pjp_items_count, message}` | Create PJP from calendar beats |

### 10.3 `beat.module` Model Methods

| Method | Arguments | Returns | Description |
|---|---|---|---|
| `action_start_beat` | — | `True / False` | Start the beat (pending → in_progress) |
| `action_complete_beat` | — | `True / False` | Complete the beat (in_progress → completed) |
| `action_swap_beat` | `new_beat_id, reason` | `{success, message, new_beat_id, ...}` | Swap to a different beat |
| `copy_to_date` | `target_date` | `{id, beat_number, name, customer_count}` | Drag-and-drop beat copy |

### 10.4 `beat.switch.history` Model Methods

| Method | Arguments | Returns | Description |
|---|---|---|---|
| `get_history_for_employee` | `employee_id, date` | `[{id, switch_time, start_beat_name, switched_beat_name, reason}]` | Beat switch audit trail |

### 10.5 `kpi.target` Model Methods

| Method | Arguments | Returns | Description |
|---|---|---|---|
| `get_kpi_dashboard_data` | `period_id` | `{rows, team_rows, kpi_types, periods}` | Full dashboard payload |
| `save_target_value` | `target_id, kpi_key, value` | `{success, actual, achievement, overall}` | Inline edit from OWL dashboard |

### 10.6 `hr.attendance` Model Methods

| Method | Arguments | Returns | Description |
|---|---|---|---|
| `reverse_geocode_location` | `latitude, longitude` | `{full_address, city, state, country}` | Coordinates to address |

### 10.7 HTTP Controller Routes

| Route | Method | Auth | Description |
|---|---|---|---|
| `/beatcalendar` | GET | user | Renders FullCalendar HTML page for a given employee_id |
| `/beatcalendar/events` | GET | (no CSRF) | Returns JSON array of beat events for FullCalendar |

---

## 11. KPI Computation Pipeline

This section explains precisely how a number flows from a real-world action into the KPI dashboard — including all triggers, dependencies, and data sources.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 KPI COMPUTATION PIPELINE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 Trigger Events:
   A) visit.model.write(status='completed')
   B) sale.order.write(state='sale') or write(state='done')
   C) sale.order.create() [if already in sale/done state]
   D) Direct call to kpi.target._compute_actuals()

        │
        ▼
 1. ACTUAL VISITS (auto-sourced)
        │
        │  self.env['visit.model'].sudo().search([
        │      ('employee_id', '=', employee.id),
        │      ('status', '=', 'completed'),
        │      ('actual_start_time', '>=', period.date_from + ' 00:00:00'),
        │      ('actual_start_time', '<=', period.date_to + ' 23:59:59'),
        │  ])
        │  sys_visits = len(completed_visits)
        │
        ▼
 2. ACTUAL ORDERS + ORDER AMOUNT (auto-sourced)
        │
        │  # Search by salesperson user OR by visit linkage (covers non-admin users)
        │  order_domain = [
        │      '|',
        │      ('user_id', '=', employee.user_id.id),
        │      ('visit_id.employee_id', '=', employee.id),
        │  ]
        │  sale_orders = self.env['sale.order'].sudo().search(
        │      order_domain + [
        │          ('date_order', '>=', date_from),
        │          ('date_order', '<=', date_to),
        │          ('state', 'in', ['sale', 'done']),
        │      ]
        │  )
        │  sys_orders = len(sale_orders)
        │  sys_order_amount = sum(sale_orders.mapped('amount_total'))
        │
        ▼
 3. MANUAL KPI ACTUALS (from kpi.actual records)
        │
        │  For each entry in record.actual_ids:
        │      manual[entry.kpi_type] += entry.value
        │
        │  Covers: new_dealers, payment_collected, complaints_solved
        │  Also available as override for orders and visits
        │
        ▼
 4. MERGE (take maximum of system vs manual)
        │
        │  record.actual_visits  = max(sys_visits,  manual['visits'])
        │  record.actual_orders  = max(sys_orders,  manual['orders'])
        │  record.actual_order_amount = sys_order_amount
        │  record.actual_new_dealers      = manual['new_dealers']
        │  record.actual_payment_collected = manual['payment_collected']
        │  record.actual_complaints_solved = manual['complaints_solved']
        │
        ▼
 5. ACHIEVEMENT % COMPUTATION
        │
        │  def pct(actual, target):
        │      return round(actual / target * 100, 2) if target else 0.0
        │
        │  record.achievement_orders    = pct(actual_orders,    target_orders)
        │  record.achievement_visits    = pct(actual_visits,    target_visits)
        │  record.achievement_new_dealers = pct(actual_new_dealers, target_new_dealers)
        │  ...
        │
        │  overall = average of all achievements where target > 0
        │
        ▼
 6. TEAM ROLLUP (kpi.manager.target)
        │
        │  team_actual_orders = sum(member.actual_orders for member in team)
        │  team_overall_achievement = average of team member achievements
        │
        ▼
 7. LIVE DATA IN DASHBOARD (extra safety layer)
        │
        │  In get_kpi_dashboard_data() and _get_live_actuals():
        │    → Re-queries visit.model and sale.order at request time
        │    → Takes max(live_value, stored_value) for visits and orders
        │    → Ensures dashboard never shows stale data even if triggers missed
        │
 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 11.1 Achievement Computation Formula

```python
# For each KPI type:
achievement_X = round(actual_X / target_X * 100, 2) if target_X > 0 else 0.0

# Overall achievement = average of all KPIs where a target was set:
achieved_list = [
    achievement_val
    for (target_val, achievement_val) in [
        (record.target_orders,            record.achievement_orders),
        (record.target_visits,            record.achievement_visits),
        (record.target_new_dealers,       record.achievement_new_dealers),
        (record.target_payment_collected, record.achievement_payment_collected),
        (record.target_complaints_solved, record.achievement_complaints_solved),
    ]
    if target_val > 0      # Only include KPIs that have a target set
]
overall_achievement = round(sum(achieved_list) / len(achieved_list), 2)
                      if achieved_list else 0.0
```

---

## 12. Security & Access Control

### 12.1 Security Groups

Defined in `employee_dashboard/security/security.xml`:

```xml
<!-- Group: Employee Dashboard > User -->
<!-- Inherits: base.group_user (Internal User) -->
<!-- Capability: Can view ONLY their own dashboard data -->
<record id="group_employee_dashboard_user" model="res.groups">
    <field name="name">User</field>
    <field name="category_id" ref="module_category_employee_dashboard"/>
    <field name="implied_ids" eval="[(4, ref('base.group_user'))]"/>
</record>

<!-- Group: Employee Dashboard > Manager -->
<!-- Inherits: group_employee_dashboard_user -->
<!-- Capability: Can view ALL employees dashboard data -->
<record id="group_employee_dashboard_manager" model="res.groups">
    <field name="name">Manager</field>
    <field name="category_id" ref="module_category_employee_dashboard"/>
    <field name="implied_ids" eval="[(4, ref('group_employee_dashboard_user'))]"/>
</record>
```

### 12.2 Data Isolation Logic

```python
# employee_dashboard/models/hr_employee.py

@api.model
def get_accessible_employees(self):
    """
    Non-managers can ONLY see themselves.
    Managers can see all employees.
    """
    is_manager = user.has_group('employee_dashboard.group_employee_dashboard_manager')

    if not is_manager:
        employee = self.env['hr.employee'].search([('user_id', '=', user.id)], limit=1)
        domain = [('id', '=', employee.id)] if employee else [('id', '=', False)]
    else:
        domain = []   # no restriction for managers

    return self.env['hr.employee'].search_read(domain, ['name', 'work_email', ...])
```

### 12.3 Record Access Controls

Each module ships an `ir.model.access.csv` file granting CRUD rights:

| Model | Group | Create | Read | Write | Delete |
|---|---|---|---|---|---|
| `beat.module` | Employee Dashboard User | Yes | Yes | Yes | Yes |
| `beat.line` | Employee Dashboard User | Yes | Yes | Yes | Yes |
| `beat.switch.history` | Employee Dashboard User | Yes | Yes | No | No |
| `visit.model` | Employee Dashboard User | Yes | Yes | Yes | No |
| `kpi.target` | Employee Dashboard User | Yes | Yes | Yes | Yes |
| `kpi.manager.target` | Employee Dashboard Manager | Yes | Yes | Yes | Yes |

### 12.4 `sudo()` Usage

Many backend methods use `.sudo()` to ensure managers can access data across all company employees without individual record rules blocking cross-employee queries:

```python
# Examples from the codebase:
HrAttendance = self.env['hr.attendance'].sudo()
completed_visits = self.env['visit.model'].sudo().search([...])
sale_orders = self.env['sale.order'].sudo().search([...])
kpi_targets = self.env['kpi.target'].sudo().search([...])
```

---

## 13. Third-Party Libraries & Dependencies

### 13.1 Python Dependencies

| Library | Purpose |
|---|---|
| `geopy` | Reverse geocoding via Nominatim (OpenStreetMap) |
| `python-dateutil` | `relativedelta` for period date calculations |
| `pytz` | Timezone conversion for attendance check-in/check-out |

### 13.2 JavaScript / Frontend Libraries

| Library | File Location | Purpose |
|---|---|---|
| Chart.js | `employee_dashboard/static/lib/chart.min.js` | Dashboard charting |
| FullCalendar v5 | `employee_dashboard/static/lib/fullcalendar/` | Beat calendar view (`/beatcalendar`) |
| Leaflet.js | `employee_dashboard/static/lib/leaflet/` | Map rendering for GPS location display |
| DataTables.js | `employee_dashboard/static/lib/datatables/` | Sortable/filterable data tables |
| FullCalendar (calendar) | `employee_dashboard/static/lib/calendar/` | OWL PJP calendar variant |

---

## 14. Git History & Change Summary

The repository has **95 commits** across **47 merged pull requests**. Below is a summary of major feature areas developed:

| PR Range | Feature Category | Key Changes |
|---|---|---|
| #1–#6 | Beat Swap & PJP Foundation | Beat swap display, rotation beat numbers, beat filter by visit completion |
| #7–#10 | PJP Beat Assignment | Fix PJP creation to reference existing beats, enforce future dates |
| #11–#12 | KPI Target System | Full 16-requirement KPI system, link actuals to visit data, dealer metrics |
| #14–#16 | Visit Improvements | Visit attachment validation, store image required on start, simplify end modal |
| #18 | Drag-and-Drop Copy | Copy customers to new beat on drag-and-drop instead of moving |
| #30 | Executive Beat Report | Management report for daily beat assignments and switch history |
| #31–#39 | Sale Order KPI Fix | Series of fixes to ensure sale order actual values propagate to KPI for all users including non-admin; `compute_sudo=True` on stored fields |
| #40–#43 | Custom Enquiry / Odoo Integration | Website contact form enquiry interception, Odoo 18 compatibility |
| #44 | Dashboard Analytics Reports | Comprehensive dashboard analytics XML views for all modules |
| #45 | ERP Menu | Add ERP menu to custom_enquiry for external demo navigation |
| #46 | Cohort View Fix | Fix invalid cohort view type incompatible with Odoo 18 Community |
| #47 | Master Document | Initial project documentation |

### 14.1 Notable Technical Decisions & Fixes

**1. Non-Admin Employee KPI Bug (PR #31–#39)**

The most complex bug series in the project: sale order actual values showed `0` for non-admin employees. Root cause: Odoo's record rules for `sale.order` blocked non-sudo access. Fix applied across multiple PRs:

```python
# Final fix: use sudo() for all KPI actuals queries
sale_orders = self.env['sale.order'].sudo().search(order_domain + [...])

# Also: compute_sudo=True on all KPI stored computed fields
actual_orders = fields.Float(compute='_compute_actuals', store=True, compute_sudo=True)
```

**2. Attendance Auto-Checkout Prevention**

Odoo 18 has an overtime module that automatically inserts `check_out` values. The system overrides this to prevent the field executive's checkout from being auto-populated:

```python
class HrAttendance(models.Model):
    def write(self, vals):
        # Block automatic checkout unless context flag is set
        if 'check_out' in vals:
            if not (self.env.context.get('manual_checkout') or
                    self.env.context.get('force_write') or
                    self.env.context.get('tracking_disable')):
                vals = {k: v for k, v in vals.items() if k != 'check_out'}
        return super().write(vals)
```

**3. Checkout via Direct SQL**

The checkout also deletes overtime records and uses raw SQL to ensure the write is not blocked by any ORM override:

```python
# Delete today's overtime to prevent duplicate key errors
self.env.cr.execute("""
    DELETE FROM hr_attendance_overtime
    WHERE employee_id = %s AND date = %s
""", (employee_id, today_date))

# Direct SQL update for reliable checkout
self.env.cr.execute(f"""
    UPDATE hr_attendance SET {', '.join(set_parts)}
    WHERE id = %s
""", values)
self.env.cr.commit()
```

---

## 15. Deployment Checklist

### 15.1 Installation Order

```
1. Install beat_module first        (no inter-module dependencies)
2. Install kpi_target second        (no inter-module dependencies)
3. Install employee_dashboard last  (uses beat.module models at runtime)
```

### 15.2 Python Package Requirements

```bash
pip install geopy
pip install python-dateutil
pip install pytz
```

### 15.3 Post-Installation Configuration Steps

1. **IR Sequences are auto-created** — `beat_module/data/sequence_data.xml` creates `beat.module.sequence`; `employee_dashboard/data/visit_sequence.xml` creates the `visit.model` sequence on install.

2. **Assign Security Groups** — Navigate to Settings > Users, assign each field executive to `Employee Dashboard > User` group. Assign managers to `Employee Dashboard > Manager` group.

3. **Create KPI Periods** — KPI > Periods > New. Set type (monthly/quarterly/yearly) and start date. The system auto-fills end date and name.

4. **Create Beats** — Beat Module > Beats > New. Assign employee, add customer lines.

5. **Configure Employee User Links** — Each `hr.employee` must have a linked `res.users` record so that `sale.order` attribution works correctly via `employee.user_id`.

6. **Verify geopy Connectivity** — The Nominatim geocoder requires internet access to `nominatim.openstreetmap.org`. Verify firewall rules allow outbound HTTPS on port 443.

### 15.4 Module Dependencies Summary

```python
# beat_module/__manifest__.py
'depends': ['base', 'contacts', 'hr']

# employee_dashboard/__manifest__.py
'depends': ['hr', 'hr_timesheet']
# Runtime uses: 'beat.module', 'hr.attendance', 'sale.order'

# kpi_target/__manifest__.py
'depends': ['base', 'hr', 'web']
# Runtime uses: 'visit.model', 'sale.order'
```

---

*End of Employee 360 Project Document*
*Document  — Generated March 2026*
*For questions or updates, contact the development team.*
