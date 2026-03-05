# AGENTS.md - mail_discuss_hub_gateway

## Leitura obrigatoria

- Leia `AGENTS.md` (raiz) e `README.rst` deste modulo antes de alterar.

## Objetivo

Integrações Discuss + mail_gateway (UI e regras comuns de canais gateway).

## Dependencias

- `mail_gateway`
- `mail_gateway_base`
- `mail_discuss_hub`

## Arquivos principais

- `static/src/js/gateway_instance_sidebar.esm.js`
- `static/src/js/message_patch.esm.js` (corrige click do autor em mensagens gateway)
- `models/discuss_channel.py` (propaga time do gateway para o canal)
- `models/mail_gateway.py` (campo discuss_team_id no gateway)
- `models/mail_gateway_abstract.py` (cria canal sem membros em massa)
- `views/mail_gateway_views.xml` (campo do time no form do gateway)
- `static/src/js/thread_actions.esm.js` (acao placeholder no Discuss para canal gateway)

## Regras

- Nao alterar OCA diretamente.
- Manter o modulo focado em regras genericas de gateway.
- Canais gateway nao devem adicionar membros automaticamente (apenas autor/guest).
- Canais gateway devem herdar `group_public_id` do time para controle de acesso.
- Greenfield: sem hooks de backfill.
- Merge de visitante -> parceiro nao depende de `mail.guest.gateway_id`; usa `gateway_phone`
  e deriva gateways pelos canais do visitante.
- Ao fazer merge, enviar Store das mensagens para atualizar o autor no Discuss sem refresh.
- TODO: Avaliar constraint em `discuss.channel.member` para bloquear usuarios internos fora do `group_public_id` em canais gateway, considerando bypass para guests/autores e promocao de visitante -> contato.
