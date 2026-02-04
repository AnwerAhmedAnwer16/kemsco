/* @odoo-module */

import { onWillRender } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { FormRenderer } from "@web/views/form/form_renderer";

patch(FormRenderer.prototype, {

    setup() {
        super.setup(...arguments);
        let self = this;
        self.orm = useService("orm");

        onWillRender(async () => {
            let result = await self.orm.call(
                "access.management", "get_chatter_buttons_2_hide", [ self.props.record.model.config.resModel ]);

            if (result['hide_send_mail']){
                var btn1 = setInterval(function() {
                    if ($('.o-mail-Chatter-sendMessage').length) {
                        $('.o-mail-Chatter-sendMessage').remove();
                        clearInterval(btn1);
                    }
                }, 50);
            }
            if (result['hide_log_notes']){
                var btn2 = setInterval(function() {
                    if ($('.o-mail-Chatter-logNote').length) {
                        $('.o-mail-Chatter-logNote').remove();
                        clearInterval(btn2);
                    }
                }, 50);
            }
            if (result['hide_schedule_activity']){
                var btn3 = setInterval(function() {
                    if ($('.o-mail-Chatter-activity').length) {
                        $('.o-mail-Chatter-activity').remove();
                        clearInterval(btn3);
                    }
                }, 50);
            }

        })
    }

})
