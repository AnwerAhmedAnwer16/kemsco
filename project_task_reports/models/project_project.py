# models/project_project.py

from odoo import models, fields, api


class ProjectProject(models.Model):
    _inherit = 'project.project'

    purchase_order_ids = fields.One2many('purchase.order', 'project_id', string="Purchase Orders")
    purchase_order_count = fields.Integer(
        string="PO Count",
        compute='_compute_purchase_order_stats',
        store=True,
    )
    purchase_order_total = fields.Monetary(
        string="PO Total",
        compute='_compute_purchase_order_stats',
        currency_field='currency_id',
        store=True,
    )

    @api.depends('purchase_order_ids.amount_total', 'purchase_order_ids.state')
    def _compute_purchase_order_stats(self):
        for project in self:
            orders = project.sudo().purchase_order_ids.filtered(lambda po: po.state != 'cancel')
            project.purchase_order_count = len(orders)
            project.purchase_order_total = sum(orders.mapped('amount_total'))

    def action_view_purchase_orders(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Purchase Orders',
            'res_model': 'purchase.order',
            'view_mode': 'tree,form',
            'domain': [('project_id', '=', self.id)],
        }
