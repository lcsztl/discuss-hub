/* @odoo-module */

import { reactive } from "@odoo/owl";
import { registry } from "@web/core/registry";

export const contactSidebarService = {
    start() {
        const state = reactive({
            selection: null,
            requestId: 0,
        });
        const openers = new Set();
        return {
            state,
            register(opener) {
                openers.add(opener);
                return () => openers.delete(opener);
            },
            open(selection) {
                state.selection = selection;
                state.requestId += 1;
                for (const opener of openers) {
                    opener();
                }
            },
            clear() {
                state.selection = null;
                state.requestId += 1;
            },
        };
    },
};

registry.category("services").add("discuss_hub.contact_sidebar", contactSidebarService);
