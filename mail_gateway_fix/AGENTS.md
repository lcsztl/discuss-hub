# AGENTS.md - mail_gateway_fix

## Leitura obrigatoria

- Leia `AGENTS.md` (raiz) e `README.rst` deste modulo antes de alterar.

## Objetivo

Corrigir o cache do lookup de gateways em `mail.gateway`.

## Pontos importantes

- OCA `mail_gateway` usa `@tools.ormcache()` sem chave em `_get_gateway_map`.
  Este modulo adiciona chaves `state/gateway_type` para evitar cache cruzado e
  erro "Gateway was not found" quando existem multiplos gateways.
- Werkzeug 3 removeu `Request.charset`; `mail_gateway` usa esse atributo no
  controller de webhook e gerava 500. Este modulo aplica patch para repor
  `Request.charset` com fallback para `mimetype_params`/`utf-8`.
