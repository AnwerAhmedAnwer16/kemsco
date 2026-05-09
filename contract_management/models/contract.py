from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ContractManagement(models.Model):
    _name = "contract.management"
    _description = "إدارة العقود"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name desc"

    name = fields.Char(string="اسم العقد", required=True, tracking=True)
    partner_id = fields.Many2one(
        "res.partner", string="العميل", required=True, tracking=True
    )
    date_start = fields.Date(string="تاريخ البداية", required=True, tracking=True)
    date_end = fields.Date(string="تاريخ الانتهاء", required=True, tracking=True)
    contract_value = fields.Monetary(
        string="قيمة العقد", currency_field="currency_id"
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="العملة",
        default=lambda self: self.env.company.currency_id,
    )
    stage_id = fields.Many2one(
        "contract.stage",
        string="المرحلة",
        default=lambda self: self.env.ref(
            "contract_management.stage_draft"
        ).id,
        tracking=True,
        group_expand="_read_group_stage_ids",
    )
    user_id = fields.Many2one(
        "res.users", string="المسؤول", default=lambda self: self.env.uid
    )
    project_id = fields.Many2one("project.project", string="المشروع", readonly=True)
    sale_order_id = fields.Many2one(
        "sale.order", string="عرض السعر", readonly=True
    )
    task_count = fields.Integer(
        string="عدد المهام", compute="_compute_task_count"
    )
    invoice_count = fields.Integer(
        string="عدد الفواتير", compute="_compute_invoice_count"
    )
    note = fields.Html(string="ملاحظات")
    color = fields.Integer(string="اللون")
    
    visits_frequency = fields.Char(string="تكرار الزيارات", default="شهر")
    payment_terms = fields.Text(string="شروط الدفع")
    signature = fields.Binary(string="توقيع العميل")
    
    stage_sequence = fields.Integer(related="stage_id.sequence", string="تسلسل المرحلة", store=True)
    stage_is_done = fields.Boolean(related="stage_id.is_done", string="منتهي؟", store=True)
    stage_is_cancelled = fields.Boolean(related="stage_id.is_cancelled", string="ملغي؟", store=True)

    # ── Compute ──────────────────────────────────────────────

    @api.depends("project_id")
    def _compute_task_count(self):
        for rec in self:
            if rec.project_id:
                rec.task_count = self.env["project.task"].search_count(
                    [("project_id", "=", rec.project_id.id)]
                )
            else:
                rec.task_count = 0

    @api.depends("sale_order_id")
    def _compute_invoice_count(self):
        for rec in self:
            if rec.sale_order_id:
                rec.invoice_count = self.env["account.move"].search_count(
                    [
                        ("move_type", "=", "out_invoice"),
                        ("invoice_origin", "=", rec.sale_order_id.name),
                    ]
                )
            else:
                rec.invoice_count = 0

    @api.model
    def _read_group_stage_ids(self, stages, domain, order):
        return stages.search([], order=order)

    # ── CRUD ─────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("project_id"):
                project_vals = {
                    "name": vals.get("name", "New"),
                    "partner_id": vals.get("partner_id"),
                }
                project = (
                    self.env["project.project"].sudo().create(project_vals)
                )
                vals["project_id"] = project.id
        records = super().create(vals_list)
        for rec in records:
            if rec.project_id:
                rec.project_id.contract_id = rec.id
        return records

    def write(self, vals):
        result = super().write(vals)
        if "name" in vals:
            for rec in self:
                if rec.project_id and rec.project_id.name != rec.name:
                    rec.project_id.name = rec.name
        if "project_id" in vals:
            for rec in self:
                if rec.project_id:
                    rec.project_id.contract_id = rec.id
        return result

    # ── Stage Actions ────────────────────────────────────────

    def action_to_review(self):
        stage = self.env.ref("contract_management.stage_review")
        self.write({"stage_id": stage.id})

    def action_approve(self):
        stage = self.env.ref("contract_management.stage_approved")
        self.write({"stage_id": stage.id})

    def action_set_active(self):
        stage = self.env.ref("contract_management.stage_active")
        self.write({"stage_id": stage.id})

    def action_set_done(self):
        stage = self.env.ref("contract_management.stage_done")
        self.write({"stage_id": stage.id})

    def action_cancel(self):
        stage = self.env.ref("contract_management.stage_cancelled")
        self.write({"stage_id": stage.id})

    def action_reactivate(self):
        stage = self.env.ref("contract_management.stage_active")
        self.write({"stage_id": stage.id})

    # ── Sale Quotation ───────────────────────────────────────

    def action_create_sale_quotation(self):
        self.ensure_one()
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner_id.id,
                "contract_id": self.id,
            }
        )
        self.sale_order_id = order.id
        return {
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "res_id": order.id,
            "view_mode": "form",
            "views": [(False, "form")],
        }

    # ── Smart‑Button Actions ─────────────────────────────────

    def action_open_tasks(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "المهام",
            "res_model": "project.task",
            "view_mode": "list,form",
            "domain": [("project_id", "=", self.project_id.id)],
        }

    def action_open_invoices(self):
        self.ensure_one()
        if self.sale_order_id:
            domain = [
                ("move_type", "=", "out_invoice"),
                ("invoice_origin", "=", self.sale_order_id.name),
            ]
        else:
            domain = [
                ("move_type", "=", "out_invoice"),
                ("invoice_origin", "=", self.name),
            ]
        return {
            "type": "ir.actions.act_window",
            "name": "الفواتير",
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": domain,
        }

    def action_open_sale_order(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "res_id": self.sale_order_id.id,
            "view_mode": "form",
            "views": [(False, "form")],
        }

    def action_open_project(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "project.project",
            "res_id": self.project_id.id,
            "view_mode": "form",
            "views": [(False, "form")],
        }

    # ── Visit Wizard Launcher ────────────────────────────────

    def action_generate_visits_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "توليد الزيارات الميدانية",
            "res_model": "contract.visit.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_contract_id": self.id},
        }