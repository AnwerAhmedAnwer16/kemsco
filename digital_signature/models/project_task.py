# -*- coding: utf-8 -*-
##############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2023-TODAY Cybrosys Technologies(<https://www.cybrosys.com>).
#    Author: Mruthul Raj @cybrosys(odoo@cybrosys.com)
#
#    You can modify it under the terms of the GNU AFFERO
#    GENERAL PUBLIC LICENSE (AGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU AFFERO GENERAL PUBLIC LICENSE (AGPL v3) for more details.
#
#    You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE
#    (AGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ProjectTask(models.Model):
    """ Extends the 'project.task' model to support digital signatures
    on project tasks."""
    _inherit = "project.task"

    @api.model
    def _default_show_sign(self):
        """Get the default value for the 'Show Digital Signature' field on
        project tasks."""
        return self.env['ir.config_parameter'].sudo().get_param(
            'digital_signature.is_show_digital_sign_task')

    @api.model
    def _default_enable_sign(self):
        """Get the default value for the 'Enable Digital Signature Options'
        field on project tasks."""
        return self.env['ir.config_parameter'].sudo().get_param(
            'digital_signature.is_enable_options_task')

    digital_sign = fields.Binary(string='Signature', help="Binary field to "
                                                          "store digital "
                                                          "signatures.")
    sign_by = fields.Many2one('res.partner', string='Signed By',
                              help="Partner who signed the document.")

    designation = fields.Char(string='Designation', help="Designation of the "
                                                         "person who signed "
                                                         "the document.")
    sign_on = fields.Datetime(string='Signed On', help="Date and time when the "
                                                       "document was signed.")
    is_show_signature = fields.Boolean(string='Show Signature',
                                       default=_default_show_sign,
                                       compute='_compute_show_signature',
                                       help="Determines whether the digital "
                                            "signature should be displayed "
                                            "on project tasks.")
    is_enable_others = fields.Boolean(string="Enable Others",
                                      default=_default_enable_sign,
                                      compute='_compute_enable_others',
                                      help="Enables various digital signature "
                                           "options on project tasks.")

    def _compute_show_signature(self):
        """Compute the 'Show Signature' field on project tasks."""
        is_show_signature = self._default_show_sign()
        for record in self:
            record.is_show_signature = is_show_signature

    def _compute_enable_others(self):
        """Compute the 'Enable Digital Signature Options' field on project tasks."""
        is_enable_others = self._default_enable_sign()
        for record in self:
            record.is_enable_others = is_enable_others

    def write(self, vals):
        """Override write to check for signature when task is marked as done."""
        if 'state' in vals and vals.get('state') == 'done':
            for record in self:
                if self.env['ir.config_parameter'].sudo().get_param(
                        'digital_signature.is_confirm_sign_task') and \
                        record.digital_sign is False:
                    raise UserError(_("Signature is missing"))
        return super(ProjectTask, self).write(vals)
