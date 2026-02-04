from odoo import fields, models, api, tools


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    @tools.ormcache('frozenset(self.env.user.groups_id.ids)', 'debug')
    def _visible_menu_ids(self, debug=False):
        res = super()._visible_menu_ids(debug)
        for menu in self.env.user.access_management_ids.mapped('hide_menu_ids'):
            res.discard(menu.id)
        return res
