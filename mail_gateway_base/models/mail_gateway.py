# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import api, models, tools

_logger = logging.getLogger(__name__)


class MailGateway(models.Model):
    _inherit = "mail.gateway"

    @api.model
    @tools.ormcache("state", "gateway_type")
    def _get_gateway_map(self, state="integrated", gateway_type=False):
        result = {}
        for record in self.sudo().search(
            [
                ("integrated_webhook_state", "=", state),
                ("gateway_type", "=", gateway_type),
            ]
        ):
            result[record.webhook_key] = record._get_gateway_data()
        return result

    def _after_gateway_message_received(
        self,
        channel,
        message,
        *,
        author=None,
        payload=None,
    ):
        """Extension point for persisted inbound gateway messages."""

    def _dispatch_after_gateway_message_received(
        self,
        channel,
        message,
        *,
        author=None,
        payload=None,
    ):
        self.ensure_one()
        try:
            return self._after_gateway_message_received(
                channel,
                message,
                author=author,
                payload=payload,
            )
        except Exception:
            _logger.exception(
                "Gateway inbound hook failed for gateway %s and message %s.",
                self.id,
                message.id if message else None,
            )
        return False

    def _after_gateway_outbound_sent(
        self,
        notification,
        *,
        message=None,
        channel=None,
        result=None,
    ):
        """Extension point for successful outbound gateway sends."""

    def _dispatch_after_gateway_outbound_sent(
        self,
        notification,
        *,
        message=None,
        channel=None,
        result=None,
    ):
        self.ensure_one()
        try:
            return self._after_gateway_outbound_sent(
                notification,
                message=message,
                channel=channel,
                result=result,
            )
        except Exception:
            _logger.exception(
                "Gateway outbound hook failed for gateway %s and notification %s.",
                self.id,
                notification.id if notification else None,
            )
        return False
