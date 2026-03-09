================
Mail Gateway LLM
================

Visão Geral
===========

Este módulo conecta conversas de gateway ao stack ``odoo-llm`` da Apexive.

Ele permite que cada ``mail.gateway`` use um ``llm.assistant`` para mensagens
recebidas, mantém um ``llm.thread`` dedicado por ``discuss.channel`` e
processa o trabalho da IA de forma assíncrona através de
``mail.gateway.llm.run``.

Principais Funcionalidades
==========================

- Configurar um ``LLM Mode`` por gateway: ``Off``, ``Suggest`` ou
  ``Auto Reply``.
- Vincular um gateway a um ``llm.assistant``.
- Criar e manter um ``llm.thread`` por canal de gateway.
- Espelhar mensagens inbound do cliente no ``llm.thread`` como contexto
  ``user``.
- Espelhar respostas humanas enviadas com sucesso no ``llm.thread`` como
  contexto ``assistant``.
- Gerar respostas da IA de forma assíncrona após o commit da transação.
- Publicar a resposta da IA no canal quando o modo estiver em
  ``Auto Reply``.
- Manter um log operacional em ``mail.gateway.llm.run`` com mensagem de
  origem, mensagem da IA, mensagem publicada, tentativas e erros.
- Permitir pausar as respostas automáticas por canal sem perder memória de
  conversa.

Dependências
============

Este módulo depende de:

- ``mail_gateway_base``
- ``llm_assistant``

Detalhes das Dependências
=========================

``mail_gateway_base``
    Fornece a base técnica do lado dos gateways usada por este módulo,
    incluindo a superfície de hooks e os serviços compartilhados de
    normalização de mensagens.

``llm_assistant``
    Fornece assistant, thread, prompt, provider, model e orquestração de
    tools usados para falar com o LLM.

O módulo ``llm_assistant`` vem do projeto ``odoo-llm`` da Apexive:

- Repositório: https://github.com/apexive/odoo-llm
- Link do módulo: https://github.com/apexive/odoo-llm/tree/main/llm_assistant

Configuração Inicial
====================

1. Instale ``mail_gateway_base``.
2. Instale o stack ``odoo-llm`` da Apexive, incluindo ao menos
   ``llm_assistant``.
3. Configure um provider e um model no ``odoo-llm``.
4. Crie um ``llm.assistant`` com prompt, provider, model e tools desejadas.
5. Abra o cadastro do ``mail.gateway``.
6. Defina o ``LLM Assistant``.
7. Escolha o ``LLM Mode``:

   - ``Off``: não executa IA.
   - ``Suggest``: gera resposta, mas não publica automaticamente.
   - ``Auto Reply``: gera e publica automaticamente no canal.

Como Funciona
=============

1. Uma mensagem de gateway chega ao ``discuss.channel``.
2. O gateway configurado enfileira um registro em ``mail.gateway.llm.run``.
3. O run é processado de forma assíncrona após o commit.
4. A mensagem de origem é espelhada para o ``llm.thread`` do canal.
5. O assistant gera a resposta usando provider, model, prompt e tools.
6. Em ``Suggest``, a resposta fica disponível para revisão.
7. Em ``Auto Reply``, a resposta é publicada no canal e o fluxo normal do
   gateway cuida da entrega externa.

Estrutura Técnica
=================

- ``discuss.channel`` continua sendo a conversa visível ao operador.
- ``llm.thread`` continua sendo a memória operacional e o contexto da IA.
- ``mail.gateway.llm.run`` continua sendo a fila durável e auditável do
  pipeline.

Isso evita executar o LLM inline no webhook e separa claramente:

- transporte da mensagem
- memória/contexto da IA
- estado operacional de execução

Uso de Desenvolvimento
======================

Se ``mail_discuss_hub_gateway_devtools`` também estiver instalado, é possível
inspecionar traces de request/response do LLM para análise de desenvolvimento.

Esse trace é útil para verificar:

- contexto enviado ao ``llm.thread``
- histórico usado no turno
- tools disponíveis
- resposta retornada pela IA

Notas Operacionais
==================

- ``mail.gateway.llm.run`` existe para manter o pipeline da IA durável,
  rastreável e com retry. A chamada ao LLM não é executada inline no webhook.
- A conversa visível permanece em ``discuss.channel``.
- A memória da IA e a execução de tools permanecem em ``llm.thread``.
- O módulo não depende de ``mail_discuss_hub`` para funcionar.
