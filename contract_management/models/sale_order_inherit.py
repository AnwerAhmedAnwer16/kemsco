from odoo import models, fields, api, _


class SaleOrder(models.Model):
    _inherit = "sale.order"

    contract_id = fields.Many2one(
        "contract.management", string="العقد المرتبط"
    )

    def action_confirm(self):
        if self.contract_id and not self.env.context.get("skip_split"):
            return {
                "type": "ir.actions.act_window",
                "name": "تقسيم الفواتير",
                "res_model": "contract.invoice.split.wizard",
                "view_mode": "form",
                "target": "new",
                "context": {
                    "default_sale_order_id": self.id,
                },
            }
        return super().action_confirm()
    def action_open_contract(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "contract.management",
            "res_id": self.contract_id.id,
            "view_mode": "form",
            "views": [(False, "form")],
        }

    def action_open_project_from_contract(self):
        self.ensure_one()
        if self.contract_id and self.contract_id.project_id:
            return {
                "type": "ir.actions.act_window",
                "res_model": "project.project",
                "res_id": self.contract_id.project_id.id,
                "view_mode": "form",
                "views": [(False, "form")],
            }