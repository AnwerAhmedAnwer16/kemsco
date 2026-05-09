import odoo
import logging
from odoo import fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ClearDataModel(models.Model):
    _name = 'clear.data.model'
    _description = "Clear Data"

    name = fields.Char(string="Models group Name")
    internal_model_list = fields.Char(
        string='Always clear',
        help="Model in this list do not need installed. style like this:[string,string,...]")
    model_clear_ids = fields.Many2many(
        comodel_name="ir.model", relation='clear_data_ir_model_rel', column1='group_id', column2='model_id',
        domain=[('model', 'not in', ['clear.data.model'])], ondelete='cascade')
    auto_clear_ir_sequence = fields.Boolean(string="Auto clear ir sequence", default=True)

    def action_do_clear(self):
        self.ensure_one()
        self._do_clear_internal_model()
        self._do_clear_model_relation()

        if self.auto_clear_ir_sequence:
            self._do_clear_ir_sequence()
        return True

    def _do_clear_model_relation(self):
        self.ensure_one()
        for model_id in self.model_clear_ids:
            if model_id:
                self._do_clear_by_model_name(model_id.model)

    def _do_clear_internal_model(self):
        self.ensure_one()
        if not self.internal_model_list:
            return True

        try:
            model_list = eval(self.internal_model_list.strip())
            if not isinstance(model_list, list):
                raise UserError('Always clear model list format is incorrect!')
        except:
            raise UserError('Always clear model list format is incorrect!')

        if all(model_list):
            for model_name in model_list:
                self._do_clear_by_model_name(model_name)

        return True

    def _do_clear_by_model_name(self, model_name):
        self.ensure_one()
        model_obj = self.pool.get(model_name)
        if not model_obj or not odoo.tools.table_exists(self._cr, model_obj._table):
            return
        self._cr.execute("delete from %s" % model_obj._table)

    def _do_clear_ir_sequence(self):
        cr = self._cr
        cr.execute("update ir_sequence set number_next=1")
        cr.execute("update ir_sequence_date_range set number_next=1")
        seq_list = self.env['ir.sequence'].search([('implementation', '=', 'standard')])
        if seq_list:
            for seq in seq_list:
                cr.execute("ALTER SEQUENCE ir_sequence_%03d RESTART WITH 1" % seq.id)
