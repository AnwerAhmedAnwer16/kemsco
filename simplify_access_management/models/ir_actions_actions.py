from odoo import api, fields, models, tools


class IrActionsActions(models.Model):
    _inherit = 'ir.actions.actions'

    @api.model
    def create(self, vals):
        record = super(IrActionsActions, self).create(vals)
        for rec in record:
            self.env['ir.access.actions'].create({'name': rec.name, 'action_id': rec.id})
        return record

    def unlink(self):
        for record in self:
            self.env['ir.access.actions'].search([('action_id', '=', record.id)]).unlink()
        return super(IrActionsActions, self).unlink()
