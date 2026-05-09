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