==================================
Mail Discuss Hub Helpdesk Mgmt
==================================

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

This module provides Helpdesk Mgmt integration for Discuss Hub. The
current implementation focuses on linking Helpdesk teams to Discuss
teams as a foundation for future routing and assignment strategies.

**Table of contents**

.. contents::
   :local:

Overview
========

Currently adds a Discuss Team field on Helpdesk teams and keeps teams
synchronized between Helpdesk and Discuss. Additional Helpdesk
integration features are planned.

Dependencies
============

- ``mail_discuss_hub`` (`lcsztl/discuss-hub <https://github.com/lcsztl/discuss-hub>`_)
- ``helpdesk_mgmt`` (`OCA/helpdesk <https://github.com/OCA/helpdesk/tree/18.0/helpdesk_mgmt>`_)

Configuration
=============

No extra configuration is required.

Usage
=====

Open Helpdesk Team and set the "Discuss Team" field. Team changes are
synchronized between Helpdesk and Discuss. Other Helpdesk integration
features are under development.

Roadmap (TODO)
==============

- Auto-create tickets from gateway messages.
- Route new tickets based on Discuss Team rules.
- Extend routing rules based on ticket stages or categories.

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
