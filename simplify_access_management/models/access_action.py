from odoo import fields, models, api, _


class AccessAction(models.Model):
    _name = 'access.action'
    _description = "Access Action"

    access_management_id = fields.Many2one(comodel_name='access.management', string='Access Management')
    model_id = fields.Many2one(comodel_name='ir.model', string='Model', ondelete='cascade')
    ir_ui_view_type_ids = fields.Many2many(
        comodel_name='ir.ui.view.type', relation='access_action_view_type_rel',
        column1='access_action_id', column2='ir_view_type_id', string='Hide Views',
        help="The views are added on list will be hidden in selected model from the defined users.")
    server_action_ids = fields.Many2many(
        comodel_name='ir.access.actions', relation='access_action_server_action_rel',
        column1='access_action_id', column2='server_ir_action_id', string='Hide Actions',
        domain="[('action_id.binding_model_id', '=', model_id), ('action_id.type', '!=', 'ir.actions.report')]",
        help="The actions are added on list will be hidden in selected model from the defined users.")
    report_action_ids = fields.Many2many(
        comodel_name='ir.access.actions', relation='access_action_report_action_rel',
        column1='access_action_id', column2='report_ir_action_id', string='Hide Reports',
        domain="[('action_id.binding_model_id', '=', model_id), ('action_id.type', '=', 'ir.actions.report')]",
        help="The Reports are added on list will be hidden in selected model from the defined users.")
    readonly = fields.Boolean(string='Read-Only')
    hide_create = fields.Boolean(
        string='Hide Create', help="Create Button will be hidden in selected model from the defined users.")
    hide_edit = fields.Boolean(
        string='Hide Edit', help="Edit Button will be hidden in selected model from the defined users.")
    hide_delete = fields.Boolean(
        string='Hide Delete', help="Delete Button will be hidden in selected model from the defined users.")
    hide_archive_unarchive = fields.Boolean(
        string='Hide Archive/Unarchive',
        help="Archive and Unarchive action will be hidden in selected model from the defined users.")
    hide_duplicate = fields.Boolean(
        string='Hide Duplicate', help="Duplicate action will be hidden in selected model from the defined users.")
    hide_export = fields.Boolean(
        string='Hide Export', help="Export Button will be hidden in selected model from the defined users.")
    hide_import = fields.Boolean(
        string='Hide Import', help="Import Button will be hidden in selected model from the defined users.")
    hide_add_properties = fields.Boolean(
        string='Hide Add Properties', default=True,
        help="Add Properties Button will be hidden in selected model from the defined users.")
    hide_external_link = fields.Boolean(
        string='Remove External Link',
        help="External Link will be hidden for relational fields in selected model from the defined users.")
    hide_link_create = fields.Boolean(
        string='Hide Create link',
        help="Create Link will be hidden for relational fields in selected model from the defined users.")
    hide_link_edit = fields.Boolean(
        string='Hide Edit link',
        help="Edit Link will be hidden for relational fields in selected model from the defined users.")
