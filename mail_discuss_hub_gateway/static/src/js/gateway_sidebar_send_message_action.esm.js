import {DiscussSidebarCategory} from "@mail/discuss/core/public_web/discuss_sidebar_categories";

import {_t} from "@web/core/l10n/translation";
import {patch} from "@web/core/utils/patch";

const GATEWAY_CATEGORY_PREFIX = "mail_gateway_instance_";

patch(DiscussSidebarCategory.prototype, {
    openGatewaySendMessageWizard(gatewayId) {
        const actionService = this.actionService || this.env.services.action;
        actionService.doAction({
            name: _t("Send message"),
            type: "ir.actions.act_window",
            res_model: "mail.gateway.send.message.wizard",
            view_mode: "form",
            views: [[false, "form"]],
            target: "new",
            context: {
                default_gateway_id: gatewayId,
            },
        });
    },
    get actions() {
        const actions = super.actions;
        const categoryId = this.category?.id;
        if (
            this.category?.open &&
            typeof categoryId === "string" &&
            categoryId.startsWith(GATEWAY_CATEGORY_PREFIX)
        ) {
            const gatewayId = parseInt(categoryId.slice(GATEWAY_CATEGORY_PREFIX.length), 10);
            if (gatewayId) {
                actions.push({
                    onSelect: () => this.openGatewaySendMessageWizard(gatewayId),
                    label: _t("Send message"),
                    icon: "fa fa-paper-plane",
                    class: "o-mail-DiscussSidebarCategory-sendGatewayMessage",
                });
            }
        }
        return actions;
    },
});

