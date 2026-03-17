# -*- coding: utf-8 -*-
"""
emp360_mobile — Install / Upgrade Hooks

post_init_hook: automatically clears compiled asset bundles from ir.attachment
so the new JS/XML takes effect immediately after:
    ./odoo-bin -d <db> -u emp360_mobile
without needing a manual cache-clear step.
"""
import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Clear Odoo asset bundle cache so recompile happens on next page load."""
    try:
        attachments = env['ir.attachment'].sudo().search([
            '|',
            ('url', 'like', '/web/content/'),
            ('name', 'like', 'web.assets'),
        ])
        count = len(attachments)
        if count:
            attachments.unlink()
            _logger.info(
                "emp360_mobile post_init_hook: cleared %d compiled asset bundle(s). "
                "Fresh assets will compile on next page load.", count
            )
        else:
            _logger.info("emp360_mobile post_init_hook: no cached asset bundles found.")
    except Exception as exc:
        _logger.warning("emp360_mobile post_init_hook: could not clear assets: %s", exc)
