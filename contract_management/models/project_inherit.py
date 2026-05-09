from odoo import models, fields, api


class ProjectProject(models.Model):
    _inherit = "project.project"

    contract_id = fields.Many2one(
        "contract.management",
        compute="_compute_contract_id",
        store=True,
        string="العقد",
    )

    @api.depends("name")
    def _compute_contract_id(self):
        for rec in self:
            contract = self.env["contract.management"].search(
                [("project_id", "=", rec.id)], limit=1
            )
            rec.contract_id = contract if contract else False

    def action_open_contract(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "contract.management",
            "res_id": self.contract_id.id,
            "view_mode": "form",
            "views": [(False, "form")],
        }