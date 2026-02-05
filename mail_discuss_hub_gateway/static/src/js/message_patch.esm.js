/* @odoo-module */

import { Message } from "@mail/core/common/message";
import { markEventHandled } from "@web/core/utils/misc";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(Message.prototype, {
    _isGatewayGuestAuthor() {
        return (
            this.message.gateway_type &&
            this.message.author?.type === "guest" &&
            this.message.author.id
        );
    },
    _isGatewayPartnerAuthor() {
        return (
            this.message.gateway_type &&
            this.message.author?.type === "partner" &&
            this.message.author.id
        );
    },
    hasAuthorClickable() {
        return super.hasAuthorClickable() || this._isGatewayPartnerAuthor();
    },
    getAuthorText() {
        if (this._isGatewayGuestAuthor()) {
            return _t("Ver contato");
        }
        if (this._isGatewayPartnerAuthor() && !this.message.author?.userId) {
            return _t("Ver contato");
        }
        return super.getAuthorText();
    },
    onClickAuthor(ev) {
        if (this._isGatewayGuestAuthor()) {
            markEventHandled(ev, "Message.ClickAuthor");
            ev.stopPropagation();
            if (this._openGatewayContactSidebar()) {
                return true;
            }
            return this.env.services.action.doAction({
                name: _t("Manage guest"),
                type: "ir.actions.act_window",
                res_model: "mail.guest.manage",
                context: { default_guest_id: this.message.author.id },
                views: [[false, "form"]],
                target: "new",
            });
        }
        if (this._isGatewayPartnerAuthor() && !this.message.author?.userId) {
            markEventHandled(ev, "Message.ClickAuthor");
            if (this._openGatewayContactSidebar()) {
                return true;
            }
            return this.env.services.action.doAction({
                type: "ir.actions.act_window",
                res_model: "res.partner",
                res_id: this.message.author.id,
                views: [[false, "form"]],
                target: "current",
            });
        }
        return super.onClickAuthor(ev);
    },
    _openGatewayContactSidebar() {
        const contactSidebar = this.env.services["discuss_hub.contact_sidebar"];
        const thread = this.message.thread;
        if (!contactSidebar || !thread || !this.message.author?.id) {
            return false;
        }
        contactSidebar.open({
            threadId: thread.id,
            threadModel: thread.model,
            authorType: this.message.author.type,
            authorId: this.message.author.id,
        });
        return true;
    },
});
