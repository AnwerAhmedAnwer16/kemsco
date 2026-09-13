# models/project_task.py

from odoo import models, fields, api

class ProjectTask(models.Model):
    _inherit = 'project.task'

    report_type = fields.Selection(
        selection=[
            ('maintenance', 'Maintenance'),
            ('technical_report', 'Technical Report'),
        ],
        string="Report Type",
        help="Select the type of report to fill out for this task."
    )

    technical_checklist_ids = fields.One2many('checklist.line', 'task_id', string="Technical Checklist")
    maintenance_activity_ids = fields.One2many('maintenance.activity.line', 'task_id', string="Maintenance Activities")
    customer_signature = fields.Binary(string="Customer Signature", attachment=True, help="Customer signature for report approval.")

    purchase_order_ids = fields.One2many('purchase.order', 'task_id', string="Purchase Orders")
    purchase_order_count = fields.Integer(
        string="PO Count",
        compute='_compute_purchase_order_stats',
        store=True,
    )
    purchase_order_total = fields.Monetary(
        string="PO Total",
        compute='_compute_purchase_order_stats',
        currency_field='currency_id',
        store=True,
    )
    currency_id = fields.Many2one('res.currency', string="Currency", related='company_id.currency_id')

    @api.depends('purchase_order_ids.amount_total', 'purchase_order_ids.state')
    def _compute_purchase_order_stats(self):
        for task in self:
            orders = task.sudo().purchase_order_ids.filtered(lambda po: po.state != 'cancel')
            task.purchase_order_count = len(orders)
            task.purchase_order_total = sum(orders.mapped('amount_total'))

    def action_view_purchase_orders(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Purchase Orders',
            'res_model': 'purchase.order',
            'view_mode': 'tree,form',
            'domain': [('task_id', '=', self.id)],
            'context': {'default_task_id': self.id},
        }

    def action_create_purchase_order(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'New Purchase Order',
            'res_model': 'purchase.order',
            'view_mode': 'form',
            'target': 'current',
            'context': {'default_task_id': self.id},
        }

    def _report_attachments(self):
        """Attachments shown in the printed task report: the task's main
        attachments plus the ones coming from messages."""
        self.ensure_one()
        return self.message_ids.attachment_ids | self.attachment_ids

    def _report_video_attachments(self):
        """Video attachments of the report, ensuring each one has an access
        token so the printed links can be opened by users without an Odoo
        login (the bucket stays private)."""
        self.ensure_one()
        videos = self._report_attachments().filtered(
            lambda att: att.mimetype and att.mimetype.startswith('video/'))
        videos.sudo().generate_access_token()
        return videos

    @api.onchange('report_type')
    def _onchange_report_type(self):
        """Automatically populate the checklist when a report type is selected."""
        # Clear any existing lines first
        self.technical_checklist_ids = [(5, 0, 0)]
        self.maintenance_activity_ids = [(5, 0, 0)]

        if self.report_type == 'technical_report':
            # Define the static list of sections and their items
            sections = [
                ('FIRE FIGHTING SYS.', [
                    ('hose_reels', 'HOSE REELS SYS.'),
                    ('sprinklers', 'SPRINKLERS SYS.'),
                    ('dry_wet_riser', '(DRY & WET) RISER'),
                    ('main_pumps', 'MAIN PUMPS'),
                    ('jockey_pump', 'JOCKEY PUMP'),
                    ('extinguishers', 'FIRE EXTINGUISHERS'),
                ]),
                ('FIRE ALARM SYS.', [
                    ('alarm_panel', 'FIRE ALARM CONTROL PANEL'),
                    ('call_points', 'CALL POINTS'),
                    ('smoke_detectors', 'SMOKE DETECTORS'),
                    ('heat_detectors', 'HEAT DETECTORS'),
                    ('alarm_bells', 'ALARM BELLS'),
                ]),
                ('VENTILLATION SYS.', [
                    ('smoke_van', 'SMOKE VAN'),
                    ('fresh_air_van', 'FRESH AIR VAN'),
                ]),
                ('EMERG. LIGHTS SYS.', [
                    ('exit_light', 'EXIT LIGHT'),
                    ('emergency_light', 'EMERGENCY LIGHT'),
                ]),
            ]
            
            lines_to_create = []
            for section_name, items in sections:
                # 1. Add the section header line
                lines_to_create.append((0, 0, {
                    'display_type': 'line_section',
                    'name': section_name,
                }))
                # 2. Add the items under this section
                for item_key, item_name in items:
                    lines_to_create.append((0, 0, {
                        'description': item_key,
                    }))
            self.technical_checklist_ids = lines_to_create

        elif self.report_type == 'maintenance':
            # Define the static list of maintenance activities
            items = [
                ('oil_leakage', 'Check for any oil leakage'),
                ('coolant_level', 'Check coolant level'),
                ('oil_level', 'Check oil level'),
                ('fuel_level', 'Check fuel level'),
                ('fan_belt', 'Check fan belt tension'),
                ('water_pump', 'Check water pump for any leakage'),
                ('alternator_noise', 'Check alternator bearing noise'),
                ('battery_voltage', 'Check battery voltage'),
                ('battery_electrolyte', 'Check battery electrolyte level'),
                ('battery_terminal', 'Check battery terminal & clean'),
                ('electrical_connections', 'Check all electrical connections'),
                ('air_filter', 'Check air filter element'),
                ('engine_mounting', 'Check engine mounting bolts'),
                ('exhaust_system', 'Check exhaust system for leakage'),
                ('abnormal_noise', 'Run generator & check for abnormal noise'),
                ('voltage_frequency', 'Check voltage & frequency'),
                ('control_panel', 'Check control panel operation'),
                ('general_cleaning', 'General cleaning of generator'),
            ]
            
            # CORRECTED: Build a list of commands and assign it
            lines_to_create = []
            for item_key, item_name in items:
                lines_to_create.append((0, 0, {'activity_description': item_key}))
            self.maintenance_activity_ids = lines_to_create