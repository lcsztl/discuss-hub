/* @odoo-module */

import { ChannelMemberList } from "@mail/discuss/core/common/channel_member_list";
import { markEventHandled } from "@web/core/utils/misc";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(ChannelMemberList.prototype, {
    onClickAvatar(ev, member) {
        if (this._openGatewayMemberContact(ev, member)) {
            return;
        }
        return super.onClickAvatar(ev, member);
    },
    _openGatewayMemberContact(ev, member) {
        const thread = this.props.thread;
        const persona = member?.persona;
        if (thread?.channel_type !== "gateway" || !persona?.id) {
            return false;
        }
        if (persona.type === "guest") {
            markEventHandled(ev, "ChannelMemberList.ClickAvatar");
            ev.stopPropagation();
            const contactSidebar = this.env.services["discuss_hub.contact_sidebar"];
            if (contactSidebar) {
                contactSidebar.open({
                    threadId: thread.id,
                    threadModel: thread.model,
                    authorType: persona.type,
                    authorId: persona.id,
                });
                return true;
            }
            return this.env.services.action.doAction({
                name: _t("Manage guest"),
                type: "ir.actions.act_window",
                res_model: "mail.guest.manage",
                context: { default_guest_id: persona.id },
                views: [[false, "form"]],
                target: "new",
            });
        }
        if (persona.type === "partner" && !persona.userId) {
            markEventHandled(ev, "ChannelMemberList.ClickAvatar");
            ev.stopPropagation();
            const contactSidebar = this.env.services["discuss_hub.contact_sidebar"];
            if (contactSidebar) {
                contactSidebar.open({
                    threadId: thread.id,
                    threadModel: thread.model,
                    authorType: persona.type,
                    authorId: persona.id,
                });
                return true;
            }
            this.env.services.action.doAction({
                type: "ir.actions.act_window",
                res_model: "res.partner",
                res_id: persona.id,
                views: [[false, "form"]],
                target: "current",
            });
            return true;
        }
        return false;
    },
});
