from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.home import Home, ensure_db


class AccessHome(Home):

    @http.route('/web', type='http', auth="none")
    def web_client(self, s_action=None, **kw):
        ensure_db()
        if kw.get('debug') != "0":
            user = request.env.user.browse(request.session.uid)
            if any(user.access_management_ids.filtered(lambda a: a.is_active and a.disable_debug_mode)):
                return request.redirect('/web?debug=0')

        return super(AccessHome, self).web_client(s_action=s_action, **kw)
