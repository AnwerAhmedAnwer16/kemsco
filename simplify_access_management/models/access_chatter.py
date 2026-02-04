from odoo import fields, models, api, _


class AccessChatter(models.Model):
    _name = 'access.chatter'
    _description = "Access Chatter"

    access_management_id = fields.Many2one(comodel_name='access.management', string='Access Management')
    model_id = fields.Many2one(comodel_name='ir.model', string='Model', ondelete='cascade')
    hide_chatter = fields.Boolean(
        string='Chatter', help="The Chatter will be hidden in selected model from the specified users.")
    hide_send_mail = fields.Boolean(
        string='Send Message',
        help="The Send Message button will be hidden in chatter of selected model from the specified users.")
    hide_log_notes = fields.Boolean(
        string='Log Notes',
        help="The Log Notes button will be hidden in chatter of selected model from the specified users.")
    hide_schedule_activity = fields.Boolean(
        string='Schedule Activity',
        help="The Schedule Activity button will be hidden in chatter of selected model from the specified users.")
