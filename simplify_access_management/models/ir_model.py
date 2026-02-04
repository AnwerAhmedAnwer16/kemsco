from odoo import api, fields, models


class IrModel(models.Model):
    _inherit = 'ir.model'

    def name_get(self):
        res = super().name_get()
        if self._context.get('is_access_rights'):
            res = []
            for model in self:
                res.append((model.id, "{} ({})".format(model.name, model.model)))
        return res
