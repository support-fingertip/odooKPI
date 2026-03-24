# -*- coding: utf-8 -*-
from odoo import models, fields


class BoqCategory(models.Model):
    """
    Work category for BOQ (e.g. Electrical, Civil, Lighting, Plumbing).
    Each category maps to one notebook tab in the BOQ form.
    """
    _name = 'boq.category'
    _description = 'BOQ Work Category'
    _order = 'sequence, name'

    name = fields.Char(
        string='Category Name',
        required=True,
        translate=True,
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Order in which the tab appears on the BOQ form.',
    )
    code = fields.Char(
        string='Code',
        help='Short technical code used for field identification (no spaces).',
    )
    color = fields.Integer(
        string='Color Index',
        default=0,
    )
    icon = fields.Char(
        string='Icon',
        default='fa-tools',
        help='FontAwesome icon class, e.g. fa-bolt',
    )
    description = fields.Text(string='Description')
    active = fields.Boolean(default=True)

    # Computed count for kanban / list view
    boq_count = fields.Integer(
        string='BOQ Count',
        compute='_compute_boq_count',
    )

    def _compute_boq_count(self):
        for rec in self:
            rec.boq_count = self.env['boq.boq'].search_count(
                [('category_ids', 'in', rec.id)]
            )

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Category name must be unique.'),
    ]
