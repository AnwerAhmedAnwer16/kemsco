from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta
from dateutil.relativedelta import relativedelta


class ContractInvoiceSplitLine(models.TransientModel):
    _name = "contract.invoice.split.line"
    _description = "سطر تقسيم الفاتورة"
    _order = "sequence, id"

    wizard_id = fields.Many2one("contract.invoice.split.wizard", string="المعالج")
    sequence = fields.Integer(string="الترتيب", default=10)
    label = fields.Char(string="الوصف")
    date = fields.Date(string="التاريخ")
    percentage = fields.Float(string="النسبة %", digits=(16, 2))
    amount = fields.Float(
        string="المبلغ", compute="_compute_amount", readonly=True, digits=(16, 2)
    )

    @api.depends("percentage", "wizard_id.remaining_amount")
    def _compute_amount(self):
        for rec in self:
            rec.amount = rec.percentage * (rec.wizard_id.remaining_amount or 0) / 100.0


class ContractInvoiceSplitWizard(models.TransientModel):
    _name = "contract.invoice.split.wizard"
    _description = "معالج تقسيم الفواتير"

    sale_order_id = fields.Many2one("sale.order", string="أمر البيع", required=True)
    contract_value = fields.Monetary(
        related="sale_order_id.amount_total",
        string="قيمة العقد",
        readonly=True,
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(related="sale_order_id.currency_id", readonly=True)

    has_advance = fields.Boolean(string="دفعة مقدمة")
    advance_amount = fields.Monetary(
        string="قيمة الدفعة المقدمة", currency_field="currency_id"
    )
    remaining_amount = fields.Monetary(
        string="المبلغ المتبقي للتقسيم",
        compute="_compute_remaining_amount",
        currency_field="currency_id",
        store=True,
    )

    split_method = fields.Selection(
        [("equal", "نسبة موحدة"), ("custom", "تخصيص يدوي")],
        string="طريقة التقسيم",
        default="equal",
        required=True,
    )
    uniform_percentage = fields.Float(
        string="النسبة الموحدة %", digits=(16, 2)
    )
    invoice_count = fields.Integer(string="عدد الفواتير", default=2)
    recurrence_type = fields.Selection(
        [("days", "يوم"), ("weeks", "أسبوع"), ("months", "شهر")],
        string="التكرار",
        default="months",
    )
    recurrence_interval = fields.Integer(string="الفترة", default=1)
    first_invoice_date = fields.Date(
        string="تاريخ أول فاتورة", required=True, default=fields.Date.today
    )
    line_ids = fields.One2many(
        "contract.invoice.split.line", "wizard_id", string="الأسطر"
    )

    total_percentage = fields.Float(
        string="مجموع النسب", compute="_compute_total_percentage", digits=(16, 2)
    )
    total_split_amount = fields.Monetary(
        string="مجموع الدفعات المقسمة",
        compute="_compute_total_split_amount",
        currency_field="currency_id",
    )
    grand_total = fields.Monetary(
        string="الإجمالي الكلي",
        compute="_compute_grand_total",
        currency_field="currency_id",
    )

    # ════════════════ Computes ════════════════

    @api.depends("contract_value", "advance_amount", "has_advance")
    def _compute_remaining_amount(self):
        for rec in self:
            adv = rec.advance_amount if rec.has_advance else 0.0
            rec.remaining_amount = max((rec.contract_value or 0.0) - adv, 0.0)

    @api.depends("line_ids.percentage")
    def _compute_total_percentage(self):
        for rec in self:
            rec.total_percentage = sum(rec.line_ids.mapped("percentage"))

    @api.depends("line_ids.amount")
    def _compute_total_split_amount(self):
        for rec in self:
            rec.total_split_amount = sum(rec.line_ids.mapped("amount"))

    @api.depends("total_split_amount", "has_advance", "advance_amount")
    def _compute_grand_total(self):
        for rec in self:
            adv = rec.advance_amount if rec.has_advance else 0.0
            rec.grand_total = adv + rec.total_split_amount

    # ════════════════ Default Get ════════════════

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        count = res.get("invoice_count", 2)
        first_date = res.get("first_invoice_date") or fields.Date.today()

        if count and first_date:
            uniform_pct = round(100.0 / count, 2)
            res["uniform_percentage"] = uniform_pct

            commands = []
            for i in range(count):
                if i == count - 1:
                    pct = round(100.0 - (uniform_pct * (count - 1)), 2)
                else:
                    pct = uniform_pct
                commands.append(
                    (0, 0, {
                        "sequence": i + 1,
                        "label": f"دفعة {i + 1}",
                        "date": first_date,
                        "percentage": pct,
                    })
                )
            res["line_ids"] = commands

        return res

    # ════════════════ Onchange ════════════════

    @api.onchange(
        "split_method",
        "uniform_percentage",
        "invoice_count",
        "advance_amount",
        "recurrence_type",
        "recurrence_interval",
        "first_invoice_date",
        "has_advance",
    )
    def _onchange_generate_lines(self):
        # لو نسبة موحدة: احسبها تلقائياً من العدد
        if self.split_method == "equal" and self.invoice_count:
            self.uniform_percentage = round(100.0 / self.invoice_count, 2)

        self._generate_lines()

    def _add_interval(self, date):
        if not date:
            return date
        interval = self.recurrence_interval or 1
        if self.recurrence_type == "days":
            return date + timedelta(days=interval)
        elif self.recurrence_type == "weeks":
            return date + timedelta(weeks=interval)
        elif self.recurrence_type == "months":
            return date + relativedelta(months=interval)
        return date

    def _generate_lines(self):
        effective_advance = self.advance_amount if self.has_advance else 0.0
        remaining = (self.contract_value or 0.0) - effective_advance

        if remaining <= 0 or not self.invoice_count or not self.first_invoice_date:
            self.line_ids = [(5,)]
            return

        # أول دفعة بعد الدفعة المقدمة بفترة
        if self.has_advance and effective_advance > 0:
            current_date = self._add_interval(self.first_invoice_date)
        else:
            current_date = self.first_invoice_date

        commands = [(5,)]
        uniform = self.uniform_percentage

        # لو نسبة موحدة وصفرية -> احسب
        if self.split_method == "equal" and (not uniform or uniform <= 0):
            uniform = round(100.0 / self.invoice_count, 2)

        for i in range(self.invoice_count):
            pct = 0.0
            if self.split_method == "equal":
                if i == self.invoice_count - 1:
                    used = round(uniform, 2) * (self.invoice_count - 1)
                    pct = round(100.0 - used, 2)
                else:
                    pct = round(uniform, 2)

            commands.append(
                (0, 0, {
                    "sequence": i + 1,
                    "label": f"دفعة {i + 1}",
                    "date": current_date,
                    "percentage": pct,
                })
            )
            current_date = self._add_interval(current_date)

        self.line_ids = commands

    # ════════════════ Constrains ════════════════

    @api.constrains("line_ids", "split_method")
    def _check_percentage_sum(self):
        for rec in self:
            if rec.split_method == "custom" and rec.line_ids:
                total = sum(rec.line_ids.mapped("percentage"))
                if abs(total - 100.0) > 0.01:
                    raise ValidationError(
                        _("مجموع النسب يجب أن يساوي 100%% (الحالي: %s%%)")
                        % round(total, 2)
                    )

    # ════════════════ Confirm ════════════════

    def action_confirm_split(self):
        self.ensure_one()

        effective_advance = self.advance_amount if self.has_advance else 0.0
        if effective_advance > (self.contract_value or 0.0):
            raise ValidationError(_("قيمة الدفعة المقدمة تتجاوز قيمة العقد"))

        if self.split_method == "custom" and self.line_ids:
            total = sum(self.line_ids.mapped("percentage"))
            if abs(total - 100.0) > 0.01:
                raise ValidationError(
                    _("مجموع النسب يجب أن يساوي 100%% (الحالي: %s%%)")
                    % round(total, 2)
                )

        remaining = max((self.contract_value or 0.0) - effective_advance, 0.0)
        origin = self.sale_order_id.name
        contract = self.sale_order_id.contract_id
        inv_count = 0

        if self.has_advance and effective_advance > 0:
            self._create_invoice(
                date=self.first_invoice_date,
                label=f"دفعة مقدمة - {origin}",
                amount=effective_advance,
                origin=origin,
            )
            inv_count += 1

        if remaining > 0 and self.line_ids:
            for line in self.line_ids:
                if not line.date:
                    raise ValidationError(_("يجب تحديد تاريخ لجميع الدفعات"))
                amount = line.percentage * remaining / 100.0
                label = line.label or (
                    f"دفعة من عقد {contract.name}" if contract else "دفعة"
                )
                self._create_invoice(
                    date=line.date,
                    label=label,
                    amount=amount,
                    origin=origin,
                )
                inv_count += 1

        if inv_count == 0:
            raise ValidationError(_("لا توجد فواتير لإنشائها"))

        self.sale_order_id.with_context(skip_split=True).action_confirm()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("تم بنجاح"),
                "message": _("تم إنشاء %s فاتورة وتأكيد أمر البيع") % inv_count,
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def _create_invoice(self, date, label, amount, origin):
        company = self.sale_order_id.company_id
        revenue_account = self.env["account.account"].search(
            [("account_type", "=", "income"), ("company_id", "=", company.id)],
            limit=1,
        )
        self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.sale_order_id.partner_id.id,
            "invoice_date": date,
            "invoice_date_due": date,
            "invoice_origin": origin,
            "currency_id": self.currency_id.id,
            "invoice_line_ids": [
                (0, 0, {
                    "name": label,
                    "quantity": 1,
                    "price_unit": amount,
                    "account_id": revenue_account.id if revenue_account else False,
                }),
            ],
        })