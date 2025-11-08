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

    @api.onchange('report_type')
    def _onchange_report_type(self):
        """Automatically populate the checklist when a report type is selected."""
        # Clear any existing lines first
        self.technical_checklist_ids = [(5, 0, 0)]
        self.maintenance_activity_ids = [(5, 0, 0)]

        if self.report_type == 'technical_report':
            # Define the static list of technical items
            items = [
                ('fire_fighting_sys', 'Fire Fighting System'),
                ('sprinklers_sys', 'Sprinklers System'),
                ('fire_pump', 'Fire Pump'),
                ('fire_alarm_sys', 'Fire Alarm System'),
                ('smoke_detectors', 'Smoke Detectors'),
                ('heat_detectors', 'Heat Detectors'),
                ('fire_extinguishers', 'Fire Extinguishers'),
                ('hose_reel_cabinet', 'Fire Hose Reel Cabinet'),
                ('emergency_lights', 'Emergency Lights'),
                ('fire_mantel_cabinet', 'Fire Mantel / Cabinet'),
            ]
            
            # CORRECTED: Build a list of commands and assign it
            lines_to_create = []
            for item_key, item_name in items:
                lines_to_create.append((0, 0, {'description': item_key}))
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