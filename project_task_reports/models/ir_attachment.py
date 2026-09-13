# models/ir_attachment.py

from odoo import models, fields, api


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    task_report_url = fields.Char(
        string="Report URL",
        compute='_compute_task_report_url',
        help="Absolute download URL used in the printed task report. "
             "Attachments are served through Odoo (/web/content) so the "
             "normal access control applies, including for external storage.",
    )

    @api.depends('access_token')
    def _compute_task_report_url(self):
        base_url = (self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url', '') or '').rstrip('/')
        for attachment in self:
            attachment.task_report_url = attachment._task_report_content_url(base_url)

    def _task_report_content_url(self, base_url):
        """Standard Odoo download URL, including the access token when the
        attachment has one so the link also works for users who are not
        logged in."""
        self.ensure_one()
        token = self.sudo().access_token
        suffix = '&access_token=%s' % token if token else ''
        return '%s/web/content/%s?download=true%s' % (base_url, self.id, suffix)
