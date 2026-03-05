=================
Mail Gateway Base
=================

This module provides base technical components for gateway addons:

- Cache key fix for ``mail.gateway._get_gateway_map`` scoped by ``state`` and
  ``gateway_type``.
- ``Request.charset`` compatibility patch for Werkzeug 3.
- ``res.partner.gateway_phone`` canonical field.
- Reusable dispatch service: ``mail.gateway.dispatch.service``.
- Central text normalization for gateway messages (HTML/text -> plain text) with
  plain-body persistence in ``mail.message``.

Dependencies
============

- ``mail_gateway`` (OCA/social)
