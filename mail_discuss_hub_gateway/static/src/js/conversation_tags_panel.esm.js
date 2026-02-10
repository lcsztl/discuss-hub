/* @odoo-module */

import { ActionPanel } from "@mail/discuss/core/common/action_panel";
import { Component, useEffect, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

export class ConversationTagsPanel extends Component {
    static components = { ActionPanel };
    static props = ["thread"];
    static template = "mail_discuss_hub_gateway.ConversationTagsPanel";

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            loading: false,
            saving: false,
            tags: [],
        });
        useEffect(
            () => {
                this.loadTags();
            },
            () => []
        );
    }

    get thread() {
        return this.props.thread;
    }

    get selectedTagIds() {
        const raw = this.thread?.discuss_hub_tag_ids;
        if (Array.isArray(raw)) {
            return raw;
        }
        if (raw instanceof Set) {
            return [...raw];
        }
        return [];
    }

    isSelected(tagId) {
        return this.selectedTagIds.includes(tagId);
    }

    async loadTags() {
        if (this.state.loading) {
            return;
        }
        this.state.loading = true;
        try {
            const tags = await this.orm.searchRead(
                "mail.discuss.hub.tag",
                [["active", "=", true]],
                ["name", "color"]
            );
            tags.sort((a, b) => (a.name || "").localeCompare(b.name || ""));
            this.state.tags = tags;
        } catch {
            this.state.tags = [];
        } finally {
            this.state.loading = false;
        }
    }

    async setTags(nextIds) {
        const thread = this.thread;
        if (!thread || this.state.saving) {
            return;
        }
        this.state.saving = true;
        try {
            const result = await this.orm.call(
                "discuss.channel",
                "action_discuss_hub_set_tags",
                [[thread.id], nextIds]
            );
            const ids = result?.discuss_hub_tag_ids ?? nextIds;
            thread.update({ discuss_hub_tag_ids: ids });
        } catch {
            this.notification.add(_t("Unable to update conversation tags."), {
                type: "danger",
            });
        } finally {
            this.state.saving = false;
        }
    }

    toggleTag(tagId) {
        const current = new Set(this.selectedTagIds);
        if (current.has(tagId)) {
            current.delete(tagId);
        } else {
            current.add(tagId);
        }
        return this.setTags([...current]);
    }

    clearTags() {
        return this.setTags([]);
    }

    manageTags() {
        return this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "mail.discuss.hub.tag",
            views: [[false, "list"], [false, "form"]],
            target: "current",
        });
    }
}

