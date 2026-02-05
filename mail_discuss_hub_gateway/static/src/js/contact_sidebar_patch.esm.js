/* @odoo-module */

import { Discuss } from "@mail/core/public_web/discuss";
import { ChatWindow } from "@mail/core/common/chat_window";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { onWillUnmount } from "@odoo/owl";

function useContactSidebarOpen(component, getThread) {
    component.contactSidebar = useService("discuss_hub.contact_sidebar");
    const unregister = component.contactSidebar.register(() => {
        const selection = component.contactSidebar.state.selection;
        const thread = getThread();
        if (!selection || !thread) {
            return;
        }
        if (
            selection.threadId !== thread.id ||
            selection.threadModel !== thread.model
        ) {
            return;
        }
        const action = component.threadActions.actions.find(
            (entry) => entry.id === "gateway-contact-sidebar"
        );
        action?.onSelect({ keepPrevious: true });
    });
    onWillUnmount(() => unregister());
}

patch(Discuss.prototype, {
    setup() {
        super.setup();
        useContactSidebarOpen(this, () => this.thread);
    },
});

patch(ChatWindow.prototype, {
    setup() {
        super.setup();
        useContactSidebarOpen(this, () => this.thread);
    },
});
