from odoo import models, fields


class ContractStage(models.Model):
    _name = "contract.stage"
    _description = "مراحل العقد"
    _order = "sequence, id"

    name = fields.Char(string="المرحلة", required=True, translate=True)
    sequence = fields.Integer(string="الترتيب", default=10)
    fold = fields.Boolean(string="مطوي")
    is_cancelled = fields.Boolean(string="ملغي")
    is_done = fields.Boolean(string="منتهي")