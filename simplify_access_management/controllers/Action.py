from odoo import http
from odoo.http import request
from odoo.tools.translate import _
from odoo.exceptions import UserError
from odoo.addons.web.controllers.action import Action


class AccessAction(Action):

    @http.route('/web/action/load', type='json', auth="user")
    def load(self, action_id, additional_context=None):
        res = super(AccessAction, self).load(action_id, additional_context=additional_context)
        if res:
            access_action_domain = [
                ('model_id.model', '=', res.get('res_model')),
                ('access_management_id', 'in', request.env.user.access_management_ids.ids)
            ]
            access_action_ids = request.env['access.action'].sudo().search(access_action_domain)
            for view_type in set(access_action_ids.mapped('ir_ui_view_type_ids.tech_name')):
                for view in res.get('views'):
                    if view_type == view[1]:
                        res['views'].pop(res['views'].index(view))
            if 'views' in res.keys() and not len(res.get('views')):
                raise UserError(
                    _("You don't have the permission to access any views. Please contact to administrator."))
        return res
