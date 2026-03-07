# AGENTS.md - mail_gateway_whatsapp_common

## Leitura obrigatoria

- Leia `AGENTS.md` (raiz) e `README.rst` do modulo chamador quando houver.

## Objetivo

Servico comum para gateways WhatsApp (DTO, idempotencia e sync com Discuss).

## Pontos importantes

- `mail_gateway_whatsapp_common` e o unico ponto de conexao entre Odoo e providers de whatssapp nao oficial.
- Identidade de `mail.guest` e global por `gateway_phone`; nao usar
  `gateway_id`/`gateway_token` para identidade (podem existir varios gateways
  para o mesmo telefone).
