/** @odoo-module */

const { onWillStart } = owl;
import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";

patch(FormController.prototype, {

    setup() {
        super.setup(...arguments);
        var self = this;
        self.action_to_remove = [];

        onWillStart(async () => {
            self.action_to_remove = await self.env.services.orm.silent.call(
                "access.management", "get_action_menu_2_hide", [ self.props.resModel ]);
        });
    },

    getStaticActionMenuItems(){
        var res = super.getStaticActionMenuItems();
        for (const [key, value] of Object.entries(res)) {
            if (this.action_to_remove.includes(value.description)) {
                delete res[key]
            }
        }
        return res
    }

});
