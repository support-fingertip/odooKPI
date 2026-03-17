# -*- coding: utf-8 -*-
"""
emp360_mobile — Asset Cache Clear Controller

Visiting /emp360/clear-assets while logged in as an admin/manager
deletes ALL compiled asset bundles from ir.attachment, forcing Odoo
to recompile web.assets_backend on the next page load.

This is needed when JS/XML source files change but the server hasn't
been restarted or the module hasn't been upgraded (-u emp360_mobile).

Usage:
  1. Open browser, go to:  http://localhost:8070/emp360/clear-assets
  2. Wait for redirect to home
  3. Hard-refresh the app page: Ctrl+Shift+R (Windows/Linux) or Cmd+Shift+R (Mac)
"""
import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class EmpMobileClearAssets(http.Controller):

    @http.route('/emp360/clear-assets', auth='user', type='http', methods=['GET'])
    def clear_assets_cache(self, **kwargs):
        """Delete compiled asset bundles so Odoo recompiles on next request."""

        # Only allow users with system config rights (managers/admins)
        env = request.env
        is_allowed = env.user.has_group('base.group_system') or \
                     env.user.has_group('base.group_erp_manager')

        if not is_allowed:
            return request.make_response(
                '<h3>Not authorized. Only managers/admins can clear asset cache.</h3>',
                headers=[('Content-Type', 'text/html')]
            )

        # Find and delete all compiled asset bundles
        attachments = env['ir.attachment'].sudo().search([
            '|',
            ('url', 'like', '/web/content/'),
            ('name', 'like', 'web.assets'),
        ])
        count = len(attachments)
        attachments.unlink()

        _logger.info("emp360_mobile: cleared %d compiled asset attachments", count)

        # Return auto-redirect page
        html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>Assets Cleared</title>
  <style>
    body {{font-family:system-ui,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;background:#f0f4ff;}}
    .card {{background:#fff;border-radius:20px;padding:40px;text-align:center;box-shadow:0 8px 32px rgba(67,97,238,0.15);max-width:440px;}}
    .icon {{font-size:48px;margin-bottom:16px;}}
    h2 {{color:#0f172a;margin:0 0 8px;}}
    p  {{color:#64748b;margin:0 0 24px;}}
    .badge {{background:#dcfce7;color:#166534;border-radius:100px;padding:6px 16px;font-weight:700;font-size:14px;}}
    .btn {{display:inline-block;margin-top:24px;padding:12px 28px;background:linear-gradient(135deg,#4361ee,#3a0ca3);color:#fff;border-radius:12px;text-decoration:none;font-weight:700;}}
    .counter {{font-size:13px;color:#94a3b8;margin-top:12px;}}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">✅</div>
    <h2>Asset Cache Cleared</h2>
    <p>Deleted <strong>{count}</strong> compiled bundle(s) from database.<br/>
       Odoo will recompile fresh assets on the next page load.</p>
    <span class="badge">emp360_mobile v18.0.1.0.2 will now load</span>
    <br/>
    <a class="btn" href="/web">→ Go to App</a>
    <div class="counter" id="ct">Redirecting in 4s…</div>
  </div>
  <script>
    let n = 4;
    const ct = document.getElementById('ct');
    const t = setInterval(() => {{
      n--;
      ct.textContent = n > 0 ? 'Redirecting in ' + n + 's…' : 'Redirecting…';
      if (n <= 0) {{ clearInterval(t); window.location.href = '/web'; }}
    }}, 1000);
  </script>
</body>
</html>"""
        return request.make_response(html, headers=[('Content-Type', 'text/html; charset=utf-8')])
