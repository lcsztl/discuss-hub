import { Record } from "@mail/core/common/record";
import { Thread } from "@mail/core/common/thread_model";
import { DiscussAppCategory } from "@mail/core/public_web/discuss_app_category_model";
import { DiscussSidebarCategories } from "@mail/discuss/core/public_web/discuss_sidebar_categories";
import { cleanTerm } from "@mail/utils/common/format";
import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";

const discussHubSidebarFilterRegistry = registry.category("discuss_hub.sidebar_filters");

function isThreadArchived(thread) {
    return thread?.active === false;
}

function applyDiscussHubSidebarTagFilter(threads, activeTagIds) {
    if (!activeTagIds?.length) {
        return threads;
    }
    const tagSet = new Set(activeTagIds);
    return threads.filter((thread) => {
        const threadTagIds = thread?.discuss_hub_tag_ids;
        if (!threadTagIds) {
            return false;
        }
        if (Array.isArray(threadTagIds)) {
            return threadTagIds.some((id) => tagSet.has(id));
        }
        if (threadTagIds instanceof Set) {
            for (const id of threadTagIds) {
                if (tagSet.has(id)) {
                    return true;
                }
            }
            return false;
        }
        // Best-effort support for iterable values (unlikely, but keeps this resilient).
        if (typeof threadTagIds === "object" && Symbol.iterator in threadTagIds) {
            for (const id of threadTagIds) {
                if (tagSet.has(id)) {
                    return true;
                }
            }
            return false;
        }
        return false;
    });
}

function applyDiscussHubSidebarFilter(threads, activeFilter, activeTagIds) {
    const visibleThreads = threads.filter((thread) => !isThreadArchived(thread));
    let result = visibleThreads;
    if (activeFilter !== "all") {
        const providers = discussHubSidebarFilterRegistry.getAll();
        if (providers.length) {
            const filterKey = activeFilter === "unassigned" ? "isUnassigned" : "isMine";
            result = result.filter((thread) => {
                const matchingProviders = providers.filter(
                    (provider) => provider.appliesTo && provider.appliesTo(thread)
                );
                if (!matchingProviders.length) {
                    return true;
                }
                return matchingProviders.some((provider) => provider[filterKey]?.(thread));
            });
        }
    }
    return applyDiscussHubSidebarTagFilter(result, activeTagIds);
}

patch(Thread.prototype, {
    setup() {
        super.setup(...arguments);
        if (!("active" in this)) {
            this.active = Record.attr(true);
        }
        if (!("discuss_hub_tag_ids" in this)) {
            // Keep it as a primitive list of ids so the store doesn't require a
            // JS-side relational model definition.
            this.discuss_hub_tag_ids = Record.attr([]);
        }
    },
    _computeDiscussAppCategory() {
        if (this.active === false) {
            return;
        }
        return super._computeDiscussAppCategory(...arguments);
    },
});

patch(DiscussSidebarCategories.prototype, {
    filteredThreads(threads) {
        const activeFilter = this.store.discuss.discussHubSidebarFilter || "mine";
        const activeTagIds = this.store.discuss.discussHubSidebarTagIds || [];
        if (activeFilter === "mine") {
            const baseThreads = super.filteredThreads(threads);
            return applyDiscussHubSidebarFilter(baseThreads, activeFilter, activeTagIds);
        }
        const providers = discussHubSidebarFilterRegistry.getAll();
        const searchTerm = this.state.quickSearchVal
            ? cleanTerm(this.state.quickSearchVal)
            : "";
        const baseThreads = threads.filter((thread) => {
            const isProviderThread = providers.some(
                (provider) => provider.appliesTo && provider.appliesTo(thread)
            );
            if (!thread.displayInSidebar && !isProviderThread) {
                return false;
            }
            if (!thread.parent_channel_id && searchTerm) {
                return cleanTerm(thread.displayName).includes(searchTerm);
            }
            return true;
        });
        return applyDiscussHubSidebarFilter(baseThreads, activeFilter, activeTagIds);
    },
});

patch(DiscussAppCategory.prototype, {
    get isVisible() {
        if (this.hideWhenEmpty) {
            const hasVisibleThreads = this.threads.some(
                (thread) =>
                    !isThreadArchived(thread) &&
                    (thread.displayToSelf || thread.isLocallyPinned)
            );
            if (!hasVisibleThreads) {
                return false;
            }
        }
        const visible = super.isVisible;
        if (visible) {
            return visible;
        }
        const activeFilter = this.store.discuss.discussHubSidebarFilter || "mine";
        if (activeFilter === "mine") {
            return false;
        }
        const providers = discussHubSidebarFilterRegistry.getAll();
        return this.threads.some(
            (thread) =>
                !isThreadArchived(thread) &&
                providers.some((provider) => provider.appliesTo && provider.appliesTo(thread))
        );
    },
});
