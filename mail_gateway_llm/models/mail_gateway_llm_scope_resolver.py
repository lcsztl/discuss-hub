# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models


class MailGatewayLLMScopeResolver(models.AbstractModel):
    _name = "mail.gateway.llm.scope.resolver"
    _description = "Mail Gateway LLM Scope Resolver"

    def resolve_from_context(self):
        identity = self.env["mail.gateway.llm.identity.resolver"].resolve_from_context()
        return self.compute(identity)

    def compute(self, identity):
        identity = dict(identity or {})
        partner = self._resolved_partner(identity)
        if not partner:
            return self._empty_scope(identity)

        commercial_partner = partner.commercial_partner_id.sudo().exists() or partner
        binding = self._find_binding(identity, partner, commercial_partner)
        principal_partner = self._principal_partner(binding, partner, commercial_partner)
        related_partners = self._related_partners(partner, principal_partner)

        scope = dict(identity)
        scope.update(
            {
                "resolved_partner_id": partner.id,
                "resolved_partner": partner,
                "partner_id": partner.id,
                "partner": partner,
                "principal_partner_id": principal_partner.id if principal_partner else False,
                "principal_partner": principal_partner,
                "commercial_partner_id": commercial_partner.id if commercial_partner else False,
                "commercial_partner": commercial_partner,
                "related_partner_ids": related_partners.ids,
                "related_partners": related_partners,
                "binding_id": binding.id if binding else False,
                "binding": binding or self.env["mail.gateway.llm.access.binding"],
                "verification_mode": binding.verification_mode if binding else "phone_only",
                "allow_sensitive_data": self._allow_sensitive_data(
                    identity.get("confidence"),
                    binding,
                ),
                "scope_mode": "binding" if binding else "automatic",
            }
        )
        return scope

    def _empty_scope(self, identity):
        scope = dict(identity or {})
        scope.update(
            {
                "principal_partner_id": False,
                "principal_partner": self.env["res.partner"],
                "commercial_partner_id": False,
                "commercial_partner": self.env["res.partner"],
                "related_partner_ids": [],
                "related_partners": self.env["res.partner"],
                "binding_id": False,
                "binding": self.env["mail.gateway.llm.access.binding"],
                "verification_mode": False,
                "allow_sensitive_data": False,
                "scope_mode": "empty",
            }
        )
        return scope

    def _resolved_partner(self, identity):
        partner = identity.get("resolved_partner") or identity.get("partner")
        if not partner:
            return self.env["res.partner"]
        return partner.sudo().exists()

    def _principal_partner(self, binding, partner, commercial_partner):
        if binding:
            principal_partner = binding.principal_partner_id.sudo().exists()
            if principal_partner:
                return principal_partner
        if commercial_partner and commercial_partner != partner:
            return commercial_partner
        return partner

    def _related_partners(self, partner, principal_partner):
        partners = self.env["res.partner"]
        if partner:
            partners |= partner.sudo().exists()
        if principal_partner:
            partners |= principal_partner.sudo().exists()
        return partners

    def _find_binding(self, identity, partner, commercial_partner):
        candidate_partner_ids = [partner.id]
        if commercial_partner and commercial_partner != partner:
            candidate_partner_ids.append(commercial_partner.id)

        bindings = self.env["mail.gateway.llm.access.binding"].sudo().search(
            [
                ("active", "=", True),
                ("principal_partner_id", "in", candidate_partner_ids),
            ]
        )
        gateway_id = identity.get("gateway_id")
        company_id = identity.get("company_id")
        if gateway_id:
            bindings = bindings.filtered(
                lambda binding: not binding.gateway_id or binding.gateway_id.id == gateway_id
            )
        else:
            bindings = bindings.filtered(lambda binding: not binding.gateway_id)
        if company_id:
            bindings = bindings.filtered(
                lambda binding: not binding.company_id or binding.company_id.id == company_id
            )
        else:
            bindings = bindings.filtered(lambda binding: not binding.company_id)

        if not bindings:
            return self.env["mail.gateway.llm.access.binding"]

        return bindings.sorted(
            key=lambda binding: (
                2 if binding.principal_partner_id.id == partner.id else 1,
                1 if gateway_id and binding.gateway_id.id == gateway_id else 0,
                1 if company_id and binding.company_id.id == company_id else 0,
                binding.id,
            ),
            reverse=True,
        )[:1]

    def _allow_sensitive_data(self, confidence, binding):
        if confidence in ("none", "low"):
            return False
        if confidence == "medium":
            return bool(binding and binding.allow_sensitive_data)
        if confidence == "high":
            return False if binding and not binding.allow_sensitive_data else True
        return False
