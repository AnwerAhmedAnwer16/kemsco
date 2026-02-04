from odoo.http import request
from odoo.addons.web.controllers.export import Export


class AccessExport(Export):

    def fields_get(self, model):
        fields = super(AccessExport, self).fields_get(model)
        access_field_domain = [
            ('model_id.model', '=', model),
            ('access_management_id.is_active', '=', True),
            ('access_management_id', 'in', request.env.user.access_management_ids.ids)
        ]
        hide_field_ids = request.env['access.field'].search(access_field_domain)
        if not hide_field_ids:
            return fields
        else:
            for key, value in list(fields.items()):
                for field in hide_field_ids.field_ids:
                    if key == field.name and key != "id":
                        del fields[key]
            return fields
