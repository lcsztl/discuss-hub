# AGENTS.md - mail_discuss_hub_crm

## Leitura obrigatoria

- Leia `AGENTS.md` (raiz) e `README.rst` deste modulo antes de alterar.

## Objetivo

- Sincronizar `mail.discuss.team` com `crm.team`.
- Permitir criar leads pelo Discuss via painel lateral.

## Dependencias

- `mail_discuss_hub`
- `crm`

## Arquivos principais

- `models/crm_team.py` (campo discuss_team_id + sync)
- `models/mail_discuss_team.py` (campo crm_team_id + sync)
- `models/discuss_channel.py` (vinculo de leads e criacao via painel)
- `models/crm_lead.py` (vinculo com sessões Discuss)
- `static/src/discuss/*` (painel OWL no Discuss)
- `views/crm_team_views.xml`

## Regras

- Sync deve ser bidirecional.
- Use context flags para evitar loop:
  - `mail_discuss_hub_sync_from_crm`
  - `mail_discuss_hub_sync_from_discuss`