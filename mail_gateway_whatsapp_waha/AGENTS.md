# AGENTS.md - mail_gateway_whatsapp_waha

## Leitura obrigatoria

- Leia `AGENTS.md` (raiz) e `README.rst` deste modulo antes de alterar.

## Objetivo

Gateway WhatsApp via WAHA.

## Dependencias

- `mail_gateway` (OCA).
- `mail_gateway_whatsapp_common` (DTO/servico compartilhado).

## Pontos importantes

- `token` e usado como API key da WAHA (header `X-Api-Key`).
- `waha_api_url` deve ser o base URL (sem barra final).
- `waha_session` default e `default` (WAHA Core suporta apenas esta sessao).
- Webhook inbound suporta `message`/`message.any` e `engine.event` com
  `payload.event=message_create` (texto).
- WAHA envia timestamps em epoch (segundos/ms); normalize para `datetime`
  no provider para evitar falhas no common.
- Eventos de webhook podem ser configurados no Settings do gateway, mas eventos fora
  de `message`/`message.any` e `engine.event(message_create)` ainda sao ignorados pelo provider.
- WAHA pode enviar `engine.event` com remetente em `@lid` (sem numero). Nesse caso,
  o telefone nao vem no payload; use API de contatos da WAHA para resolver o `lid`
  (ou aceite `@lid` como id externo).
- `webhook_secret` vira HMAC SHA-256 (`X-Webhook-Hmac`) nos webhooks.
- Common e o unico ponto de conexao com o Odoo; este modulo nao escreve no Odoo.
- Outbound e' roteado pelo common; este modulo so implementa `_send_outbound` (API externa).
- Anexos/medias ainda nao suportados no envio nem no inbound.
- Devtools e opcional e nunca deve ser dependencia de modulo algum.
- Fix generico para cache de `_get_gateway_map` fica no addon
  `mail_gateway_base`.
