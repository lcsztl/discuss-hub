import {DiscussAppCategory} from "@mail/core/public_web/discuss_app_category_model";
import {Thread} from "@mail/core/common/thread_model";
import {
    DiscussSidebarCategories,
    DiscussSidebarChannel,
} from "@mail/discuss/core/public_web/discuss_sidebar_categories";
import {assignIn, compareDatetime} from "@mail/utils/common/misc";
import {_t} from "@web/core/l10n/translation";
import {rpc} from "@web/core/network/rpc";
import {useService} from "@web/core/utils/hooks";
import {patch} from "@web/core/utils/patch";

const GATEWAY_CATEGORY_PREFIX = "mail_gateway_instance_";
const GATEWAY_CATEGORY_SEQUENCE = 24;

function getGatewayInfo(thread) {
    const gateway = thread.gateway;
    const rawGateway = thread.gateway_id;
    const rawGatewayId =
        rawGateway && typeof rawGateway === "object" ? rawGateway.id : rawGateway;
    const gatewayId = gateway?.id || rawGatewayId;
    if (!gatewayId) {
        return null;
    }
    const gatewayName =
        gateway?.name ||
        (rawGateway && typeof rawGateway === "object" ? rawGateway.name : undefined) ||
        thread.gateway_name;
    return { id: gatewayId, name: gatewayName };
}

function ensureGatewayCategory(store, gatewayInfo) {
    if (!store || !store.DiscussAppCategory || !gatewayInfo?.id) {
        return null;
    }
    const normalizedId = Number.parseInt(gatewayInfo.id, 10);
    if (!normalizedId) {
        return null;
    }
    const categoryId = `${GATEWAY_CATEGORY_PREFIX}${normalizedId}`;
    let category = store.DiscussAppCategory.get({id: categoryId});
    const fallbackName = gatewayInfo.name || _t("Gateway");
    if (!category) {
        category = store.DiscussAppCategory.insert({
            id: categoryId,
            app: store.discuss,
            name: fallbackName,
            extraClass: "o-mail-DiscussSidebarCategory-gateway",
            hideWhenEmpty: false,
            canView: false,
            canAdd: false,
            sequence: GATEWAY_CATEGORY_SEQUENCE,
        });
    } else if (gatewayInfo.name && category.name !== gatewayInfo.name) {
        category.update({name: gatewayInfo.name});
    }
    return category;
}

function getGatewayCategory(thread) {
    const gatewayInfo = getGatewayInfo(thread);
    if (!gatewayInfo) {
        return null;
    }
    const store = thread.store;
    if (!store || !store.DiscussAppCategory) {
        return null;
    }
    return ensureGatewayCategory(store, gatewayInfo);
}

async function loadGatewayCategories(store) {
    if (!store?.DiscussAppCategory || store.discuss?._gatewaySidebarLoaded) {
        return;
    }
    store.discuss._gatewaySidebarLoaded = true;
    try {
        const gateways = await rpc("/discuss_hub/gateway/sidebar", {});
        if (!Array.isArray(gateways)) {
            return;
        }
        for (const gatewayInfo of gateways) {
            ensureGatewayCategory(store, gatewayInfo);
        }
    } catch {
        if (store.discuss) {
            store.discuss._gatewaySidebarLoaded = false;
        }
    }
}

function requestGatewayCategoryCompute(thread) {
    // Touch the computed relational field so lazy-compute evaluates (and inverse
    // lists get updated) without calling low-level requestCompute() with proxies.
    void thread?.discussAppCategory;
}

patch(Thread, {
    _insert(data) {
        const thread = super._insert(...arguments);
        if (data && thread.channel_type === "gateway") {
            assignIn(thread, data, ["anonymous_name", "gateway"]);
        }
        if (thread.channel_type === "gateway") {
            requestGatewayCategoryCompute(thread);
        }
        return thread;
    },
});

patch(DiscussSidebarCategories.prototype, {
    setup() {
        super.setup(...arguments);
        Promise.resolve().then(() => loadGatewayCategories(this.store));
    },
});

patch(Thread.prototype, {
    update(data) {
        super.update(data);
        if (data && this.channel_type === "gateway") {
            assignIn(this, data, ["anonymous_name", "gateway"]);
        }
        if (
            data &&
            ("gateway" in data || "gateway_id" in data || "channel_type" in data || "active" in data)
        ) {
            if (this.channel_type === "gateway") {
                requestGatewayCategoryCompute(this);
            }
        }
    },
    _computeDiscussAppCategory() {
        if (this.active === false) {
            return;
        }
        if (this.channel_type === "gateway") {
            return (
                getGatewayCategory(this) ||
                this.store?.discuss?.gateway ||
                super._computeDiscussAppCategory(...arguments)
            );
        }
        return super._computeDiscussAppCategory(...arguments);
    },
});

const DiscussSidebarChannelPatch = {
    setup() {
        super.setup();
        this.actionService = useService("action");
    },
    get commands() {
        const commands = super.commands;
        if (this.thread.channel_type === "gateway") {
            commands.push({
                onSelect: () => this.openGatewayChannelSettings(),
                label: _t("Channel settings"),
                icon: "fa fa-cog",
                sequence: 10,
            });
        }
        return commands;
    },
    openGatewayChannelSettings() {
        if (this.thread.channel_type !== "gateway") {
            return;
        }
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "discuss.channel",
            res_id: this.thread.id,
            views: [[false, "form"]],
            target: "current",
        });
    },
};

patch(DiscussAppCategory.prototype, {
    get isVisible() {
        if (this.id === "gateway") {
            return this.threads.some((thread) => thread.displayToSelf || thread.isLocallyPinned);
        }
        return super.isVisible;
    },
    sortThreads(t1, t2) {
        const categoryId = this.id;
        if (
            categoryId === "gateway" ||
            (typeof categoryId === "string" && categoryId.startsWith(GATEWAY_CATEGORY_PREFIX))
        ) {
            return compareDatetime(t2.lastInterestDt, t1.lastInterestDt) || t2.id - t1.id;
        }
        return super.sortThreads(t1, t2);
    },
});

patch(DiscussSidebarChannel.prototype, DiscussSidebarChannelPatch);
