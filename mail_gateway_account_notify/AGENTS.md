# AGENTS.md - mail_gateway_account_notify

## Objective

Integrate invoice send flow (`account.move.send.wizard`) with `mail_gateway`
without duplicating gateway channel/send internals.

## Dependencies

- `account`
- `mail_gateway_base`

## Invariants

- Do not change default behavior for existing methods (`manual`, `email`, `snailmail`).
- Gateway delivery must use `mail.gateway.dispatch.service`.
- Destination priority remains `gateway_phone` -> `mobile` -> `phone`.

## Scope

- `models/res_partner.py`: adds sending method option.
- `models/account_move_send.py`: sending logic + alerts + applicability checks.
- `wizard/account_move_send_wizard.py`: gateway wizard fields/settings.
- `views/account_move_send_wizard_views.xml`: gateway UI on invoice send wizard.
