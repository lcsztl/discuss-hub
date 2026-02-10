/* @odoo-module */

import { threadActionsRegistry } from "@mail/core/common/thread_actions";
import { GatewayTransferPanel } from "./gateway_transfer_panel.esm";
import { ContactSidebarPanel } from "./contact_sidebar_panel.esm";
import { ConversationTagsPanel } from "./conversation_tags_panel.esm";
import { _t } from "@web/core/l10n/translation";
import { usePopover } from "@web/core/popover/popover_hook";
import { useComponent } from "@odoo/owl";

threadActionsRegistry
    .add("join-channel", {
        condition(component) {
            const thread = component.thread;
            return (
                thread?.model === "discuss.channel" &&
                thread.channel_type === "gateway" &&
                !thread.selfMember &&
                (!component.props.chatWindow || component.props.chatWindow.isOpen)
            );
        },
        icon: "fa fa-fw fa-sign-in",
        iconLarge: "fa fa-fw fa-lg fa-sign-in",
        name: _t("Join Channel"),
        sequence: 11,
        sequenceGroup: 20,
        async open(component) {
            const thread = component.thread;
            try {
                await component.store.joinChannel(thread.id, thread.name);
            } catch {
                component.env.services.notification.add(_t("Unable to join channel."), {
                    type: "danger",
                });
            }
        },
    })
    .add("transfer-channel", {
        condition(component) {
            const thread = component.thread;
            return (
                thread?.model === "discuss.channel" &&
                thread.channel_type === "gateway" &&
                thread.selfMember &&
                (!component.props.chatWindow || component.props.chatWindow.isOpen)
            );
        },
        icon: "fa fa-fw fa-share-square-o",
        iconLarge: "fa fa-fw fa-lg fa-share-square-o",
        name: _t("Transferir"),
        component: GatewayTransferPanel,
        componentProps(action, component) {
            return { thread: component.thread, close: () => action.close() };
        },
        panelOuterClass(component) {
            return `o-discuss-ChannelInvitation ${
                component.props.chatWindow ? "bg-inherit" : ""
            } bg-100 border border-secondary`;
        },
        setup(action) {
            const component = useComponent();
            if (!component.props.chatWindow) {
                action.popover = usePopover(GatewayTransferPanel, {
                    onClose: () => action.close(),
                    popoverClass: action.panelOuterClass,
                });
            }
        },
        open(component, action) {
            action.popover?.open(component.root.el.querySelector(`[name="${action.id}"]`), {
                hasSizeConstraints: true,
                thread: component.thread,
            });
        },
        close(component, action) {
            action.popover?.close();
        },
        sequence: 12,
        sequenceGroup: 20,
        toggle: true,
    })
    .add("gateway-contact-sidebar", {
        condition(component) {
            const thread = component.thread;
            return (
                thread?.model === "discuss.channel" &&
                thread.channel_type === "gateway" &&
                (!component.props.chatWindow || component.props.chatWindow.isOpen)
            );
        },
        component: ContactSidebarPanel,
        componentProps(action, component) {
            return { thread: component.thread };
        },
        icon: "fa fa-fw fa-address-card-o",
        iconLarge: "fa fa-fw fa-lg fa-address-card-o",
        name: _t("Contato"),
        panelOuterClass: "o-discuss-ContactSidebar bg-inherit",
        sequence: 15,
        sequenceGroup: 20,
        toggle: true,
    })
    .add("gateway-conversation-tags", {
        condition(component) {
            const thread = component.thread;
            return (
                thread?.model === "discuss.channel" &&
                thread.channel_type === "gateway" &&
                (!component.props.chatWindow || component.props.chatWindow.isOpen)
            );
        },
        component: ConversationTagsPanel,
        componentProps(action, component) {
            return { thread: component.thread };
        },
        icon: "fa fa-fw fa-tags",
        iconLarge: "fa fa-fw fa-lg fa-tags",
        name: _t("Tags"),
        panelOuterClass: "o-discuss-ConversationTags bg-inherit",
        sequence: 16,
        sequenceGroup: 20,
        toggle: true,
    })
    .add("leave-channel", {
        condition(component) {
            const thread = component.thread;
            return (
                thread?.model === "discuss.channel" &&
                thread.channel_type === "gateway" &&
                thread.selfMember &&
                (!component.props.chatWindow || component.props.chatWindow.isOpen)
            );
        },
        icon: "fa fa-fw fa-sign-out",
        iconLarge: "fa fa-fw fa-lg fa-sign-out",
        name: _t("Leave Channel"),
        sequence: 13,
        sequenceGroup: 20,
        async open(component) {
            try {
                await component.thread.leave();
            } catch {
                component.env.services.notification.add(_t("Unable to leave channel."), {
                    type: "danger",
                });
            }
        },
    })
    .add("resolve-channel", {
        condition(component) {
            const thread = component.thread;
            return (
                thread?.model === "discuss.channel" &&
                thread.channel_type === "gateway" &&
                thread.selfMember &&
                (!component.props.chatWindow || component.props.chatWindow.isOpen)
            );
        },
        icon: "fa fa-fw fa-check-square-o",
        iconLarge: "fa fa-fw fa-lg fa-check-square-o",
        name: _t("Resolver/Arquivar"),
        sequence: 14,
        sequenceGroup: 20,
        async open(component) {
            const thread = component.thread;
            try {
                await component.env.services.orm.call("discuss.channel", "action_archive", [[thread.id]]);
                if ("active" in thread) {
                    thread.active = false;
                }
                if (component.props?.chatWindow) {
                    component.props.chatWindow.close();
                } else if (component.store?.inbox) {
                    component.store.inbox.setAsDiscussThread();
                }
            } catch {
                component.env.services.notification.add(_t("Unable to archive channel."), {
                    type: "danger",
                });
            }
        },
    });
