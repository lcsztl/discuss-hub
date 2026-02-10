=============================================
Mail Gateway WhatsApp Evolution API Manager
=============================================

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

This module provides a lightweight manager for Evolution API servers and
instances, independent from the gateway connection. Settings changes on
instances are pushed to Evolution API using helpers from the gateway module.

**Table of contents**

.. contents::
   :local:

Overview
========

Main features:

- Register multiple Evolution API servers.
- Sync instances via ``/instance/fetchInstances``.
- View instance status, profile name, and phone number.
- Update Evolution settings (reject calls, ignore groups, always online, etc).

Dependencies
============

- ``mail_gateway_whatsapp_evolution_api`` (`lcsztl/discuss-hub <https://github.com/lcsztl/discuss-hub>`_)

Configuration
=============

Create an Evolution API server with:

- Base URL
- API Key

Usage
=====

Go to Settings > Discuss > Messages > EvolutionAPI Manager.
Use **Sync Instances** to refresh the instance list.

Roadmap (TODO)
==============

- Optional link to ``mail.gateway`` records.
- Instance settings management (reject calls, ignore groups, always online).
- QR code refresh and connection actions.

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
