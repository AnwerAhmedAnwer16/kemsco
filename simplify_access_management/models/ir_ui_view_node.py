from odoo import api, fields, models


class IrUiViewNode(models.Model):
    _name = 'ir.ui.view.node'
    _description = 'Ir Ui View Node'
    _rec_name = 'attribute_string'

    model_id = fields.Many2one(comodel_name='ir.model', string='Model', index=True, ondelete='cascade', required=True)
    node_option = fields.Selection(selection=[
        ('button', 'Button'), ('page', 'Page'), ('link', 'Link'), ('filter', 'Filter'), ('group_by', 'Group By')],
        string="Node Option",  required=True)
    attribute_name = fields.Char(string='Attribute Name')
    attribute_string = fields.Char(string='Attribute String', required=True)

    button_type = fields.Selection(selection=[('object', 'Object'), ('action', 'Action')], string="Button Type")
    is_smart_button = fields.Boolean(string='Smart Button')

    def name_get(self):
        result = []
        for rec in self:
            name = rec.attribute_string
            if rec.attribute_name:
                name = name + ' (' + rec.attribute_name + ')'
                if rec.is_smart_button and rec.node_option == 'button':
                    name = name + ' (Smart Button)'
            result.append((rec.id, name))
        return result

    @api.model_create_multi
    def create(self, vals_list):
        vals_2_create = []
        for values in vals_list:
            domain = [
                ('model_id', '=', values.get('model_id')),
                ('attribute_name', '=', values.get('attribute_name')),
                ('attribute_string', '=', values.get('attribute_string')),
                ('node_option', '=', values.get('node_option')),
                ('button_type', '=', values.get('button_type')),
            ]
            if not self.sudo().search(domain):
                vals_2_create.append(values)

        return super(IrUiViewNode, self).create(vals_2_create)
