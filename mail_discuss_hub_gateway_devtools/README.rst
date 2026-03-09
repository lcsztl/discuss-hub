mail_discuss_hub_gateway_devtools
=================================

Ferramentas tecnicas opcionais para apoiar desenvolvimento e testes do Discuss Hub.
Quando instalado, habilita logging de webhooks, visualizacao detalhada e wizards
de suporte; fora dele, os gateways continuam processando webhooks sem persistir.

Principais funcionalidades
--------------------------

- Menus de administracao em Discuss > Messages:
  - Messages
  - Scheduled Messages
  - Subtypes
  - Message Reactions
  - User Settings
  - Teams
  - Guests
  - Channels
  - Channels/Members
- Modelo generico ``mail.gateway.webhook.log`` para armazenar request/response,
  status e metadados do webhook.
- Campos em ``mail.message`` para vincular a log de webhook e exibir payloads.
- Views/lista/form para logs, menu "Discuss Dev" (apenas admins) e aba "Webhook"
  no form de mensagens.
- Wizards (placeholder) para replay de webhooks e cleanup rapido de dados
  durante testes controlados.
- Script utilitario ``scripts/replay_webhook_logs.py`` para reprocessar logs via
  ``odoo-bin shell`` configurando filtros por variaveis de ambiente.
- Recursos de tracing de LLM ficam em um addon opcional separado,
  ``mail_discuss_hub_gateway_devtools_llm``.

Uso
---

- Instale apenas em ambientes de desenvolvimento/QA quando quiser inspecionar
  webhooks; em producao pode ficar desinstalado sem impacto no processamento.
- Nao deve ser dependencia de nenhum outro modulo; tudo precisa funcionar sem ele.
- Acesso aos menus apenas para ``base.group_system``.
- Os wizards estao protegidos com mensagens de placeholder para evitar uso
  acidental; revise antes de habilitar em ambientes compartilhados.
