# AGENTS.md - mail_gateway_base

## Leitura obrigatoria

- Leia `AGENTS.md` (raiz) e `README.rst` deste modulo antes de alterar.

## Objetivo

Fornecer base tecnica para addons de gateway (patches e servicos comuns).

## Pontos importantes

- OCA `mail_gateway` usa `@tools.ormcache()` sem chave em `_get_gateway_map`.
  Este modulo adiciona chaves `state/gateway_type` para evitar cache cruzado e
  erro "Gateway was not found" quando existem multiplos gateways.
- Werkzeug 3 removeu `Request.charset`; `mail_gateway` usa esse atributo no
  controller de webhook e gerava 500. Este modulo aplica patch para repor
  `Request.charset` com fallback para `mimetype_params`/`utf-8`.
- Ownership de `res.partner.gateway_phone` fica neste modulo.
- Servico comum de envio gateway fica em `mail.gateway.dispatch.service`.
