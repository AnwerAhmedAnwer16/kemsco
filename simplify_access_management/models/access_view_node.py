from odoo import api, fields, models, Command, _


class AccessViewNode(models.Model):
    _name = 'access.view.node'
    _description = 'Access View Node'

    access_management_id = fields.Many2one(comodel_name='access.management', string='Access Management')
    model_id = fields.Many2one(comodel_name='ir.model', string='Model', index=True, required=True, ondelete='cascade')

    ir_ui_view_btn_node_ids = fields.Many2many(
        comodel_name='ir.ui.view.node', relation='view_btn_access_node_rel',
        column1='btn_node_id', column2='access_node_id',
        string='Hide Button', domain="[('model_id','=',model_id), ('node_option', '=', 'button')]",
        help="The Buttons are added on list will be hidden in selected model from the defined users.")
    ir_ui_view_page_node_ids = fields.Many2many(
        comodel_name='ir.ui.view.node', relation='view_page_access_node_rel',
        column1='page_node_id', column2='access_node_id',
        string='Hide Tab/Page', domain="[('model_id','=',model_id), ('node_option', '=' ,'page')]",
        help="The Tabs (pages) are added on list will be hidden in selected model from the defined users.")
    ir_ui_view_link_node_ids = fields.Many2many(
        comodel_name='ir.ui.view.node', relation='view_link_access_node_rel',
        column1='link_node_id', column2='access_node_id',
        string='Hide Link', domain="[('model_id','=',model_id), ('node_option', '=' ,'link')]",
        help="The Links are added on list will be hidden in selected model from the defined users.")
    ir_ui_view_filter_node_ids = fields.Many2many(
        comodel_name='ir.ui.view.node', relation='view_filter_access_node_rel',
        column1='filter_node_id', column2='access_node_id',
        string='Hide Filters', domain="[('model_id','=',model_id), ('node_option', '=', 'filter')]",
        help="The filters are added on list will be hidden in search view of selected model from the specified users.")
    ir_ui_view_group_by_node_ids = fields.Many2many(
        comodel_name='ir.ui.view.node', relation='view_group_by_access_node_rel',
        column1='group_by_node_id', column2='access_node_id',
        string='Hide Group By', domain="[('model_id','=',model_id), ('node_option', '=', 'group_by')]",
        help="The Group By are added on list will be hidden in search view of selected model from the specified users.")

    def _get_smart_btn_string(self, btn):
        def _get_span_text(span_list):
            text = ''
            for sp in span_list:
                if sp.text:
                    text = text + ' ' + sp.text
            return text.strip()

        name = ''
        field_list = btn.findall('field')
        if field_list:
            name = field_list[0].get('string')
        else:
            span_list = btn.findall('span')
            if span_list:
                name = _get_span_text(span_list)
            else:
                div_list = btn.findall('div')
                if div_list:
                    span_list = div_list[0].findall('span')
                    if span_list:
                        name = _get_span_text(span_list)
        if not name:
            name = btn.get('string')

        return name

    @api.onchange('model_id')
    def _onchange_model_id(self):
        if self.model_id:
            self._prepare_model_view_node()

    def _prepare_model_view_node(self):
        view_node_2_create = []
        view_ids = self.env['ir.ui.view'].sudo().search([
            ('model', '=', self.model_id.model), ('type', 'in', ('form', 'tree', 'kanban', 'search'))])
        for view_id in view_ids:
            arch, view = self.env[self.model_id.model].sudo()._get_view(view_id.id, view_id.type)
            # Prepare btn node
            for btn_obj in arch.xpath("//button[@type='object']"):
                btn_obj_string = btn_obj.get('string')
                if view_id.type == 'kanban' and not btn_obj_string:
                    btn_obj_string = btn_obj.text if not btn_obj.text.startswith('\n') else False
                if btn_obj.get('name') and btn_obj_string:
                    node_vals = {
                        'model_id': self.model_id.id,
                        'node_option': 'button',
                        'attribute_name': btn_obj.get('name'),
                        'attribute_string': btn_obj_string,
                        'button_type': btn_obj.get('type'),
                        'is_smart_button': False
                    }
                    if node_vals not in view_node_2_create:
                        view_node_2_create.append(node_vals)
            for btn_act in arch.xpath("//button[@type='action']"):
                btn_act_string = btn_act.get('string')
                if view_id.type == 'kanban' and not btn_act_string:
                    btn_act_string = btn_act.text if not btn_act.text.startswith('\n') else False
                if btn_act.get('name') and btn_act_string:
                    btn_vals = {
                        'model_id': self.model_id.id,
                        'node_option': 'button',
                        'attribute_name': btn_act.get('name'),
                        'attribute_string': btn_act_string,
                        'button_type': btn_act.get('type'),
                        'is_smart_button': False
                    }
                    if btn_vals not in view_node_2_create:
                        view_node_2_create.append(btn_vals)
            if view_id.type == 'form':
                for btn_box in arch.xpath("//div[@class='oe_button_box']"):
                    for btn_box_obj in btn_box.xpath("//button[@type='object']"):
                        btn_box_obj_string = self._get_smart_btn_string(btn_box_obj)
                        if btn_box_obj.get('name') and btn_box_obj_string:
                            btn_box_vals = {
                                'model_id': self.model_id.id,
                                'node_option': 'button',
                                'attribute_name': btn_box_obj.get('name'),
                                'attribute_string': btn_box_obj_string,
                                'button_type': btn_box_obj.get('type'),
                                'is_smart_button': True
                            }
                            if btn_box_vals not in view_node_2_create:
                                view_node_2_create.append(btn_box_vals)
                    for btn_box_act in btn_box.xpath("//button[@type='action']"):
                        btn_box_act_string = self._get_smart_btn_string(btn_box_act)
                        if btn_box_act.get('name') and btn_box_act_string:
                            btn_act_vals = {
                                'model_id': self.model_id.id,
                                'node_option': 'button',
                                'attribute_name': btn_box_act.get('name'),
                                'attribute_string': btn_box_act_string,
                                'button_type': btn_box_act.get('type'),
                                'is_smart_button': True
                            }
                            if btn_act_vals not in view_node_2_create:
                                view_node_2_create.append(btn_act_vals)
            # Prepare page node
            for page in arch.xpath("//page"):
                if page.get('name') or page.get('string'):
                    page_vals = {
                        'model_id': self.model_id.id,
                        'node_option': 'page',
                        'attribute_name': page.get('name') or page.get('string'),
                        'attribute_string': page.get('string') or page.get('name')
                    }
                    if page_vals not in view_node_2_create:
                        view_node_2_create.append(page_vals)
            # Prepare link node
            for link in arch.xpath("//a"):
                if (link.text and '\n' not in link.text and 'type' in link.attrib.keys() and
                        link.attrib['type'] and 'name' in link.attrib.keys() and link.attrib['name']):
                    link_vals = {
                        'model_id': self.model_id.id,
                        'node_option': 'link',
                        'attribute_name': link.get('name') ,
                        'attribute_string': link.text,
                        'button_type': link.get('type')
                    }
                    if link_vals not in view_node_2_create:
                        view_node_2_create.append(link_vals)
            # Prepare filter node
            for filter in arch.xpath("//filter"):
                # Filters By records
                if filter.get('name') and filter.get('string') and not filter.get('context'):
                    filter_vals = {
                        'model_id': self.model_id.id,
                        'node_option': 'filter',
                        'attribute_name': filter.get('name'),
                        'attribute_string': filter.get('string')
                    }
                    if filter_vals not in view_node_2_create:
                        view_node_2_create.append(filter_vals)
            # Prepare group by node
            for group in arch.xpath("//group"):
                # Group By records
                for group_filter in group.xpath("//filter"):
                    if group_filter.get('name') and group_filter.get('string') and group_filter.get('context'):
                        group_vals = {
                            'model_id': self.model_id.id,
                            'node_option': 'group_by',
                            'attribute_name': filter.get('name'),
                            'attribute_string': filter.get('string')
                        }
                        if group_vals not in view_node_2_create:
                            view_node_2_create.append(group_vals)

        if view_node_2_create:
            self.env['ir.ui.view.node'].sudo().create(view_node_2_create)
