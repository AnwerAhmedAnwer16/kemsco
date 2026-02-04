from odoo import fields, models, api, _


class AccessField(models.Model):
    _name = 'access.field'
    _description = "Access Field"

    access_management_id = fields.Many2one(comodel_name='access.management', string='Access Management')
    model_id = fields.Many2one(comodel_name='ir.model', string='Model', ondelete='cascade')
    field_ids = fields.Many2many(
        comodel_name='ir.model.fields', relation='access_field_field_rel',
        column1='access_field_id', column2='field_id', string='Fields')
    invisible = fields.Boolean(
        string='Invisible',
        help="Selected Field will be hidden in selected model from the defined users.")
    readonly = fields.Boolean(
        string='Read-Only',
        help="Selected Field will be Read only in selected model from the defined users.")
    required = fields.Boolean(
        string='Required',
        help="Selected Field will be set as required for selected model from the defined users.")
    external_link = fields.Boolean(
        string='Remove External Link',
        help="External Link will be hidden for relational fields in selected model from the defined users.")
    hide_create = fields.Boolean(
        string='Hide Create link',
        help="Create Link will be hidden for relational fields in selected model from the defined users.")
    hide_edit = fields.Boolean(
        string='Hide Edit link',
        help="Edit Link will be hidden for relational fields in selected model from the defined users.")
