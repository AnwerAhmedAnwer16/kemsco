from odoo import models, api, fields, _
from datetime import timedelta


class ProjectTask(models.Model):
    _inherit = "project.task"

    @api.model
    def _cron_notify_visit_assignees(self):
        today_plus_2 = fields.Date.today() + timedelta(days=2)
        tasks = self.search(
            [
                ("date_deadline", "=", today_plus_2),
                ("project_id.contract_id", "!=", False),
            ]
        )
        tasks = tasks.filtered(
            lambda t: t.user_ids and not t.stage_id.is_closed
        )
        for task in tasks:
            for user in task.user_ids:
                task.activity_schedule(
                    "mail.mail_activity_data_todo",
                    fields.Date.today(),
                    summary="تذكير بزيارة ميدانية",
                    note=(
                        f"الزيارة الميدانية «{task.name}» مقررة بعد يومين.\n"
                        f"يرجى التأكد من الاستعداد."
                    ),
                    user_id=user.id,
                )