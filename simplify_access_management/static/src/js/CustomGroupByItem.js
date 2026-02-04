/** @odoo-module */

import { onWillStart } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { CustomGroupByItem } from "@web/search/custom_group_by_item/custom_group_by_item";

patch(CustomGroupByItem.prototype, {

    setup() {
        super.setup(...arguments);
        var self = this;

        onWillStart(async () => {
            let result = await self.env.services.orm.silent.call(
                "access.management", "get_fields_2_hide", [ self?.env?.searchModel?.resModel ]);

            self.props.fields = self.props.fields.filter((ele) => !result.includes(ele.name))
        });
    }

});
