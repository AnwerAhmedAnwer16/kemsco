/** @odoo-module */

import { onWillStart } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { PivotGroupByMenu } from "@web/views/pivot/pivot_group_by_menu";

patch(PivotGroupByMenu.prototype, {

    setup() {
        super.setup(...arguments);
        var self = this;

//        onWillStart(async () => {
//            let result = await self.env.services.orm.silent.call(
//                "access.management", "get_fields_2_hide", [ self?.env?.searchModel?.resModel ]);
//
//            self.fields = self.fields.filter((ele) => !result.includes(ele.name));
//        });
    }

});
