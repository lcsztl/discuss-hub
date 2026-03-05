===========================
Mail Gateway Account Notify
===========================

Purpose
=======

Add a new invoice sending method (``by Gateway``) to the standard
``account.move.send.wizard`` flow.

When selected, invoices are delivered through ``mail_gateway`` using the
shared service from ``mail_gateway_base``.

Dependencies
============

- ``account``
- ``mail_gateway_base``

Main behaviors
==============

- Adds ``mail_gateway`` option to ``res.partner.invoice_sending_method``.
- Adds gateway selector and destination fields on invoice send wizard.
- Reuses existing mail body/template and attachment widget.
- Sends gateway messages via ``mail.gateway.dispatch.service``.
