from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import timedelta
from dateutil.relativedelta import relativedelta


class ContractVisitWizard(models.TransientModel):
    _name = "contract.visit.wizard"
    _description = "معالج توليد الزيارات الميدانية"

    contract_id = fields.Many2one(
        "contract.management", string="العقد", required=True
    )
    visit_count = fields.Integer(string="عدد الزيارات", required=True)
    first_visit_date = fields.Date(string="تاريخ أول زيارة", required=True)
    recurrence_type = fields.Selection(
        [
            ("days", "يوم"),
            ("weeks", "أسبوع"),
            ("months", "شهر"),
        ],
        string="التكرار",
        default="months",
    )
    recurrence_interval = fields.Integer(string="الفترة", default=1)

    def action_generate_visits(self):
        self.ensure_one()
        contract = self.contract_id
        if not contract.project_id:
            raise UserError(_("لا يوجد مشروع مرتبط بالعقد"))

        # البحث عن مرحلة "جديد" في المشروع
        stage_new = self.env["project.task.type"].search(
            [
                ("project_ids", "=", contract.project_id.id),
            ],
            order="sequence asc",
            limit=1,
        )

        task_vals_list = []
        current_date = self.first_visit_date

        for i in range(self.visit_count):
            vals = {
                "name": f"زيارة {i + 1} - {contract.name}",
                "project_id": contract.project_id.id,
                "date_deadline": current_date,
            }
            if stage_new:
                vals["stage_id"] = stage_new.id
            task_vals_list.append(vals)

            if self.recurrence_type == "days":
                current_date += timedelta(days=self.recurrence_interval)
            elif self.recurrence_type == "weeks":
                current_date += timedelta(weeks=self.recurrence_interval)
            elif self.recurrence_type == "months":
                current_date += relativedelta(months=self.recurrence_interval)

        self.env["project.task"].create(task_vals_list)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("تم بنجاح"),
                "message": _(
                    "تم إنشاء %s زيارة ميدانية بنجاح"
                ) % self.visit_count,
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }