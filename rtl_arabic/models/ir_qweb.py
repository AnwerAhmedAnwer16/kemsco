# -*- coding: utf-8 -*-

from odoo import models


class IrQWeb(models.AbstractModel):
    _inherit = "ir.qweb"

    def _render(self, id_or_xml_id, values=None, **options):
        values = values or {}
        if "lang_direction" not in values:
            lang = (options or {}).get("lang") or self.env.context.get("lang") or "en_US"
            direction = self.env["res.lang"]._lang_get_direction(lang) or "ltr"
            values["lang_direction"] = direction
        return super()._render(id_or_xml_id, values=values, **options)

