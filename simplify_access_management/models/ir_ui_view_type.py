from odoo import fields, models, api, _


class IrUiViewType(models.Model):
    _name = 'ir.ui.view.type'
    _description = "Ir Ui View Type"

    name = fields.Char('Name')
    tech_name = fields.Char('Technical Name')


    