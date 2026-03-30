# -*- coding: utf-8 -*-
from odoo import models, fields, api


class BoqCategory(models.Model):
    """
    BOQ Work Category — maps to a notebook tab in the BOQ form.
    Examples: Electrical, Civil, Lighting, Plumbing, HVAC, Finishing.
    """
    _name = 'boq.category'
    _description = 'BOQ Work Category'
    _order = 'sequence asc, name asc'
    _rec_name = 'name'

    # ── Identity ─────────────────────────────────────────────────────────
    name = fields.Char(
        string='Category Name',
        required=True,
        translate=True,
        index=True,
    )
    code = fields.Char(
        string='Technical Code',
        required=True,
        help='Short lowercase code with no spaces. Used internally to link tab fields.',
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )
    description = fields.Text(
        string='Description',
        translate=True,
    )

    # ── Visual ───────────────────────────────────────────────────────────
    color = fields.Integer(string='Color', default=0)
    icon = fields.Char(
        string='Icon Class',
        default='fa-tools',
        help='FontAwesome class, e.g. fa-bolt, fa-building, fa-tint',
    )
    tag_color_class = fields.Char(
        string='Tag CSS Class',
        compute='_compute_tag_color_class',
        store=True,
    )

    # ── Dynamic Category Flag ─────────────────────────────────────────────
    # Non-stored: persisted via a '[dynamic]' prefix in the description field
    # so no new DB column is required on boq_category.
    is_dynamic = fields.Boolean(
        string='Dynamic Category',
        compute='_compute_is_dynamic',
        inverse='_inverse_is_dynamic',
        store=False,
        help='Enable to allow creating sub-categories under this category. '
             'When disabled, the "Add new category" option is hidden.',
    )

    # ── Hierarchy (optional parent / children) ────────────────────────────
    # parent_id: non-stored computed — looks up by parent name stored in
    # description prefix "[parent:CODE]" to avoid any new DB column.
    parent_id = fields.Many2one(
        comodel_name='boq.category',
        string='Parent Category',
        compute='_compute_parent_id',
        inverse='_inverse_parent_id',
        store=False,
    )
    child_ids = fields.One2many(
        comodel_name='boq.category',
        inverse_name='parent_id',
        string='Sub-categories',
    )

    # ── Status ───────────────────────────────────────────────────────────
    active = fields.Boolean(default=True)

    # ── Statistics ───────────────────────────────────────────────────────
    boq_count = fields.Integer(
        string='BOQs',
        compute='_compute_boq_count',
    )
    line_count = fields.Integer(
        string='Total Lines',
        compute='_compute_boq_count',
    )

    # ── Constraints ──────────────────────────────────────────────────────
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Category name must be unique.'),
        ('code_uniq', 'unique(code)', 'Category code must be unique.'),
    ]

    # ── Helpers for description-backed virtual fields ─────────────────────
    # Format: first line of description may contain flag tokens like
    # "[dynamic]" or "[parent:CODE]". These tokens are stripped when
    # the user reads the visible description.

    def _desc_flags(self):
        """Return (flags_dict, clean_description) parsed from self.description."""
        raw = self.description or ''
        flags = {'dynamic': False, 'parent_code': None}
        lines = raw.split('\n')
        clean_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped == '[dynamic]':
                flags['dynamic'] = True
            elif stripped.startswith('[parent:') and stripped.endswith(']'):
                flags['parent_code'] = stripped[8:-1]
            else:
                clean_lines.append(line)
        return flags, '\n'.join(clean_lines).strip()

    def _set_desc_flags(self, dynamic=None, parent_code=None):
        """Write flag tokens back into the description field."""
        for rec in self:
            flags, clean = rec._desc_flags()
            if dynamic is not None:
                flags['dynamic'] = dynamic
            if parent_code is not None:
                flags['parent_code'] = parent_code or None
            tokens = []
            if flags['dynamic']:
                tokens.append('[dynamic]')
            if flags['parent_code']:
                tokens.append('[parent:%s]' % flags['parent_code'])
            rec.description = ('\n'.join(tokens) + '\n' + clean).strip() or False

    # ── is_dynamic compute / inverse ──────────────────────────────────────
    @api.depends('description')
    def _compute_is_dynamic(self):
        for rec in self:
            flags, _ = rec._desc_flags()
            rec.is_dynamic = flags['dynamic']

    def _inverse_is_dynamic(self):
        for rec in self:
            rec._set_desc_flags(dynamic=rec.is_dynamic)

    # ── parent_id compute / inverse ───────────────────────────────────────
    @api.depends('description')
    def _compute_parent_id(self):
        all_cats = {c.code: c for c in self.env['boq.category'].search([])}
        for rec in self:
            flags, _ = rec._desc_flags()
            rec.parent_id = all_cats.get(flags['parent_code'], False)

    def _inverse_parent_id(self):
        for rec in self:
            code = rec.parent_id.code if rec.parent_id else None
            rec._set_desc_flags(parent_code=code)

    # ── Computes ─────────────────────────────────────────────────────────
    @api.depends('color')
    def _compute_tag_color_class(self):
        color_map = {
            0: 'boq_tag_grey',   1: 'boq_tag_red',
            2: 'boq_tag_orange', 3: 'boq_tag_yellow',
            4: 'boq_tag_teal',   5: 'boq_tag_purple',
            6: 'boq_tag_slate',  7: 'boq_tag_cyan',
            8: 'boq_tag_green',  9: 'boq_tag_pink',
            10: 'boq_tag_blue',  11: 'boq_tag_indigo',
        }
        for rec in self:
            rec.tag_color_class = color_map.get(rec.color, 'boq_tag_grey')

    def _compute_boq_count(self):
        Line = self.env['boq.order.line']
        for rec in self:
            boqs = self.env['boq.boq'].search_count(
                [('category_ids', 'in', rec.id)]
            )
            lines = Line.search_count([('category_id', '=', rec.id)])
            rec.boq_count = boqs
            rec.line_count = lines
