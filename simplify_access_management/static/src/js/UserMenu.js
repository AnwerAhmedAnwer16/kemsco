/** @odoo-module **/

import { session } from "@web/session";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { UserMenu } from "@web/webclient/user_menu/user_menu";


patch(UserMenu.prototype, {
    setup() {
        super.setup(...arguments);
        this.hide_db_name = session.hide_db_name;
    }
})



