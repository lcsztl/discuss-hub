import { Record } from "@mail/core/common/record";
import { discussSidebarItemsRegistry } from "@mail/core/public_web/discuss_sidebar";
import { DiscussApp } from "@mail/core/public_web/discuss_app_model";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { Component, useEffect, useState } from "@odoo/owl";

patch(DiscussApp.prototype, {
    setup(env) {
        super.setup(env);
        this.discussHubSidebarFilter = Record.attr("mine");
        // Client-side selection for the sidebar tags filter (list of tag ids).
        this.discussHubSidebarTagIds = Record.attr([]);
    },
});

export class DiscussHubSidebarFilters extends Component {
    static template = "mail_discuss_hub.DiscussHubSidebarFilters";

    setup() {
        this.store = useState(useService("mail.store"));
        this.orm = useService("orm");
        this.state = useState({
            tags: [],
            loadingTags: false,
        });
        this.filterRegistry = registry.category("discuss_hub.sidebar_filters");
        this.loadingFilters = new Set();
        this.labels = {
            mine: _t("Minhas"),
            unassigned: _t("Nao atribuidas"),
            all: _t("Todas"),
            tags: _t("Tags"),
            clear: _t("Limpar"),
        };
        if (!this.store.discuss.discussHubSidebarFilter) {
            this.store.discuss.update({ discussHubSidebarFilter: "mine" });
        }
        if (!this.store.discuss.discussHubSidebarTagIds) {
            this.store.discuss.update({ discussHubSidebarTagIds: [] });
        }
        useEffect(
            (activeFilter) => {
                this.loadAccessibleThreads(activeFilter);
            },
            () => [this.activeFilter]
        );
        useEffect(
            () => {
                this.loadTags();
            },
            () => []
        );
    }

    get activeFilter() {
        return this.store.discuss.discussHubSidebarFilter || "mine";
    }

    get activeTagIds() {
        return this.store.discuss.discussHubSidebarTagIds || [];
    }

    setFilter(value) {
        this.store.discuss.update({ discussHubSidebarFilter: value });
    }

    toggleTag(tagId) {
        const current = this.activeTagIds;
        const next = current.includes(tagId)
            ? current.filter((id) => id !== tagId)
            : [...current, tagId];
        this.store.discuss.update({ discussHubSidebarTagIds: next });
    }

    clearTags() {
        this.store.discuss.update({ discussHubSidebarTagIds: [] });
    }

    async loadTags() {
        if (this.state.loadingTags) {
            return;
        }
        this.state.loadingTags = true;
        try {
            const tags = await this.orm.searchRead(
                "mail.discuss.hub.tag",
                [["active", "=", true]],
                ["name", "color"]
            );
            tags.sort((a, b) => (a.name || "").localeCompare(b.name || ""));
            this.state.tags = tags;
        } catch {
            // Non-blocking: keep filters usable even if tags cannot be loaded.
            this.state.tags = [];
        } finally {
            this.state.loadingTags = false;
        }
    }

    async loadAccessibleThreads(activeFilter) {
        if (activeFilter === "mine") {
            return;
        }
        if (this.loadingFilters.has(activeFilter)) {
            return;
        }
        this.loadingFilters.add(activeFilter);
        try {
            const providers = this.filterRegistry.getAll();
            if (!providers.length) {
                return;
            }
            const knownChannelIds = Object.values(this.store.Thread.records)
                .filter((thread) => thread.model === "discuss.channel")
                .map((thread) => thread.id);
            await Promise.all(
                providers.map((provider) =>
                    provider.fetch?.({
                        activeFilter,
                        store: this.store,
                        knownChannelIds,
                        rpc,
                    })
                )
            );
        } finally {
            this.loadingFilters.delete(activeFilter);
        }
    }
}

discussSidebarItemsRegistry.add("discuss_hub_filters", DiscussHubSidebarFilters, { sequence: 25 });
