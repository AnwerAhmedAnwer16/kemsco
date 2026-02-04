from odoo.exceptions import UserError
from odoo import fields, models, api, _


class AccessManagement(models.Model):
    _name = 'access.management'
    _description = "Access Management"

    name = fields.Char(string='Name')
    company_ids = fields.Many2many('res.company', 'access_management_company_rel', 'access_management_id',
                                   'company_id', 'Companies', required=True, default=lambda self: self.env.company)

    user_ids = fields.Many2many(
        comodel_name='res.users', relation='access_management_users_rel',
        column1='access_management_id', column2='user_id', string='Users')
    disabled_model_ids = fields.Many2many(
        comodel_name='ir.model', relation='access_management_disabled_model_rel',
        column1='access_management_id', column2='model_id',
        string='Disabled Models', compute="_compute_disabled_model_ids")
    # General
    readonly = fields.Boolean(string='Read-Only')
    is_active = fields.Boolean(string='Is Active', default=True)
    hide_chatter = fields.Boolean(
        string='Hide Chatter', help="The Chatter will be hidden in all model from the specified users.")
    hide_send_mail = fields.Boolean(
        string='Hide Send Message',
        help="The Send Message button will be hidden in chatter of all model from the specified users.")
    hide_log_notes = fields.Boolean(
        string='Hide Log Notes',
        help="The Log Notes button will be hidden in chatter of all model from the specified users.")
    hide_schedule_activity = fields.Boolean(
        string='Hide Schedule Activity',
        help="The Schedule Activity button will be hidden in chatter of all model from the specified users.")
    hide_export = fields.Boolean(
        string='Hide Export', help="The Export button will be hidden in all model from the specified users.")
    hide_import = fields.Boolean(
        string='Hide Import', help="The Import button will be hidden in all model from the specified users.")
    hide_add_properties = fields.Boolean(
        string='Hide Add Properties', default=True,
        help="The Add Properties button will be hidden in all model from the specified users.")
    disable_login = fields.Boolean(string='Disable Login', help="The Users can not login if this button is check.")
    disable_debug_mode = fields.Boolean(
        string='Disable Developer Mode', help="Developer mode will be hidden from the defined users.")
    hide_menu_ids = fields.Many2many(
        comodel_name='ir.ui.menu', relation='access_management_menu_rel',
        column1='access_management_id', column2='menu_id', string='Hide Menu',
        help="The menu or submenu added on above list will be hidden from the defined users.")

    hide_db_name = fields.Boolean(string="Hide Database Name")
    # Access Field
    access_field_ids = fields.One2many(
        comodel_name='access.field', inverse_name='access_management_id', string='Hide Field', copy=True)
    # Access Action
    access_action_ids = fields.One2many(
        comodel_name='access.action', inverse_name='access_management_id', string='Hide Action', copy=True)
    # Access Domain
    access_domain_ids = fields.One2many(
        comodel_name='access.domain', inverse_name='access_management_id', string='Access Domain', copy=True)
    # View Node access
    access_view_node_ids = fields.One2many(
        comodel_name='access.view.node', inverse_name='access_management_id', string='Hide View Node', copy=True)
    # Chatter access
    access_chatter_ids = fields.One2many(
        comodel_name='access.chatter', inverse_name='access_management_id', string='Hide Chatter', copy=True)

    # =========================== Compute functions =========================== #
    def _compute_disabled_model_ids(self):
        for rec in self:
            access_model_list = [
                'access.management', 'access.domain', 'access.field',
                'access.view.node', 'access.action', 'ir.ui.view.type', 'ir.ui.view.node'
            ]
            model_ids = []
            for model_id in self.env['ir.model'].sudo().search([]):
                if model_id.model and model_id.model in access_model_list and self.env[model_id.model]._abstract:
                    model_ids.append(model_id.id)

            rec.disabled_model_ids = [(6, 0, model_ids)]

    # =========================== Action functions =========================== #
    def action_toggle_active(self):
        for rec in self:
            rec.write({'is_active': not rec.is_active})

    # =========================== Built-in functions =========================== #
    @api.model
    def create(self, vals):
        record = super(AccessManagement, self).create(vals)
        self.clear_caches()
        return record

    def unlink(self):
        res = super(AccessManagement, self).unlink()
        self.clear_caches()
        return res

    def write(self, vals):
        res = super(AccessManagement, self).write(vals)
        self.clear_caches()
        return res

    # =========================== Process functions =========================== #
    @api.model
    def get_action_menu_2_hide(self, model):
        user_access_management_ids = self.env.user.access_management_ids
        access_action_domain = [
            ('model_id.model', '=', model),
            ('access_management_id.is_active', '=', True),
            ('access_management_id', 'in', user_access_management_ids.ids)
        ]
        options = set()
        if any(user_access_management_ids.filtered(lambda a: a.is_active and a.hide_export)):
            options.add(_('Export'))
        if any(user_access_management_ids.filtered(lambda a: a.is_active and a.hide_add_properties)):
            options.add(_('Add Properties'))
        for action in self.env['access.action'].sudo().search(access_action_domain):
            if action.hide_export:
                options.add(_('Export'))
            if action.hide_add_properties:
                options.add(_('Add Properties'))
            if action.hide_archive_unarchive:
                options.add(_('Archive'))
                options.add(_('Unarchive'))
            if action.hide_duplicate:
                options.add(_('Duplicate'))
        return list(options)

    @api.model
    def get_chatter_buttons_2_hide(self, model):
        user_access_management_ids = self.env.user.access_management_ids
        hide_send_mail = False
        hide_log_notes = False
        hide_schedule_activity = False
        if any(user_access_management_ids.filtered(lambda a: a.is_active and a.hide_chatter)):
            hide_send_mail = True
            hide_log_notes = True
            hide_schedule_activity = True
        else:
            if any(user_access_management_ids.filtered(lambda a: a.is_active and a.hide_send_mail)):
                hide_send_mail = True
            if any(user_access_management_ids.filtered(lambda a: a.is_active and a.hide_log_notes)):
                hide_log_notes = True
            if any(user_access_management_ids.filtered(lambda a: a.is_active and a.hide_schedule_activity)):
                hide_schedule_activity = True
        if not hide_send_mail or not hide_log_notes or hide_schedule_activity:
            access_chatter_domain = [
                ('model_id.model', '=', model),
                ('access_management_id.is_active', '=', True),
                ('access_management_id', 'in', user_access_management_ids.ids)
            ]
            chatter_ids = self.env['access.chatter'].sudo().search(access_chatter_domain)
            if not hide_send_mail and any(chatter_ids.filtered(lambda c: c.hide_send_mail)):
                hide_send_mail = True
            if not hide_log_notes and any(chatter_ids.filtered(lambda c: c.hide_log_notes)):
                hide_log_notes = True
            if not hide_schedule_activity and any(chatter_ids.filtered(lambda c: c.hide_schedule_activity)):
                hide_schedule_activity = True
        return {
            'hide_send_mail': hide_send_mail,
            'hide_log_notes': hide_log_notes,
            'hide_schedule_activity': hide_schedule_activity
        }

    @api.model
    def get_fields_2_hide(self, model):
        access_field_domain = [
            ('invisible', '=', True),
            ('model_id.model', '=', model),
            ('access_management_id.is_active', '=', True),
            ('access_management_id', 'in', self.env.user.access_management_ids.ids)
        ]
        hidden_fields = []
        for access_field in self.env['access.field'].sudo().search(access_field_domain):
            for field in access_field.field_ids:
                hidden_fields.append(field.name)
        return hidden_fields
