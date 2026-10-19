import logging

from markupsafe import Markup

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


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

    # ── Stage Permissions / Notifications ────────────────────

    def _is_contract_validator(self):
        return self.env.su or self.env.user.has_group(
            "contract_management.group_contract_validator"
        )

    def _check_stage_allowed(self, new_stage):
        """Only validators may move a contract to approved / active / done."""
        if not new_stage or new_stage.is_cancelled:
            return
        if new_stage.sequence >= 3 and not self._is_contract_validator():
            raise UserError(
                _(
                    "لا تملك صلاحية اعتماد العقد. يجب أن تكون ضمن مجموعة "
                    "«معتمد العقود» للقيام بهذا الإجراء."
                )
            )

    def _stage_needs_project(self):
        """A project is only created once the contract is validated."""
        self.ensure_one()
        return bool(
            self.stage_id
            and not self.stage_id.is_cancelled
            and self.stage_id.sequence >= 3
        )

    def _ensure_project(self):
        """Create and link the project when the contract reaches validation."""
        self.ensure_one()
        if self.project_id:
            if self.project_id.contract_id != self:
                self.project_id.sudo().contract_id = self.id
            return self.project_id

        project = self.env["project.project"].sudo().create(
            {
                "name": self.name or "New",
                "partner_id": self.partner_id.id,
            }
        )
        project.contract_id = self.id
        self.sudo().write({"project_id": project.id})
        return project

    def _notify_contract_validators(self):
        """Notify every member of the validator group that a contract is ready."""
        self.ensure_one()
        group = self.env.ref(
            "contract_management.group_contract_validator",
            raise_if_not_found=False,
        )
        if not group:
            return
        partners = group.sudo().users.filtered(
            lambda user: user.active and not user.share
        ).partner_id
        if not partners:
            _logger.warning(
                "No active contract validators found to notify for contract %s",
                self.id,
            )
            return

        contract_url = (
            f"{self.get_base_url().rstrip('/')}"
            f"/web#id={self.id}&model={self._name}&view_type=form"
        )
        body = Markup(
            "<p>تم رفع العقد <b>%s</b> للعميل <b>%s</b> إلى مرحلة المراجعة.</p>"
            "<p><a href=\"%s\">فتح العقد للمراجعة والاعتماد</a></p>"
        ) % (
            self.name or "",
            self.partner_id.display_name or "",
            contract_url,
        )
        try:
            # sudo(): the actor may not have an email configured, but the
            # notification must still reach the validators.
            self.sudo().message_notify(
                partner_ids=partners.ids,
                subject=_("عقد بانتظار الاعتماد: %s") % (self.name or ""),
                body=body,
            )
        except Exception:
            _logger.exception(
                "Failed to notify contract validators for contract %s", self.id
            )

    # ── CRUD ─────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            stage_id = vals.get("stage_id")
            if stage_id:
                self._check_stage_allowed(
                    self.env["contract.stage"].browse(stage_id)
                )
        records = super().create(vals_list)
        for rec in records:
            if rec.project_id:
                rec.project_id.contract_id = rec.id
            elif rec._stage_needs_project():
                rec._ensure_project()

        review_stage = self.env.ref(
            "contract_management.stage_review", raise_if_not_found=False
        )
        if review_stage:
            for rec in records:
                if rec.stage_id == review_stage:
                    rec._notify_contract_validators()
        return records

    def write(self, vals):
        old_stage_ids = {rec.id: rec.stage_id.id for rec in self}

        if "stage_id" in vals:
            new_stage = (
                self.env["contract.stage"].browse(vals["stage_id"])
                if vals.get("stage_id")
                else self.env["contract.stage"]
            )
            for rec in self:
                if rec.stage_id != new_stage:
                    rec._check_stage_allowed(new_stage)

        result = super().write(vals)
        if "name" in vals:
            for rec in self:
                if rec.project_id and rec.project_id.name != rec.name:
                    rec.project_id.name = rec.name
        if "project_id" in vals:
            for rec in self:
                if rec.project_id:
                    rec.project_id.contract_id = rec.id

        for rec in self:
            if not rec.project_id and rec._stage_needs_project():
                rec._ensure_project()

        if "stage_id" in vals:
            review_stage = self.env.ref(
                "contract_management.stage_review", raise_if_not_found=False
            )
            if review_stage:
                for rec in self:
                    if (
                        rec.stage_id == review_stage
                        and old_stage_ids.get(rec.id) != review_stage.id
                    ):
                        rec._notify_contract_validators()
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