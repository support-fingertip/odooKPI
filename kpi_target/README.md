# KPI Target & Actual Tracker

A comprehensive Odoo 18 module for tracking employee KPI targets and actuals with an interactive OWL dashboard.

## Features

### Models

1. **KPI Target Period** (`kpi.target.period`)
   - Manage time periods (monthly/quarterly/yearly)
   - Track multiple targets per period
   - Quick access to related targets

2. **KPI Target** (`kpi.target`)
   - Link employees to periods
   - Track 5 KPI types: Sales, Visits, New Dealers, Payment Collected, Complaints Solved
   - Denormalized target fields for fast access
   - Auto-computed actual values from entries
   - Auto-computed achievement percentages
   - State management: Draft → Confirmed → Done

3. **KPI Target Item** (`kpi.target.item`)
   - Normalized storage of target values by KPI type
   - Auto-synced with denormalized fields

4. **KPI Actual** (`kpi.actual`)
   - Record actual achievements with date
   - Support for notes/comments
   - Aggregated to compute total actuals

### Interactive Dashboard

The OWL-based dashboard provides:
- **Period filtering** - Select which period to view
- **Inline editing** - Click any target cell to edit values
- **Real-time calculations** - Achievements update immediately
- **Visual indicators** - Color-coded cells and progress bars
- **Quick navigation** - Open full target form with one click

### Views & Menus

- **Dashboard** - Interactive OWL component for data entry and monitoring
- **Targets** - Full CRUD with list, form, and search views
- **Actuals** - Editable list view for manual entry
- **Configuration** - Manage target periods

## Installation

1. Copy the `kpi_target` directory to your Odoo addons path
2. Update the addons list: `odoo-bin -u all -d your_database`
3. Install the module from Apps menu

## Usage

### Setting Up Periods

1. Navigate to: **KPI Tracker → Configuration → Target Periods**
2. Create a new period with:
   - Name (e.g., "January 2026")
   - Period type (Monthly/Quarterly/Yearly)
   - Start and end dates
   - Active status

### Setting Targets

**Method 1: Using the Dashboard**
1. Navigate to: **KPI Tracker → Dashboard**
2. Select a period from the dropdown
3. Click any target cell to edit
4. Press Enter to save or Escape to cancel

**Method 2: Using Forms**
1. Navigate to: **KPI Tracker → Targets**
2. Create a new target
3. Select employee and period
4. Enter target values in the "Targets & Actuals" tab
5. Click "Confirm" when ready

### Recording Actuals

1. Navigate to: **KPI Tracker → Targets**
2. Open a target record
3. Go to "Actual Entries" tab
4. Add entries with:
   - Date
   - KPI Type
   - Value
   - Optional notes

Actuals are automatically summed and achievement percentages calculated.

### Understanding Achievement Colors

- **Green (≥100%)** - Target exceeded
- **Yellow (≥75%)** - On track
- **Red (<75%)** - Below target

## Technical Details

### RPC Methods

- `get_kpi_dashboard_data(period_id)` - Fetch dashboard data for a period
- `save_target_value(target_id, kpi_key, value)` - Update a single target value

### SQL Constraints

- Unique employee per period
- Unique KPI type per target item

### Dependencies

- `base` - Core Odoo framework
- `hr` - Human Resources module
- `web` - Web interface and OWL framework

## Module Structure

```
kpi_target/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── kpi_target_period.py
│   ├── kpi_target.py
│   ├── kpi_target_item.py
│   └── kpi_actual.py
├── security/
│   └── ir.model.access.csv
├── views/
│   ├── kpi_target_views.xml
│   └── kpi_target_menus.xml
└── static/
    └── src/
        └── components/
            └── kpi_dashboard/
                ├── kpi_dashboard.js
                ├── kpi_dashboard.xml
                └── kpi_dashboard.scss
```

## License

LGPL-3

## Version

18.0.1.0.0
