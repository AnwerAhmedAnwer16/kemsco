# models/purchase_order.py

from odoo import models, fields


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    task_id = fields.Many2one(
        'project.task',
        string="Task",
        index=True,
        ondelete='set null',
        copy=False,
    )
    project_id = fields.Many2one(
        'project.project',
        string="Project",
        related='task_id.project_id',
        store=True,
        index=True,
        readonly=True,
    )
