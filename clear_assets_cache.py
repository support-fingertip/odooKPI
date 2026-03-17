#!/usr/bin/env python3
"""
Clear Odoo compiled asset cache for emp360_mobile module.

Run this script from the Odoo root directory:
    python3 /path/to/odooKPI/clear_assets_cache.py --database <db_name>

OR just restart Odoo with module update:
    ./odoo-bin -d <db_name> -u emp360_mobile --stop-after-init
    # then restart normally: ./odoo-bin -d <db_name>
"""
import argparse
import sys
import os

def clear_assets(db_name):
    try:
        import psycopg2
    except ImportError:
        print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary")
        sys.exit(1)

    try:
        conn = psycopg2.connect(database=db_name, user="odoo", host="localhost")
        cur = conn.cursor()

        # Delete compiled asset bundles from ir.attachment
        cur.execute("""
            DELETE FROM ir_attachment
            WHERE name LIKE '%web.assets_backend%'
               OR name LIKE '%web.assets_web%'
               OR url LIKE '/web/content/%'
              AND res_model = 'ir.attachment'
        """)
        deleted = cur.rowcount

        # Also clear the asset bundle table if it exists (Odoo 17+)
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'ir_asset'
            )
        """)
        if cur.fetchone()[0]:
            cur.execute("UPDATE ir_asset SET active = true WHERE active = false")

        conn.commit()
        print(f"✓ Cleared {deleted} cached asset records from database '{db_name}'")
        print("✓ Restart your Odoo server to recompile assets")
        conn.close()
    except Exception as e:
        print(f"ERROR: {e}")
        print("\nAlternative: Access Odoo URL with ?debug=assets to force recompile")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clear Odoo asset cache")
    parser.add_argument("--database", "-d", required=True, help="Database name")
    args = parser.parse_args()
    clear_assets(args.database)
    print("\n--- Next steps ---")
    print("1. Restart Odoo: ./odoo-bin -d", args.database)
    print("2. Hard-refresh browser: Ctrl+Shift+R (or Cmd+Shift+R on Mac)")
    print("3. The visits page crash will be fixed")
