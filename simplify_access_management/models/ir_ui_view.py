import ast
from odoo import api, fields, models, _
from odoo.http import request

class IrUiView(models.Model):
    _inherit = 'ir.ui.view'

    def _get_access_management_uid(self):
        """Return the real user id to apply access rules, even when the view is built with sudo."""
        # HTTP request always carries the original user environment, use it first when available.
        if request and request.env:
            uid = request.env.uid
            if uid:
                return uid
        # When sudo is used, the context still keeps the original uid.
        uid = self.env.context.get('uid')
        if uid:
            return uid
        # Fallback to the current env user (covers cron/background usage).
        return self.env.user.id

    def _postprocess_tag_field(self, node, name_manager, node_info):
        super()._postprocess_tag_field(node, name_manager, node_info)

        access_field_domain = [
            ('access_management_id.is_active', '=', True),
            ('access_management_id.user_ids', 'in', self._get_access_management_uid()),
            ('model_id.model', '=', name_manager.model._name)
        ]
        for access_field in self.env['access.field'].sudo().search(access_field_domain):
            for field_id in access_field.field_ids:
                if node.get('name') == field_id.name:
                    if access_field.external_link:
                        if 'widget' in node.attrib.keys():
                            if node.attrib['widget'] == 'product_configurator':
                                del node.attrib['widget']
                        if 'options' in node.attrib.keys():
                            options_dict = ast.literal_eval(node.attrib['options'])
                            options_dict.update({"no_open": True})
                            node.attrib['options'] = str(options_dict)
                        else:
                            node.attrib['options'] = str({"no_open": True})
                        node.attrib.update({'no_open': 'true'})
                    if access_field.hide_create:
                        if 'options' in node.attrib.keys():
                            options_dict = ast.literal_eval(node.attrib['options'])
                            options_dict.update({"no_create": True, "no_create_edit": True})
                            node.attrib['options'] = str(options_dict)
                        else:
                            node.attrib['options'] = str({"no_create": True, "no_create_edit": True})
                        node.attrib.update({'can_create': 'false'})
                    if access_field.hide_edit:
                        if 'options' in node.attrib.keys():
                            options_dict = ast.literal_eval(node.attrib['options'])
                            options_dict.update({"no_edit": True, "no_create_edit": True})
                            node.attrib['options'] = str(options_dict)
                        else:
                            node.attrib['options'] = str({"no_edit": True, "no_create_edit": True})
                        node.attrib.update({'can_write': 'false'})
                    if access_field.invisible:
                        node.set('invisible', '1')
                    if access_field.readonly:
                        node.set('readonly', '1')
                        node.set('force_save', '1')
                    if access_field.required:
                        node.set('required', '1')

        field_name = node.get('name')
        field_info = name_manager.model.fields_get([field_name])
        if field_info and field_info[field_name].get('relation'):
            access_action_domain = [
                ('access_management_id.is_active', '=', True),
                ('access_management_id.user_ids', 'in', self._get_access_management_uid()),
                ('model_id.model', '=', field_info[field_name]['relation'])
            ]
            for access_action in self.env['access.action'].sudo().search(access_action_domain):
                if access_action.hide_external_link:
                    if 'widget' in node.attrib.keys():
                        if node.attrib['widget'] == 'product_configurator':
                            del node.attrib['widget']
                    if 'options' in node.attrib.keys():
                        options_dict = ast.literal_eval(node.attrib['options'])
                        options_dict.update({"no_open": True})
                        node.attrib['options'] = str(options_dict)
                    else:
                        node.attrib['options'] = str({"no_open": True})
                    node.attrib.update({'no_open': 'true'})
                if access_action.hide_link_create:
                    if 'options' in node.attrib.keys():
                        options_dict = ast.literal_eval(node.attrib['options'])
                        options_dict.update({"no_create": True, "no_create_edit": True})
                        node.attrib['options'] = str(options_dict)
                    else:
                        node.attrib['options'] = str({"no_create": True, "no_create_edit": True})
                    node.attrib.update({'can_create': 'false'})
                if access_action.hide_link_edit:
                    if 'options' in node.attrib.keys():
                        options_dict = ast.literal_eval(node.attrib['options'])
                        options_dict.update({"no_edit": True, "no_create_edit": True})
                        node.attrib['options'] = str(options_dict)
                    else:
                        node.attrib['options'] = str({"no_edit": True, "no_create_edit": True})
                    node.attrib.update({'can_write': 'false'})

    def _postprocess_tag_label(self, node, name_manager, node_info):
        super()._postprocess_tag_label(node, name_manager, node_info)

        access_field_domain = [
            ('access_management_id.is_active', '=', True),
            ('access_management_id.user_ids', 'in', self._get_access_management_uid()),
            ('model_id.model', '=', name_manager.model._name)
        ]
        for access_field in self.env['access.field'].sudo().search(access_field_domain):
            for field_id in access_field.field_ids:
                if node.attrib['for'] == field_id.name:
                    if access_field.invisible:
                        node.set('invisible', '1')

    def _postprocess_tag_button(self, node, name_manager, node_info):
        postprocessor = getattr(super(IrUiView, self), '_postprocess_tag_button', False)
        if postprocessor:
            super(IrUiView, self)._postprocess_tag_button(node, name_manager, node_info)

        access_view_node_domain = [
            ('access_management_id.is_active', '=', True),
            ('access_management_id.user_ids', 'in', self._get_access_management_uid()),
            ('model_id.model', '=', name_manager.model._name)
        ]
        access_view_node_ids = self.env['access.view.node'].sudo().search(access_view_node_domain)
        for access_btn in access_view_node_ids.mapped('ir_ui_view_btn_node_ids'):
            if node.get('name') == access_btn.attribute_name:
                node.set('invisible', '1')

    def _postprocess_tag_page(self, node, name_manager, node_info):
        # Hide Any Notebook Page
        postprocessor = getattr(super(IrUiView, self), '_postprocess_tag_page', False)
        if postprocessor:
            super(IrUiView, self)._postprocess_tag_page(node, name_manager, node_info)

        access_view_node_domain = [
            ('access_management_id.is_active', '=', True),
            ('access_management_id.user_ids', 'in', self._get_access_management_uid()),
            ('model_id.model', '=', name_manager.model._name)
        ]
        access_view_node_ids = self.env['access.view.node'].sudo().search(access_view_node_domain)
        for access_page in access_view_node_ids.mapped('ir_ui_view_page_node_ids'):
            if node.get('name') == access_page.attribute_name:
                node.set('invisible', '1')
            elif node.get('string') == _(access_page.attribute_string):
                node.set('invisible', '1')

    def _postprocess_tag_a(self, node, name_manager, node_info):
        postprocessor = getattr(super(IrUiView, self), '_postprocess_tag_a', False)
        if postprocessor:
            super(IrUiView, self)._postprocess_tag_a(node, name_manager, node_info)

        access_view_node_domain = [
            ('access_management_id.is_active', '=', True),
            ('access_management_id.user_ids', 'in', self._get_access_management_uid()),
            ('model_id.model', '=', name_manager.model._name)
        ]
        access_view_node_ids = self.env['access.view.node'].sudo().search(access_view_node_domain)
        for access_link in access_view_node_ids.mapped('ir_ui_view_link_node_ids'):
            if (node.text and '\n' not in node.text and 'type' in node.attrib.keys() and
                    node.attrib['type'] and 'name' in node.attrib.keys() and node.attrib['name']):
                if (node.get('name') == access_link.attribute_name and node.text == access_link.attribute_string and
                        node.get('type') == access_link.button_type):
                    node.set('invisible', '1')

    def _postprocess_tag_filter(self, node, name_manager, node_info):
        postprocessor = getattr(super(IrUiView, self), '_postprocess_tag_filter', False)
        if postprocessor:
            super(IrUiView, self)._postprocess_tag_filter(node, name_manager, node_info)

        access_view_node_domain = [
            ('access_management_id.is_active', '=', True),
            ('access_management_id.user_ids', 'in', self._get_access_management_uid()),
            ('model_id.model', '=', name_manager.model._name)
        ]
        access_view_node_ids = self.env['access.view.node'].sudo().search(access_view_node_domain)
        # Access filters
        for access_filter in access_view_node_ids.mapped('ir_ui_view_filter_node_ids'):
            if node.get('name') == access_filter.attribute_name:
                node.set('invisible', '1')
        # Access group by
        for access_group_by in access_view_node_ids.mapped('ir_ui_view_group_by_node_ids'):
            if node.get('name') == access_group_by.attribute_name:
                node.set('invisible', '1')
