=====================
Mail Discuss Hub CRM
=====================

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

This module provides CRM integration for Discuss Hub. The current
implementation focuses on linking CRM teams to Discuss teams as a
foundation for future routing and assignment strategies.

**Table of contents**

.. contents::
   :local:

Overview
========

Currently adds a Discuss Team field on CRM Teams and keeps teams
synchronized between CRM and Discuss. Additional CRM integration
features are planned.
Adds a Discuss side panel for creating CRM leads from a channel and
keeps a lightweight link between leads and Discuss sessions.

Dependencies
============

- ``mail_discuss_hub`` (`lcsztl/discuss-hub <https://github.com/lcsztl/discuss-hub>`_)
- ``crm`` (`Odoo CRM <https://github.com/odoo/odoo/tree/18.0/addons/crm>`_)

Configuration
=============

No extra configuration is required.

Usage
=====

Open CRM Team and set the "Discuss Team" field. Team changes are
synchronized between CRM and Discuss. Other CRM integration features
are under development.

Inside Discuss, use the "Lead" side panel to create a CRM lead from the
current channel. The lead keeps a link to the Discuss session for quick
navigation later.

Roadmap (TODO)
==============

- Auto-assign leads/opportunities to Discuss Teams.
- Extend routing rules based on CRM stages or tags.
- Define routing rules based on CRM stages or tags.

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
