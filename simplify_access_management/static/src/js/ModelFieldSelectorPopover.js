/** @odoo-module */

import { onWillRender } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { ModelFieldSelectorPopover } from "@web/core/model_field_selector/model_field_selector_popover";

patch(ModelFieldSelectorPopover.prototype, {

    setup() {
        super.setup(...arguments);
        let self = this;

        onWillRender(async () => {
            let result = await self.env.services.orm.silent.call(
                "access.management", "get_fields_2_hide", [ self.props.resModel ]);

            for (var idx=0; idx<self.state.page.fieldNames.length; idx++){
                if(result.includes(self.state.page.fieldNames[idx])){
                    self.state.page.fieldNames.splice(idx, 1);
                }
            }
        });
    }

});
