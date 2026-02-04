from odoo.http import request
from odoo import api, fields, models


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def session_info(self):
        res = super().session_info()
        for access in request.env.user.access_management_ids:
            if access.hide_db_name:
                # res.update({'hide_db_name': access.hide_db_name, })
                res.update({'db': " "})
        return res
