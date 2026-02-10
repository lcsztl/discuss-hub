import {DiscussApp} from "@mail/core/public_web/discuss_app_model";
import {Record} from "@mail/core/common/record";

import {_t} from "@web/core/l10n/translation";
import {patch} from "@web/core/utils/patch";

patch(DiscussApp.prototype, {
    setup(env) {
        super.setup(env);
        // mail_gateway adds a "Gateway" sidebar category with canAdd=true, which
        // shows a "Search Gateway Channel" input. In Discuss Hub we disable this
        // entrypoint because it is not usable in our flow.
        this.gateway = Record.one("DiscussAppCategory", {
            compute() {
                return {
                    extraClass: "o-mail-DiscussSidebarCategory-gateway",
                    id: "gateway",
                    name: _t("Gateway"),
                    isOpen: false,
                    canView: false,
                    canAdd: false,
                    serverStateKey: "is_discuss_sidebar_category_gateway_open",
                };
            },
        });
    },
});

