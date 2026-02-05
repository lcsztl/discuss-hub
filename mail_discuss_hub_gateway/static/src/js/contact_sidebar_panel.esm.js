/* @odoo-module */

import { ActionPanel } from "@mail/discuss/core/common/action_panel";
import { Component, useEffect, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

export class ContactSidebarPanel extends Component {
    static components = { ActionPanel };
    static props = ["thread"];
    static template = "mail_discuss_hub_gateway.ContactSidebarPanel";

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.contactSidebar = useService("discuss_hub.contact_sidebar");
        this.state = useState({
            loading: false,
            guest: null,
            partner: null,
        });
        useEffect(
            () => {
                this._loadSelection();
            },
            () => [this.contactSidebar.state.requestId]
        );
    }

    get selection() {
        return this.contactSidebar.state.selection;
    }

    get hasSelection() {
        const selection = this.selection;
        const thread = this.props.thread;
        return (
            !!selection &&
            !!thread &&
            selection.threadId === thread.id &&
            selection.threadModel === thread.model
        );
    }

    get showGuestActions() {
        return this.state.guest && !this.state.partner;
    }

    async _loadSelection() {
        if (!this.hasSelection) {
            this.state.guest = null;
            this.state.partner = null;
            return;
        }
        const selection = this.selection;
        this.state.loading = true;
        try {
            let data = null;
            if (selection.authorType === "guest") {
                data = await this.orm.call(
                    "mail.guest",
                    "action_get_discuss_hub_contact_panel_data",
                    [[selection.authorId]]
                );
            } else if (selection.authorType === "partner") {
                data = await this.orm.call(
                    "res.partner",
                    "action_get_discuss_hub_contact_panel_data",
                    [[selection.authorId]]
                );
            }
            this.state.guest = data?.guest || null;
            this.state.partner = data?.partner || null;
        } catch (error) {
            this.notification.add(_t("Unable to load contact details."), {
                type: "danger",
            });
        } finally {
            this.state.loading = false;
        }
    }

    async createPartner() {
        if (!this.state.guest) {
            return;
        }
        try {
            const action = await this.orm.call(
                "mail.guest",
                "action_create_partner",
                [[this.state.guest.id]]
            );
            if (action) {
                this.actionService.doAction(action);
            }
            if (this.selection) {
                this.contactSidebar.open({ ...this.selection });
            }
        } catch {
            this.notification.add(_t("Unable to create contact."), {
                type: "danger",
            });
        }
    }

    linkPartner() {
        if (!this.state.guest) {
            return;
        }
        return this.actionService.doAction({
            name: _t("Manage guest"),
            type: "ir.actions.act_window",
            res_model: "mail.guest.manage",
            context: { default_guest_id: this.state.guest.id },
            views: [[false, "form"]],
            target: "new",
        });
    }

    openPartner() {
        if (!this.state.partner) {
            return;
        }
        return this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "res.partner",
            res_id: this.state.partner.id,
            views: [[false, "form"]],
            target: "current",
        });
    }
}
