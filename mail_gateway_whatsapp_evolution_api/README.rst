===================================
Mail Gateway WhatsApp Evolution API
===================================

.. |badge1| image:: https://img.shields.io/badge/maturity-Beta-yellow.png
    :target: https://odoo-community.org/page/development-status
    :alt: Beta
.. |badge2| image:: https://img.shields.io/badge/license-AGPL--3-blue.png
    :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
    :alt: License: AGPL-3
.. |badge3| image:: https://img.shields.io/badge/github-lcsztl%2Fdiscuss-hub-lightgray.png?logo=github
    :target: https://github.com/lcsztl/discuss-hub
    :alt: lcsztl/discuss-hub

|badge1| |badge2| |badge3|

This module integrates Odoo Mail Gateway with Evolution API to send and
receive WhatsApp messages.

**Table of contents**

.. contents::
   :local:

Overview
========

Features:

- Configure Evolution API URL, token, and instance name.
- Integrate, update, or remove webhooks from Odoo.
- Receive inbound messages and attachments via webhook.
- Send outbound messages and media from Discuss.
- Inbound/outbound flows are routed through ``mail_gateway_whatsapp_common``;
  this module only adapts Evolution API payloads.

Dependencies
============

- ``mail_gateway`` (`OCA/social mail_gateway <https://github.com/OCA/social/tree/18.0/mail_gateway>`_)
- ``mail_gateway_whatsapp_common`` (serviço/DTO compartilhado para processar mensagens/status/reactions)

Configuration
=============

1. Open Settings > Discuss > Messages > Gateway.
2. Create a gateway with type "WhatsApp (Evolution API)".
3. Fill Evolution API URL, token, and instance (if needed).
4. Set webhook events/base64 as needed and click "Integrate Webhook".

.. note::
   **Important:** This module requires a single database per Odoo URL.
   The ``db_name`` parameter must be set in your ``odoo.conf`` file.
   Multi-database setups with ``?db=`` in the webhook URL are not supported
   because Evolution API does not preserve query parameters in callbacks.

Usage
=====

Use Discuss to send messages. Inbound webhooks are parsed into a
``NormalizedPayload`` and processados pelo módulo
``mail_gateway_whatsapp_common`` (idempotência, status, reações). Se
``mail_discuss_hub_gateway_devtools`` estiver instalado, você pode inspecionar
logs no menu Discuss Dev. O devtools e opcional e nunca pode ser dependencia
de nenhum modulo.

Group metadata enrichment
=========================

For group chats, the provider only calls the Evolution API to fetch group
details when the webhook payload does not include ``subject/desc/picture`` and
the local channel is still incomplete (fallback name, name equal to sender,
missing description, or missing avatar). The external fetch is only triggered
on ``message.upsert`` events.

Roadmap (TODO)
==============

- Support more webhook events and message statuses.
- Improve group chat handling and naming conventions.
- Cache group/contact metadata enrichment to reduce repeated API calls.
- Add retry handling and delivery diagnostics.

Bug Tracker
===========

Bugs are tracked on `GitHub Issues <https://github.com/lcsztl/discuss-hub/issues>`_.
In case of trouble, please check there if your issue has already been reported.

Credits
=======

Authors
-------

* Soloz Techonologies <lucas.zotelli@soloz.com.br>

Maintainers
-----------

This module is maintained by Lucas Zotelli.

This module is part of the `lcsztl/discuss-hub <https://github.com/lcsztl/discuss-hub>`_
project on GitHub.
