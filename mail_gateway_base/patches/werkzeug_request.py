# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from werkzeug.wrappers import Request


def _ensure_request_charset():
    if hasattr(Request, "charset"):
        return

    @property
    def charset(self):
        return self.mimetype_params.get("charset") or "utf-8"

    Request.charset = charset


_ensure_request_charset()
