from odoo.osv import expression
from odoo import api, fields, models, _
from odoo.exceptions import AccessError
from odoo.tools.safe_eval import safe_eval


class BaseModel(models.AbstractModel):
    _inherit = 'base'

    @api.model
    def get_views(self, views, options=None):
        self.env[self._name].clear_caches()
        server_action_ids, report_action_ids = [], []
        access_action_domain = [
            ('model_id.model', '=', self._name),
            ('access_management_id', 'in', self.env.user.access_management_ids.ids)
        ]
        for access_action in self.env['access.action'].sudo().search(access_action_domain):
            server_action_ids += access_action.mapped('server_action_ids.action_id').ids
            report_action_ids += access_action.mapped('report_action_ids.action_id').ids
            for view_type in access_action.ir_ui_view_type_ids.mapped('tech_name'):
                for view in views:
                    if view_type == view[1]:
                        views.pop(views.index(view))

        res = super(BaseModel, self).get_views(views, options=options)
        if 'views' in res.keys():
            for view in ['list', 'form']:
                if view in res['views'].keys():
                    if 'toolbar' in res['views'][view].keys():
                        if 'action' in res['views'][view]['toolbar'].keys():
                            action = res['views'][view]['toolbar']['action'][:]
                            for act in action:
                                if act['id'] in server_action_ids:
                                    res['views'][view]['toolbar']['action'].remove(act)
                        if 'print' in res['views'][view]['toolbar'].keys():
                            prints = res['views'][view]['toolbar']['print'][:]
                            for pri in prints:
                                if pri['id'] in report_action_ids:
                                    res['views'][view]['toolbar']['print'].remove(pri)

        return res

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        user_access_management_ids = self.env.user.access_management_ids
        shared_domain = [
            ('model_id.model', '=', self._name),
            ('access_management_id.is_active', '=', True),
            ('access_management_id', 'in', user_access_management_ids.ids)
        ]
        # Global Hide Chatter
        if view_type == 'form':
            if any(user_access_management_ids.filtered(lambda a: a.is_active and a.hide_chatter)):
                for div in arch.xpath("//div[@class='oe_chatter']"):
                    div.getparent().remove(div)
            else:
                if self.env['access.chatter'].sudo().search(shared_domain + [('hide_chatter', '=', True)], limit=1):
                    for div in arch.xpath("//div[@class='oe_chatter']"):
                        div.getparent().remove(div)
        # Global Hide Import
        if any(user_access_management_ids.filtered(lambda a: a.is_active and a.hide_import)):
            if view_type in ['kanban', 'tree']:
                arch.attrib.update({'import': 'false'})
        if any(user_access_management_ids.filtered(lambda a: a.is_active and a.readonly)):
            if view_type in ['form', 'tree', 'kanban']:
                arch.attrib.update({'create': 'false', 'delete': 'false', 'edit': 'false'})
        else:
            # Restrict model create edit delete, import
            if view_type in ['form', 'tree', 'kanban']:
                access_action_ids = self.env['access.action'].sudo().search(shared_domain)
                if any(access_action_ids.filtered(lambda act: act.hide_create)):
                    arch.attrib.update({'create': 'false'})
                if any(access_action_ids.filtered(lambda act: act.hide_edit)):
                    arch.attrib.update({'edit': 'false'})
                if any(access_action_ids.filtered(lambda act: act.hide_delete)):
                    arch.attrib.update({'delete': 'false'})
                if any(access_action_ids.filtered(lambda act: act.readonly)):
                    arch.attrib.update({'create': 'false', 'delete': 'false', 'edit': 'false'})
                if view_type in ['tree', 'kanban']:
                    if any(access_action_ids.filtered(lambda act: act.hide_import)):
                        arch.attrib.update({'import': 'false'})

                access_domain_ids = self.env['access.domain'].sudo().search(shared_domain)
                if any(access_domain_ids.filtered(lambda ad: ad.restrict_create)):
                    arch.attrib.update({'create': 'false'})
                if any(access_domain_ids.filtered(lambda ad: ad.restrict_edit)):
                    arch.attrib.update({'edit': 'false'})
                if any(access_domain_ids.filtered(lambda ad: ad.restrict_delete)):
                    arch.attrib.update({'delete': 'false'})
        return arch, view

    def _get_access_management_domain(self, model):
        records = []
        if not model:
            return records
        try:
            self._cr.execute(f"SELECT id FROM ir_model WHERE model='{model}'")
            model_numeric_id = self._cr.fetchone()[0]
            if model_numeric_id and isinstance(model_numeric_id, int) and self.env.user:
                self._cr.execute(f"""
                    SELECT ad.id
                    FROM access_domain as ad
                    WHERE ad.model_id={model_numeric_id} 
                    AND ad.access_management_id IN (
                        SELECT am.id 
                        FROM access_management as am 
                        WHERE am.is_active='true' 
                        AND am.id IN (
                            SELECT amusr.access_management_id
                            FROM access_management_users_rel as amusr
                            WHERE amusr.user_id={self.env.user.id}
                        )
                    )
                """)
                records = self.env['access.domain'].sudo().browse(row[0] for row in self._cr.fetchall())
        except:
            pass
        return records

    def _display_access_management_error(self, mode, rule):
        msg_heads = {
            'unlink': _(
                "Due to access management rule (%(access_rule)s),\n"
                "You are not allowed to delete records from (%(document_model)s) model.",
                access_rule=rule, document_model=self._name),
            'write': _(
                "Due to access management rule (%(access_rule)s),\n"
                "You are not allowed to edit records from (%(document_model)s) model.",
                access_rule=rule, document_model=self._name),
            'create': _(
                "Due to access management rule (%(access_rule)s),\n"
                "You are not allowed to create records from (%(document_model)s) model.",
                access_rule=rule, document_model=self._name),
        }
        raise AccessError(msg_heads[mode])

    def _check_access_management_right(self, mode):
        access = True
        access_rule = None
        for access_domain in self._get_access_management_domain(model=self._name):
            access_rule = access_domain.access_management_id.name
            if mode == 'create' and access_domain.restrict_create:
                access = False
                break
            elif mode in ['write', 'unlink']:
                domain = safe_eval(access_domain.domain) if access_domain.domain else []
                search_domain = expression.normalize_domain(domain)
                records = self.sudo().search(search_domain)
                if self in records:
                    if access_domain.restrict_edit:
                        access = False
                    if access_domain.restrict_delete:
                        access = False
                    break
        if not access:
            self._display_access_management_error(mode=mode, rule=access_rule)

    def unlink(self):
        value = self.env['ir.config_parameter'].sudo().search([
            ('key', '=', 'uninstall_simplify_access_management')],limit=1).value
        if not value:
            for rec in self:
                if rec._name:
                    rec._check_access_management_right(mode='unlink')

        return super().unlink()

    def write(self, vals):
        value = self.env['ir.config_parameter'].sudo().search([
            ('key', '=', 'uninstall_simplify_access_management')], limit=1).value
        if not value:
            for rec in self:
                if rec._name:
                    rec._check_access_management_right(mode='write')

        return super().write(vals)

    @api.model_create_multi
    @api.returns('self', lambda value: value.id)
    def create(self, vals_list):
        value = self.env['ir.config_parameter'].sudo().search([
            ('key', '=', 'uninstall_simplify_access_management')], limit=1).value
        if not value:
            if self._name:
                self._check_access_management_right(mode='create')

        return super().create(vals_list)
