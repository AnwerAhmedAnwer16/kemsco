from odoo import fields, models, api, _


class IrAccessActions(models.Model):
    _name = 'ir.access.actions'
    _description = "Ir Access Actions"

    name = fields.Char(string='Name')
    action_id = fields.Many2one(comodel_name='ir.actions.actions', string='Action')

    