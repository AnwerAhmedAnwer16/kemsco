from odoo import models, api, fields, _
from datetime import timedelta


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.model
    def _cron_notify_invoice_due(self):
        today_plus_3 = fields.Date.today() + timedelta(days=3)
        invoices = self.search(
            [
                ("move_type", "=", "out_invoice"),
                ("state", "=", "posted"),
                ("payment_state", "not in", ["paid", "in_payment"]),
                ("invoice_date_due", "=", today_plus_3),
            ]
        )
        for invoice in invoices:
            if not invoice.invoice_origin:
                continue
            sale = self.env["sale.order"].search(
                [("name", "=", invoice.invoice_origin)], limit=1
            )
            if sale and sale.contract_id and sale.contract_id.user_id:
                contract = sale.contract_id
                user = contract.user_id
                message = (
                    f"🔔 تذكير بتحصيل فاتورة\n"
                    f"الفاتورة: {invoice.name}\n"
                    f"المبلغ: {invoice.amount_total} {invoice.currency_id.name}\n"
                    f"العميل: {invoice.partner_id.name}\n"
                    f"متبقي ٣ أيام على تاريخ الاستحقاق ({invoice.invoice_date_due})"
                )

                # إرسال إشعار يظهر في الجرس
                contract.with_user(user.id).message_post(
                    body=message,
                    message_type="notification",
                    subtype_xmlid="mail.mt_comment",
                    partner_ids=user.partner_id.ids,
                    notification_ids=[
                        (0, 0, {
                            "res_partner_id": user.partner_id.id,
                            "notification_type": "inbox",
                        })
                    ],
                )