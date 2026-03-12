/* @odoo-module */

import { threadActionsRegistry } from "@mail/core/common/thread_actions";
import { _t } from "@web/core/l10n/translation";

function canManageGatewayLLM(thread, component) {
    return Boolean(
        thread?.model === "discuss.channel" &&
            thread.channel_type === "gateway" &&
            thread.llm_assistant_id &&
            thread.llm_mode &&
            thread.llm_mode !== "off" &&
            (!component.props.chatWindow || component.props.chatWindow.isOpen)
    );
}

async function toggleLLMState(component, methodName, nextState, successMessage, errorMessage) {
    const thread = component.thread;
    try {
        const result = await component.env.services.orm.call(
            "discuss.channel",
            methodName,
            [[thread.id]]
        );
        thread.update({ llm_state: result?.llm_state || nextState });
        component.env.services.notification.add(successMessage, {
            type: "success",
        });
    } catch {
        component.env.services.notification.add(errorMessage, {
            type: "danger",
        });
    }
}

threadActionsRegistry
    .add("mail-gateway-llm-pause", {
        condition(component) {
            return canManageGatewayLLM(component.thread, component) && component.thread.llm_state !== "paused";
        },
        icon: "fa fa-fw fa-pause",
        iconLarge: "fa fa-fw fa-lg fa-pause",
        name: _t("Pausar IA"),
        sequence: 17,
        sequenceGroup: 20,
        async open(component) {
            await toggleLLMState(
                component,
                "action_pause_llm",
                "paused",
                _t("Auto-atendimento por IA pausado."),
                _t("Nao foi possivel pausar o auto-atendimento por IA.")
            );
        },
    })
    .add("mail-gateway-llm-resume", {
        condition(component) {
            return canManageGatewayLLM(component.thread, component) && component.thread.llm_state === "paused";
        },
        icon: "fa fa-fw fa-play",
        iconLarge: "fa fa-fw fa-lg fa-play",
        name: _t("Ativar IA"),
        sequence: 17,
        sequenceGroup: 20,
        async open(component) {
            await toggleLLMState(
                component,
                "action_resume_llm",
                "active",
                _t("Auto-atendimento por IA ativado."),
                _t("Nao foi possivel ativar o auto-atendimento por IA.")
            );
        },
    });
