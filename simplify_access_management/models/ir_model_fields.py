from odoo import api, fields, models


class IrModelField(models.Model):
    _inherit = 'ir.model.fields'

    def name_get(self):
        res = super().name_get()
        if self._context.get('is_access_rights'):
            res = []
            for field in self:
                res.append((field.id, "{} => {} ({})".format(
                    field.field_description, field.name, field.model_id.model)))
        return res
