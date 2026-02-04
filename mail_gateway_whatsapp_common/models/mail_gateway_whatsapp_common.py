import logging
import re

from odoo import models

from .common_attachments import MailGatewayWhatsappCommonAttachments
from .common_channel import MailGatewayWhatsappCommonChannel
from .common_contact import MailGatewayWhatsappCommonContact
from .common_inbound import MailGatewayWhatsappCommonInbound
from .common_outbound import MailGatewayWhatsappCommonOutbound
from .common_utils import MailGatewayWhatsappCommonUtils


class MailGatewayWhatsappCommon(models.AbstractModel):
    """Shared webhook processing for WhatsApp gateway providers.

    Providers normalize raw payloads into a DTO and call `_process_normalized`,
    which handles idempotency, guest resolution, channel creation, and posting.
    """

    _name = "mail.gateway.whatsapp.common"
    _description = "WhatsApp Gateway Common"
    _abstract = True
    _logger = logging.getLogger(__name__)
    _br_tag_re = re.compile(r"<br\s*/?>", re.IGNORECASE)


_COMMON_MIXINS = (
    MailGatewayWhatsappCommonInbound,
    MailGatewayWhatsappCommonOutbound,
    MailGatewayWhatsappCommonAttachments,
    MailGatewayWhatsappCommonContact,
    MailGatewayWhatsappCommonChannel,
    MailGatewayWhatsappCommonUtils,
)

for _mixin in _COMMON_MIXINS:
    for _name, _value in _mixin.__dict__.items():
        if not _name.startswith("_"):
            continue
        if isinstance(_value, (staticmethod, classmethod)):
            setattr(MailGatewayWhatsappCommon, _name, _value)
            continue
        if callable(_value):
            setattr(MailGatewayWhatsappCommon, _name, _value)
