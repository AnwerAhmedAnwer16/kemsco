from odoo import models, fields, api


class AccessDomain(models.Model):
    _name = 'access.domain'
    _description = 'Access Domain'

    access_management_id = fields.Many2one(comodel_name='access.management', string='Access Management')
    model_id = fields.Many2one(comodel_name='ir.model', string='Model', index=True, required=True, ondelete='cascade')
    model_name = fields.Char(string="Model Name", related="model_id.model")
    domain = fields.Char(
        string='Domain', default='[]',
        help="The create customised domain rule where we can customise rule by selecting specific fields and records")
    restrict_create = fields.Boolean(
        string='Restrict Create', help="The set 'Create' access of the selected model for the specified users")
    restrict_edit = fields.Boolean(
        string='Restrict Edit', help="The set 'Write' access of the selected model for the specified users")
    restrict_delete = fields.Boolean(
        string='Restrict Delete', help="The set 'Delete' access of the selected model for the specified users")
