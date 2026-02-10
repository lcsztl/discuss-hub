Discuss Hub Addons
==================

Repositorio de addons do Discuss Hub.

Dependencias externas (OCA/social)
==================================

Este repositorio nao inclui os modulos abaixo. Para usar os gateways, baixe o
repo oficial OCA/social (branch 18.0) e adicione ao addons_path do Odoo (ou
copie apenas estes modulos):

- mail_gateway: https://github.com/OCA/social/tree/18.0/mail_gateway
- mail_gateway_whatsapp: https://github.com/OCA/social/tree/18.0/mail_gateway_whatsapp
- mail_gateway_telegram: https://github.com/OCA/social/tree/18.0/mail_gateway_telegram

Docker Compose
==================
Este repositorio segue o padrao OCA (somente addons).

Para um ambiente pronto via Docker Compose (build do Odoo + dependencias + meta
addon para instalar tudo), use o projeto ``discuss-hub-env``.
