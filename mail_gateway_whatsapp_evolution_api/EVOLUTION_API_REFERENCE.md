# Evolution API Reference (Local)

This file is generated from the public Evolution API docs (v1/v2) and smoke-tested against the local server.

## Environment
- Base URL: https://evolutionapi.soloz.com.br
- Auth: `apikey` header (value redacted in this document).
- Test instances: `solozenergiaadm` (normal), `codex_test_instance` (used for high-risk endpoints).
- Test timestamp: 2026-01-15T00:10:07.542186Z

## Test Methodology
- `GET`/`DELETE`: no body
- `POST`/`PUT`/`PATCH`: empty JSON `{}`
- High-risk endpoints (instance restart/logout/delete/connect, webhook/set, settings/set) were tested with a non-existent instance to avoid side effects.
- Methods and payloads were also cross-checked against local server routes/schemas and reference modules (see below).

## Maintenance Rule (Agent)
If any divergence is found between this guide, public docs, reference modules, or server behavior, re-check with at least one other source (server routes, reference modules, or live tests) and update this file.

## Sources Confronted
- Local server routes: `/tmp/evolution-api/src/api/routes/*.router.ts` (v2.3.7)
- Local server schemas: `/tmp/evolution-api/src/validate/*.schema.ts`
- Local webhook schema: `/tmp/evolution-api/src/api/integrations/event/webhook/webhook.schema.ts`
- Reference modules (payloads):
  - `extra-addons-reference/odoo-whatsapp-evolution-api/whatsapp_evolution_base/models/evolution_api.py`
  - `extra-addons-reference/odoo-whatsapp-evolution-api/whatsapp_evolution_base/models/whatsapp_instance.py`
  - `extra-addons-reference/wa_conn/models/wa_account.py`
  - `extra-addons-reference/wa_conn_apps/wa_conn_evolution/models/wa_account_evolution.py`
  - `extra-addons/discuss-hub/mail_gateway_whatsapp_evolution_api/models/mail_gateway_whatsapp_evolution_api.py`
  - `extra-addons/discuss-hub/mail_gateway_whatsapp_evolution_api/models/evolution_api_client.py`

## Doc vs Server Method Corrections (v2.3.7)
| Doc Method | Path | Server Method | Evidence |
| --- | --- | --- | --- |
| `PUT` | `/instance/restart/{instance}` | `POST` | `/tmp/evolution-api/src/api/routes/instance.router.ts` |
| `GET` | `/chat/findChats/{instance}` | `POST` | `/tmp/evolution-api/src/api/routes/chat.router.ts` |
| `PUT` | `/chat/archiveChat/{instance}` | `POST` | `/tmp/evolution-api/src/api/routes/chat.router.ts` |
| `PUT` | `/chat/markMessageAsRead/{instance}` | `POST` | `/tmp/evolution-api/src/api/routes/chat.router.ts` |
| `PUT` | `/chat/updateMessage/{instance}` | `POST` | `/tmp/evolution-api/src/api/routes/chat.router.ts` |
| `PUT` | `/chat/removeProfilePicture/{instance}` | `DELETE` | `/tmp/evolution-api/src/api/routes/chat.router.ts` |
| `PUT` | `/chat/updatePrivacySettings/{instance}` | `POST` | `/tmp/evolution-api/src/api/routes/chat.router.ts` |
| `PUT` | `/chat/updateProfilePicture/{instance}` | `POST` | `/tmp/evolution-api/src/api/routes/chat.router.ts` |
| `PUT` | `/group/revokeInviteCode/{instance}` | `POST` | `/tmp/evolution-api/src/api/routes/group.router.ts` |
| `PUT` | `/group/toggleEphemeral/{instance}` | `POST` | `/tmp/evolution-api/src/api/routes/group.router.ts` |
| `PUT` | `/group/updateGroupDescription/{instance}` | `POST` | `/tmp/evolution-api/src/api/routes/group.router.ts` |
| `PUT` | `/group/updateGroupPicture/{instance}` | `POST` | `/tmp/evolution-api/src/api/routes/group.router.ts` |
| `PUT` | `/group/updateGroupSubject/{instance}` | `POST` | `/tmp/evolution-api/src/api/routes/group.router.ts` |
| `PUT` | `/group/updateParticipant/{instance}` | `POST` | `/tmp/evolution-api/src/api/routes/group.router.ts` |
| `PUT` | `/group/updateSetting/{instance}` | `POST` | `/tmp/evolution-api/src/api/routes/group.router.ts` |

Notes:
- Some reference modules still call `PUT /instance/restart/{instance}` (e.g. `extra-addons-reference/wa_conn/models/wa_account.py`); server expects `POST`.

## Reference Payloads and Examples
The payloads below are extracted from reference modules and aligned with local server schemas.

### POST /instance/create
Required (reference modules): `instanceName`, `integration`.
Common optional fields: `qrcode`, `rejectCall`, `msgCall`, `groupsIgnore`, `alwaysOnline`, `readMessages`, `readStatus`, `syncFullHistory`.
Optional webhook block (preferred by our gateway and server): `webhook.enabled`, `webhook.url`, `webhook.byEvents`, `webhook.base64`, `webhook.events`, `webhook.headers`.

Example:
```bash
curl -X POST "$BASE_URL/instance/create" \
  -H "apikey: $API_KEY" -H "Content-Type: application/json" \
  -d '{
    "instanceName": "demo_instance",
    "integration": "WHATSAPP-BAILEYS",
    "qrcode": true,
    "rejectCall": false,
    "groupsIgnore": false,
    "alwaysOnline": false,
    "readMessages": true,
    "readStatus": false,
    "syncFullHistory": false,
    "webhook": {
      "enabled": true,
      "url": "https://odoo.example.com/gateway/whatsapp_evolution_api/<uuid>/update",
      "byEvents": true,
      "base64": false,
      "events": ["MESSAGES_UPSERT", "CONNECTION_UPDATE"],
      "headers": { "webhook_key": "secret" }
    }
  }'
```

Notes:
- Some reference modules use `webhookByEvents` inside the nested webhook or top-level `webhookByEvents` fields.
  The server schema expects nested `webhook.byEvents` (see `webhook.schema.ts`).

### POST /settings/set/{instance}
Required (server schema + reference mixin): `rejectCall`, `groupsIgnore`, `alwaysOnline`, `readMessages`, `readStatus`, `syncFullHistory`.
Optional: `msgCall`, `wavoipToken`.

Example:
```bash
curl -X POST "$BASE_URL/settings/set/$INSTANCE" \
  -H "apikey: $API_KEY" -H "Content-Type: application/json" \
  -d '{
    "rejectCall": false,
    "groupsIgnore": false,
    "alwaysOnline": false,
    "readMessages": true,
    "readStatus": false,
    "syncFullHistory": false
  }'
```

### POST /webhook/set/{instance}
Required (server schema + reference modules): `webhook.enabled`, `webhook.url`.
Common optional fields: `webhook.byEvents`, `webhook.base64`, `webhook.events`, `webhook.headers`.

Example:
```bash
curl -X POST "$BASE_URL/webhook/set/$INSTANCE" \
  -H "apikey: $API_KEY" -H "Content-Type: application/json" \
  -d '{
    "webhook": {
      "enabled": true,
      "url": "https://odoo.example.com/gateway/whatsapp_evolution_api/<uuid>/update",
      "byEvents": true,
      "base64": false,
      "events": ["MESSAGES_UPSERT", "CONNECTION_UPDATE"],
      "headers": { "webhook_key": "secret" }
    }
  }'
```

### POST /message/sendText/{instance}
Required (reference modules): `number`, `text`.
Optional: `quoted` (see reply example in `wa_account_evolution.py`).

Example:
```bash
curl -X POST "$BASE_URL/message/sendText/$INSTANCE" \
  -H "apikey: $API_KEY" -H "Content-Type: application/json" \
  -d '{ "number": "5511999999999", "text": "Hello" }'
```

### POST /message/sendMedia/{instance}
Required (reference modules): `number`, `mediatype`, `media`.
Common optional fields: `mimetype`, `fileName`, `caption`.

Example:
```bash
curl -X POST "$BASE_URL/message/sendMedia/$INSTANCE" \
  -H "apikey: $API_KEY" -H "Content-Type: application/json" \
  -d '{
    "number": "5511999999999",
    "mediatype": "image",
    "mimetype": "image/png",
    "media": "<base64>",
    "fileName": "image.png",
    "caption": "Hello"
  }'
```

### POST /message/sendWhatsAppAudio/{instance}
Required (reference modules): `number`, `audio`.

Example:
```bash
curl -X POST "$BASE_URL/message/sendWhatsAppAudio/$INSTANCE" \
  -H "apikey: $API_KEY" -H "Content-Type: application/json" \
  -d '{ "number": "5511999999999", "audio": "<base64>" }'
```

### POST /message/sendSticker/{instance}
Required (reference modules): `number`, `sticker`.

Example:
```bash
curl -X POST "$BASE_URL/message/sendSticker/$INSTANCE" \
  -H "apikey: $API_KEY" -H "Content-Type: application/json" \
  -d '{ "number": "5511999999999", "sticker": "<base64>" }'
```

### POST /message/sendReaction/{instance}
Required (reference modules): `key.remoteJid`, `key.id`, `key.fromMe`, `reaction`.

Example:
```bash
curl -X POST "$BASE_URL/message/sendReaction/$INSTANCE" \
  -H "apikey: $API_KEY" -H "Content-Type: application/json" \
  -d '{
    "key": { "remoteJid": "5511999999999@s.whatsapp.net", "id": "ABCD1234", "fromMe": true },
    "reaction": "👍"
  }'
```

### POST /chat/fetchProfilePictureUrl/{instance}
Required (reference modules): `number`.

Example:
```bash
curl -X POST "$BASE_URL/chat/fetchProfilePictureUrl/$INSTANCE" \
  -H "apikey: $API_KEY" -H "Content-Type: application/json" \
  -d '{ "number": "+5511999999999" }'
```

### POST /chat/whatsappNumbers/{instance}
Required (reference modules): `numbers` (array of strings).

Example:
```bash
curl -X POST "$BASE_URL/chat/whatsappNumbers/$INSTANCE" \
  -H "apikey: $API_KEY" -H "Content-Type: application/json" \
  -d '{ "numbers": ["+5511999999999", "+5511888888888"] }'
```

### Instance lifecycle (no body)
Endpoints used by reference modules: `/instance/connect/{instance}`, `/instance/connectionState/{instance}`, `/instance/restart/{instance}`, `/instance/logout/{instance}`, `/instance/delete/{instance}`.

Example:
```bash
curl -X POST "$BASE_URL/instance/restart/$INSTANCE" -H "apikey: $API_KEY"
```

### Other endpoints
If an endpoint is present in the public docs but not used by the reference modules above,
there is no reliable payload reference here. Validate with server schemas or live tests and update this file.

## Server Schema Payloads (v2.3.7)
These payloads come directly from the local server schemas. They represent the strict validation rules.

### Messages (POST /message/*/{instance})
| Endpoint | Required fields (schema) | Notes |
| --- | --- | --- |
| `/message/sendText` | `number`, `text` | Optional: `quoted`, `mentioned`, `everyOne`, `linkPreview`, `delay`. |
| `/message/sendMedia` | `number`, `mediatype` | Optional: `media`, `mimetype`, `fileName`, `caption`, `quoted`. |
| `/message/sendPtv` | `number` | Optional: `video`, `quoted`. |
| `/message/sendWhatsAppAudio` | `number` | Optional: `audio`, `quoted`. |
| `/message/sendStatus` | `type` | Optional: `content`, `caption`, `backgroundColor`, `font`, `statusJidList`, `allContacts`. |
| `/message/sendSticker` | `number` | Optional: `sticker`, `quoted`. |
| `/message/sendLocation` | `number`, `latitude`, `longitude`, `name`, `address` |  |
| `/message/sendContact` | `number`, `contact[]` | `contact[]` items require `fullName`, `phoneNumber`. |
| `/message/sendReaction` | `key.id`, `key.remoteJid`, `key.fromMe`, `reaction` |  |
| `/message/sendPoll` | `number`, `name`, `selectableCount`, `values[]` | `values[]` min 2. |
| `/message/sendList` | `number`, `title`, `footerText`, `buttonText`, `sections[]` | `sections[].rows[]` require `title`, `rowId`. |
| `/message/sendButtons` | `number` | Buttons array is expected; schema only requires `number`. |
| `/message/sendTemplate` | `name`, `language` | `number` is present in schema but not required. |

### Chat (POST /chat/*/{instance})
| Endpoint | Required fields (schema) | Notes |
| --- | --- | --- |
| `/chat/whatsappNumbers` | none required | `numbers[]` min 1 is expected. |
| `/chat/markMessageAsRead` | `readMessages[]` | Each item: `id`, `fromMe`, `remoteJid`. |
| `/chat/archiveChat` | `archive` | `lastMessage.key` required if provided. |
| `/chat/markChatUnread` | `lastMessage` | `lastMessage.key` required. |
| `/chat/deleteMessageForEveryone` | `id`, `fromMe`, `remoteJid` | `participant` optional. |
| `/chat/fetchProfilePictureUrl` | none required | `number` expected. |
| `/chat/updateMessage` | none required | `number`, `text`, `key` are validated if present. |
| `/chat/sendPresence` | `number`, `presence`, `delay` |  |
| `/chat/updateBlockStatus` | `number`, `status` | `status` = `block` or `unblock`. |
| `/chat/findContacts` | none required | Uses `where` object. |
| `/chat/findMessages` | none required | Uses `where` object. |
| `/chat/findStatusMessage` | none required | Uses `where` object. |
| `/chat/getBase64FromMediaMessage` | `message` | Payload: `{"message": {"key": {...}, "message": {...}}}`. Returns `base64`, `mimetype`, `fileName`. |
| `/chat/findChats` | none required | Uses `where` object. |
| `/chat/fetchBusinessProfile` | none required | Accepts `number` or profile fields. |
| `/chat/fetchProfile` | none required | Accepts `wuid`, `name`, `picture`, `status`, `isBusiness`. |
| `/chat/updateProfileName` | `name` |  |
| `/chat/updateProfileStatus` | `status` |  |
| `/chat/updateProfilePicture` | none required | Accepts `number`, `picture`. |
| `/chat/removeProfilePicture` | no body |  |
| `/chat/fetchPrivacySettings` | no body |  |
| `/chat/updatePrivacySettings` | `readreceipts`, `profile`, `status`, `online`, `last`, `groupadd` |  |

### Groups (GET/POST /group/*/{instance})
| Endpoint | Required fields (schema) | Notes |
| --- | --- | --- |
| `POST /group/create` | `subject`, `participants[]` | `participants[]` numeric strings. |
| `GET /group/findGroupInfos` | `groupJid` | `groupJid` pattern `@g.us`. |
| `GET /group/participants` | `groupJid` |  |
| `GET /group/inviteCode` | `groupJid` |  |
| `GET /group/inviteInfo` | `inviteCode` |  |
| `GET /group/acceptInviteCode` | `inviteCode` |  |
| `POST /group/sendInvite` | `groupJid`, `description`, `numbers[]` |  |
| `POST /group/revokeInviteCode` | `groupJid` |  |
| `POST /group/updateParticipant` | `groupJid`, `action`, `participants[]` | `action` = add/remove/promote/demote. |
| `POST /group/updateSetting` | `groupJid`, `action` | `action` = announcement/not_announcement/locked/unlocked. |
| `POST /group/toggleEphemeral` | `groupJid`, `expiration` | `expiration` enum: 0, 86400, 604800, 7776000. |
| `POST /group/updateGroupPicture` | `groupJid`, `image` |  |
| `POST /group/updateGroupSubject` | `groupJid`, `subject` |  |
| `POST /group/updateGroupDescription` | `groupJid`, `description` |  |
| `DELETE /group/leaveGroup` | no body | Server validates `groupJid` if present. |

## Test Summary
- Unique method/path tested: 134
- Status counts: 200: 23, 201: 2, 400: 69, 401: 1, 404: 29, 500: 10

### 401 Unauthorized
- `POST /instance/create`

### 500 Server Error
- `DELETE /evolutionBot/delete/:evolutionBotId/{instance}`
- `DELETE /openai/creds/:openaiCredsId/{instance}`
- `DELETE /openai/delete/:openaiBotId/{instance}`
- `GET /chat/fetchPrivacySettings/{instance}`
- `POST /chat/fetchProfilePictureUrl/{instance}`
- `POST /chat/updateMessage/{instance}`
- `POST /chat/updateProfileName/{instance}`
- `POST /chat/updateProfilePicture/{instance}`
- `POST /chat/updateProfileStatus/{instance}`
- `POST /websocket/set/{instance}`

### 404 Not Found (likely doc mismatch / method mismatch)
- `GET /chat/findChats/{instance}`
- `GET /dify/find/:difyId/{instance}`
- `GET /flowise/find/:flowiseId/{instance}`
- `GET /openai/find/:openaiBotId/{instance}`
- `POST /flowise/update/:flowiseId/{instance}`
- `POST /message/updateBlockStatus/{instance}`
- `POST /typebot/set/{instance}`
- `POST /typebot/update/:typebotId/{instance}`
- `PUT /chat/archiveChat/{instance}`
- `PUT /chat/markMessageAsRead/{instance}`
- `PUT /chat/removeProfilePicture/{instance}`
- `PUT /chat/updateMessage/{instance}`
- `PUT /chat/updatePrivacySettings/{instance}`
- `PUT /chat/updateProfilePicture/{instance}`
- `PUT /group/revokeInviteCode/{instance}`
- `PUT /group/toggleEphemeral/{instance}`
- `PUT /group/updateGroupDescription/{instance}`
- `PUT /group/updateGroupPicture/{instance}`
- `PUT /group/updateGroupSubject/{instance}`
- `PUT /group/updateParticipant/{instance}`
- `PUT /group/updateSetting/{instance}`
- `PUT /instance/restart/{instance}`

### 404 Not Found (expected: instance missing)
- `DELETE /instance/delete/{instance}`
- `DELETE /instance/logout/{instance}`
- `GET /instance/connect/{instance}`
- `GET /instance/connectionState/{instance}`
- `POST /instance/setPresence/{instance}`
- `POST /settings/set/{instance}`
- `POST /webhook/set/{instance}`

### Side Effects Observed
- `DELETE /chat/removeProfilePicture/{instance}` returned `200` with empty payload
- `POST /chat/fetchBusinessProfile/{instance}` returned `200` with empty payload
- `POST /chat/fetchProfile/{instance}` returned `200` with empty payload
- `POST /chat/findChats/{instance}` returned `200` with empty payload
- `POST /chat/findContacts/{instance}` returned `200` with empty payload
- `POST /chat/findMessages/{instance}` returned `200` with empty payload
- `POST /chat/findStatusMessage/{instance}` returned `200` with empty payload
- `POST /rabbitmq/set/{instance}` returned `201` with empty payload
- `POST /sqs/set/{instance}` returned `201` with empty payload

## Version Differences
- v1 endpoints: 69
- v2 endpoints: 117
- New in v2 (method/path): 65

## Endpoint Catalog

### V1
#### Chat
| Method | Path | Title | Description | Test |
| --- | --- | --- | --- | --- |
| `PUT` | `/chat/archiveChat/{instance}` | Archive Chat | Archive Chat | 404 |
| `DELETE` | `/chat/deleteMessageForEveryone/{instance}` | Delete Message for Everyone | Delete Message For Everyone | 400 |
| `POST` | `/chat/fetchProfilePictureUrl/{instance}` | Fetch Profile Picture URL | Fetch Profile Picture URL | 500 |
| `GET` | `/chat/findChats/{instance}` | Find Chats | Find all chats | 404 |
| `POST` | `/chat/findContacts/{instance}` | Find Contacts | Find all contacts or just one from ID | 200 |
| `POST` | `/chat/findMessages/{instance}` | Find Messages | Find all messages | 200 |
| `POST` | `/chat/findStatusMessage/{instance}` | Find Status Message | Find status message | 200 |
| `PUT` | `/chat/markMessageAsRead/{instance}` | Mark Message As Read | Mark message as read | 404 |
| `POST` | `/chat/sendPresence/{instance}` | Send Presence | Send Presence (typing...) | 400 |
| `PUT` | `/chat/updateMessage/{instance}` | Update Message | Update message | 404 |
| `POST` | `/chat/whatsappNumbers/{instance}` | Check is WhatsApp | Check if numbers are on WhatsApp | 400 |

#### Get Information
| Method | Path | Title | Description | Test |
| --- | --- | --- | --- | --- |
| `GET` | `/` | Get Information | Get information about your EvolutionAPI | 200 |

#### Groups
| Method | Path | Title | Description | Test |
| --- | --- | --- | --- | --- |
| `GET` | `/group/acceptInviteCode/{instance}` | Accept Invite Code | Fetch group invite code | 400 |
| `POST` | `/group/create/{instance}` | Create Group | Create group | 400 |
| `GET` | `/group/fetchAllGroups/{instance}` | Fetch All Groups | Fetch all groups | 400 |
| `GET` | `/group/findGroupInfos/{instance}` | Find Group by JID | Find group by remote JID | 400 |
| `GET` | `/group/inviteCode/{instance}` | Fetch Invite Code | Fetch group invite code | 400 |
| `GET` | `/group/inviteInfo/{instance}` | Find Group by Invite Code | Find group by invite code | 400 |
| `DELETE` | `/group/leaveGroup/{instance}` | Leave Group | Leave group | 400 |
| `GET` | `/group/participants/{instance}` | Find Group Members | Fetch all group members | 400 |
| `PUT` | `/group/revokeInviteCode/{instance}` | Revoke Invite Code | Fetch group invite code | 404 |
| `POST` | `/group/sendInvite/{instance}` | Send Group Invite | Send group invite | 400 |
| `PUT` | `/group/toggleEphemeral/{instance}` | Toggle Ephemeral | Toggle temporary messages on group | 404 |
| `PUT` | `/group/updateGroupDescription/{instance}` | Update Group Description | Update group description | 404 |
| `PUT` | `/group/updateGroupPicture/{instance}` | Update Group Picture | Create group | 404 |
| `PUT` | `/group/updateGroupSubject/{instance}` | Update Group Subject | Update group subject | 404 |
| `PUT` | `/group/updateParticipant/{instance}` | Update Group Members | Update group members | 404 |
| `PUT` | `/group/updateSetting/{instance}` | Update Group Setting | Update group settings | 404 |

#### Instances
| Method | Path | Title | Description | Test |
| --- | --- | --- | --- | --- |
| `GET` | `/instance/connect/{instance}` | Instance Connect | Generates and returns the QR code for WhatsApp connection | 404 |
| `GET` | `/instance/connectionState/{instance}` | Connection State | Gets the state of the connection | 404 |
| `POST` | `/instance/create` | Create Instance Basic |  | 401 |
| `DELETE` | `/instance/delete/{instance}` | Delete Instance | Deletes instance | 404 |
| `GET` | `/instance/fetchInstances` | Fetch Instances | Returns the instance with the name informed in the parameter, or all the instances if empty. | 200 |
| `DELETE` | `/instance/logout/{instance}` | Logout Instance | Makes logout on instance | 404 |
| `PUT` | `/instance/restart/{instance}` | Restart Instance | Restarts the instance | 404 |
| `POST` | `/instance/setPresence/{instance}` | Set Presence | Deletes instance | 404 |

#### Integrations: Chatwoot
| Method | Path | Title | Description | Test |
| --- | --- | --- | --- | --- |
| `GET` | `/chatwoot/find/{instance}` | Find Chatwoot | Find Chatwoot | 200 |
| `POST` | `/chatwoot/set/{instance}` | Set Chatwoot | Set Chatwoot | 400 |

#### Integrations: RabbitMQ
| Method | Path | Title | Description | Test |
| --- | --- | --- | --- | --- |
| `GET` | `/rabbitmq/find/{instance}` | Find RabbitMQ | Find RabbitMQ | 200 |
| `POST` | `/rabbitmq/set/{instance}` | Set RabbitMQ | Set RabbitMQ | 201 |

#### Integrations: SQS
| Method | Path | Title | Description | Test |
| --- | --- | --- | --- | --- |
| `GET` | `/sqs/find/{instance}` | Find SQS | Find SQS | 200 |
| `POST` | `/sqs/set/{instance}` | Set SQS | Set SQS | 201 |

#### Integrations: Typebot
| Method | Path | Title | Description | Test |
| --- | --- | --- | --- | --- |
| `POST` | `/typebot/changeStatus/{instance}` | Change Typebot Status | Start typebot | 400 |
| `GET` | `/typebot/find/{instance}` | Find Typebot | Find typebot | 400 |
| `POST` | `/typebot/set/{instance}` | Set Typebot | Set typebot | 404 |
| `POST` | `/typebot/start/{instance}` | Start Typebot | Start typebot | 400 |

#### Integrations: Websocket
| Method | Path | Title | Description | Test |
| --- | --- | --- | --- | --- |
| `GET` | `/chatwoot/find/{instance}` | Find Chatwoot | Find Chatwoot | 200 |
| `POST` | `/chatwoot/set/{instance}` | Set Chatwoot | Set Chatwoot | 400 |

#### Messages
| Method | Path | Title | Description | Test |
| --- | --- | --- | --- | --- |
| `POST` | `/message/sendContact/{instance}` | Send Contact | Send Contact | 400 |
| `POST` | `/message/sendList/{instance}` | Send List | Send List | 400 |
| `POST` | `/message/sendLocation/{instance}` | Send Location | Send Location | 400 |
| `POST` | `/message/sendMedia/{instance}` | Send Media | Send media message | 400 |
| `POST` | `/message/sendPoll/{instance}` | Send Poll | Send Poll | 400 |
| `POST` | `/message/sendReaction/{instance}` | Send Reaction | Send Reaction | 400 |
| `POST` | `/message/sendStatus/{instance}` | Send Status | Post WhatsApp status (stories) | 400 |
| `POST` | `/message/sendSticker/{instance}` | Send Sticker | Send Sticker | 400 |
| `POST` | `/message/sendTemplate/{instance}` | Send Template | Send a template message with the Official WhatsApp API | 400 |
| `POST` | `/message/sendText/{instance}` | Send Plain Text | Send plain text message | 400 |
| `POST` | `/message/sendWhatsAppAudio/{instance}` | Send WhatsApp Audio | Send WhatsApp Audio | 400 |

#### Profile
| Method | Path | Title | Description | Test |
| --- | --- | --- | --- | --- |
| `POST` | `/chat/fetchBusinessProfile/{instance}` | Fetch Business Profile | Fetch business profile from phone number | 200 |
| `GET` | `/chat/fetchPrivacySettings/{instance}` | Fetch Privacy Settings | Fetch privacy settings | 500 |
| `POST` | `/chat/fetchProfile/{instance}` | Fetch Profile | Fetch business profile from phone number | 200 |
| `PUT` | `/chat/removeProfilePicture/{instance}` | Remove Profile Picture |  | 404 |
| `PUT` | `/chat/updatePrivacySettings/{instance}` | Update Privacy Settings | Update privacy settings | 404 |
| `POST` | `/chat/updateProfileName/{instance}` | Update Profile Name | Update profile name | 500 |
| `PUT` | `/chat/updateProfilePicture/{instance}` | Update Profile Picture | Update profile picture | 404 |
| `POST` | `/chat/updateProfileStatus/{instance}` | Update Profile Status | Update profile status | 500 |

#### Settings
| Method | Path | Title | Description | Test |
| --- | --- | --- | --- | --- |
| `GET` | `/settings/find/{instance}` | Find Settings | Fetch Webhook configuration | 200 |
| `POST` | `/settings/set/{instance}` | Set Settings | Set settings | 404 |

#### Webhook
| Method | Path | Title | Description | Test |
| --- | --- | --- | --- | --- |
| `GET` | `/webhook/find/{instance}` | Find Webhook | Fetch Webhook configuration | 200 |
| `POST` | `/webhook/set/{instance}` | Set Webhook | Set Webhook for instance | 404 |

### V2
#### Chat
| Method | Path | Title | Description | Test |
| --- | --- | --- | --- | --- |
| `POST` | `/chat/archiveChat/{instance}` | Archive Chat |  | 400 |
| `DELETE` | `/chat/deleteMessageForEveryone/{instance}` | Delete Message for Everyone |  | 400 |
| `POST` | `/chat/fetchProfilePictureUrl/{instance}` | Fetch Profile Picture URL |  | 500 |
| `POST` | `/chat/findChats/{instance}` | Find Chats |  | 200 |
| `POST` | `/chat/findContacts/{instance}` | Find Contacts |  | 200 |
| `POST` | `/chat/findMessages/{instance}` | Find Messages |  | 200 |
| `POST` | `/chat/findStatusMessage/{instance}` | Find Status Message |  | 200 |
| `POST` | `/chat/getBase64FromMediaMessage/{instance}` | Get Base64 |  | 400 |
| `POST` | `/chat/markChatUnread/{instance}` | Mark Message As Unread |  | 400 |
| `POST` | `/chat/markMessageAsRead/{instance}` | Mark Message As Read |  | 400 |
| `POST` | `/chat/sendPresence/{instance}` | Send Presence |  | 400 |
| `POST` | `/chat/updateMessage/{instance}` | Update Message |  | 500 |
| `POST` | `/chat/whatsappNumbers/{instance}` | Check is WhatsApp |  | 400 |
| `POST` | `/message/updateBlockStatus/{instance}` | Update Block Status |  | 404 |

#### Get Information
| Method | Path | Title | Description | Test |
| --- | --- | --- | --- | --- |
| `GET` | `/` | Get Information |  | 200 |

#### Groups
| Method | Path | Title | Description | Test |
| --- | --- | --- | --- | --- |
| `POST` | `/group/create/{instance}` | Create Group |  | 400 |
| `GET` | `/group/fetchAllGroups/{instance}` | Fetch All Groups |  | 400 |
| `GET` | `/group/findGroupInfos/{instance}` | Find Group by JID |  | 400 |
| `GET` | `/group/inviteCode/{instance}` | Fetch Invite Code |  | 400 |
| `GET` | `/group/inviteInfo/{instance}` | Find Group by Invite Code |  | 400 |
| `DELETE` | `/group/leaveGroup/{instance}` | Leave Group |  | 400 |
| `GET` | `/group/participants/{instance}` | Find Group Members |  | 400 |
| `POST` | `/group/revokeInviteCode/{instance}` | Revoke Invite Code |  | 400 |
| `POST` | `/group/sendInvite/{instance}` | Send Group Invite |  | 400 |
| `POST` | `/group/toggleEphemeral/{instance}` | Toggle Ephemeral |  | 400 |
| `POST` | `/group/updateGroupDescription/{instance}` | Update Group Description |  | 400 |
| `POST` | `/group/updateGroupPicture/{instance}` | Update Group Picture |  | 400 |
| `POST` | `/group/updateGroupSubject/{instance}` | Update Group Subject |  | 400 |
| `POST` | `/group/updateParticipant/{instance}` | Update Group Members |  | 400 |
| `POST` | `/group/updateSetting/{instance}` | Update Group Setting |  | 400 |

#### Instances
| Method | Path | Title | Description | Test |
| --- | --- | --- | --- | --- |
| `GET` | `/instance/connect/{instance}` | Instance Connect |  | 404 |
| `GET` | `/instance/connectionState/{instance}` | Connection State |  | 404 |
| `POST` | `/instance/create` | Create Instance |  | 401 |
| `DELETE` | `/instance/delete/{instance}` | Delete Instance |  | 404 |
| `GET` | `/instance/fetchInstances` | Fetch Instances |  | 200 |
| `DELETE` | `/instance/logout/{instance}` | Logout Instance |  | 404 |
| `PUT` | `/instance/restart/{instance}` | Restart Instance |  | 404 |
| `POST` | `/instance/setPresence/{instance}` | Set Presence |  | 404 |

#### Integrations: Chatwoot
| Method | Path | Title | Description | Test |
| --- | --- | --- | --- | --- |
| `GET` | `/chatwoot/find/{instance}` | Find Chatwoot |  | 200 |
| `POST` | `/chatwoot/set/{instance}` | Set Chatwoot |  | 400 |

#### Integrations: Dify
| Method | Path | Title | Description | Test |
| --- | --- | --- | --- | --- |
| `POST` | `/dify/changeStatus/{instance}` | Change Status Bot |  | 400 |
| `POST` | `/dify/create/{instance}` | Create Dify Bot |  | 400 |
| `GET` | `/dify/fetchSessions/:difyId/{instance}` | Find Status Bot |  | 400 |
| `GET` | `/dify/fetchSettings/{instance}` | Find Dify Settings |  | 400 |
| `GET` | `/dify/find/:difyId/{instance}` | Find Dify Bot |  | 404 |
| `GET` | `/dify/find/{instance}` | Find Dify Bots |  | 400 |
| `POST` | `/dify/settings/{instance}` | Set Dify Settings |  | 400 |
| `PUT` | `/dify/update/:difyId/{instance}` | Update Dify Bot |  | 400 |

#### Integrations: Evolution Bot
| Method | Path | Title | Description | Test |
| --- | --- | --- | --- | --- |
| `POST` | `/evolutionBot/changeStatus/{instance}` | Change Evolution Bot status |  | 400 |
| `POST` | `/evolutionBot/create/{instance}` | Create Evolution Bot |  | 400 |
| `DELETE` | `/evolutionBot/delete/:evolutionBotId/{instance}` | Delete Evolution Bot |  | 500 |
| `GET` | `/evolutionBot/fetch/:evolutionBotId/{instance}` | Fetch Evolution Bot |  | 200 |
| `GET` | `/evolutionBot/fetchSessions/:evolutionBotId/{instance}` | Fetch Evolution Bot Session |  | 200 |
| `GET` | `/evolutionBot/fetchSettings/{instance}` | Find Settings Bot |  | 200 |
| `GET` | `/evolutionBot/find/{instance}` | Find Evolution Bots |  | 200 |
| `POST` | `/evolutionBot/settings/{instance}` | Set Settings Bot |  | 400 |
| `PUT` | `/evolutionBot/update/:evolutionBotId/{instance}` | Update Evolution Bot |  | 400 |

#### Integrations: Flowise
| Method | Path | Title | Description | Test |
| --- | --- | --- | --- | --- |
| `POST` | `/flowise/changeStatus/{instance}` | Change Status Session |  | 400 |
| `POST` | `/flowise/create/{instance}` | Create Flowise Bot |  | 400 |
| `DELETE` | `/flowise/delete/:flowiseId/{instance}` | Delete Flowise Bot |  | 400 |
| `GET` | `/flowise/fetchSessions/:flowiseId/{instance}` | Find Sessions Flowise |  | 400 |
| `GET` | `/flowise/fetchSettings/{instance}` | Find Flowise settings |  | 400 |
| `GET` | `/flowise/find/:flowiseId/{instance}` | Find Flowise Bot |  | 404 |
| `GET` | `/flowise/find/{instance}` | Find Flowise Bots |  | 400 |
| `POST` | `/flowise/settings/{instance}` | Set Settings Flowise Bots |  | 400 |
| `POST` | `/flowise/update/:flowiseId/{instance}` | Update Flowise Bot |  | 404 |

#### Integrations: OpenAI
| Method | Path | Title | Description | Test |
| --- | --- | --- | --- | --- |
| `POST` | `/openai/changeStatus/{instance}` | Change status OpenAI |  | 400 |
| `POST` | `/openai/create/{instance}` | Create OpenIA Bot |  | 400 |
| `DELETE` | `/openai/creds/:openaiCredsId/{instance}` | Delete OpenIA Bot |  | 500 |
| `GET` | `/openai/creds/{instance}` | Find OpenIA Creds |  | 200 |
| `POST` | `/openai/creds/{instance}` | Creds config OpenAI |  | 400 |
| `DELETE` | `/openai/delete/:openaiBotId/{instance}` | Delete OpenIA Bot |  | 500 |
| `GET` | `/openai/fetchSessions/:openaiBotId/{instance}` | Find sessions OpenAI |  | 200 |
| `GET` | `/openai/fetchSettings/{instance}` | Find settings OpenAI |  | 200 |
| `GET` | `/openai/find/:openaiBotId/{instance}` | Find OpenIA Bot |  | 404 |
| `GET` | `/openai/find/{instance}` | Find OpenIA Bots |  | 200 |
| `POST` | `/openai/settings/{instance}` | Settigns config OpenAI |  | 400 |
| `PUT` | `/openai/update/:openaiBotId/{instance}` | Update Bot |  | 400 |

#### Integrations: RabbitMQ
| Method | Path | Title | Description | Test |
| --- | --- | --- | --- | --- |
| `GET` | `/rabbitmq/find/{instance}` | Find RabbitMQ |  | 200 |
| `POST` | `/rabbitmq/set/{instance}` | Set RabbitMQ |  | 201 |

#### Integrations: SQS
| Method | Path | Title | Description | Test |
| --- | --- | --- | --- | --- |
| `GET` | `/sqs/find/{instance}` | Find SQS |  | 200 |
| `POST` | `/sqs/set/{instance}` | Set SQS |  | 201 |

#### Integrations: Typebot
| Method | Path | Title | Description | Test |
| --- | --- | --- | --- | --- |
| `POST` | `/typebot/changeStatus/{instance}` | Change Session Status |  | 400 |
| `POST` | `/typebot/create/{instance}` | Create Typebot |  | 400 |
| `Delete` | `/typebot/delete/:typebotId/{instance}` | Delete Typebot |  | 400 |
| `GET` | `/typebot/fetch/:typebotId/{instance}` | Fetch Typebot |  | 400 |
| `GET` | `/typebot/fetchSessions/:typebotId/{instance}` | Fetch Session Typebot |  | 400 |
| `GET` | `/typebot/fetchSettings/{instance}` | Fetch Typebot Settings |  | 400 |
| `GET` | `/typebot/find/{instance}` | Find Typebot |  | 400 |
| `POST` | `/typebot/settings/{instance}` | Settings Typebot |  | 400 |
| `POST` | `/typebot/start/{instance}` | Start Typebot |  | 400 |
| `POST` | `/typebot/update/:typebotId/{instance}` | Update Typebot |  | 404 |

#### Integrations: Websocket
| Method | Path | Title | Description | Test |
| --- | --- | --- | --- | --- |
| `GET` | `/websocket/find/{instance}` | Find Websocket |  | 200 |
| `POST` | `/websocket/set/{instance}` | Set Websocket |  | 500 |

#### Messages
| Method | Path | Title | Description | Test |
| --- | --- | --- | --- | --- |
| `POST` | `/message/sendButtons/{instance}` | Send Buttons |  | 400 |
| `POST` | `/message/sendContact/{instance}` | Send Contact |  | 400 |
| `POST` | `/message/sendList/{instance}` | Send List |  | 400 |
| `POST` | `/message/sendLocation/{instance}` | Send Location |  | 400 |
| `POST` | `/message/sendMedia/{instance}` | Send Media |  | 400 |
| `POST` | `/message/sendPoll/{instance}` | Send Poll |  | 400 |
| `POST` | `/message/sendReaction/{instance}` | Send Reaction |  | 400 |
| `POST` | `/message/sendStatus/{instance}` | Send Status |  | 400 |
| `POST` | `/message/sendSticker/{instance}` | Send Sticker |  | 400 |
| `POST` | `/message/sendText/{instance}` | Send Plain Text |  | 400 |
| `POST` | `/message/sendWhatsAppAudio/{instance}` | Send WhatsApp Audio |  | 400 |

#### Profile
| Method | Path | Title | Description | Test |
| --- | --- | --- | --- | --- |
| `POST` | `/chat/fetchBusinessProfile/{instance}` | Fetch Business Profile |  | 200 |
| `GET` | `/chat/fetchPrivacySettings/{instance}` | Fetch Privacy Settings |  | 500 |
| `POST` | `/chat/fetchProfile/{instance}` | Fetch Profile |  | 200 |
| `DELETE` | `/chat/removeProfilePicture/{instance}` | Remove Profile Picture |  | 200 |
| `POST` | `/chat/updatePrivacySettings/{instance}` | Update Privacy Settings |  | 400 |
| `POST` | `/chat/updateProfileName/{instance}` | Update Profile Name |  | 500 |
| `POST` | `/chat/updateProfilePicture/{instance}` | Update Profile Picture |  | 500 |
| `POST` | `/chat/updateProfileStatus/{instance}` | Update Profile Status |  | 500 |

#### Settings
| Method | Path | Title | Description | Test |
| --- | --- | --- | --- | --- |
| `GET` | `/settings/find/{instance}` | Find Settings |  | 200 |
| `POST` | `/settings/set/{instance}` | Set Settings |  | 404 |

#### Webhook
| Method | Path | Title | Description | Test |
| --- | --- | --- | --- | --- |
| `GET` | `/webhook/find/{instance}` | Find Webhook |  | 200 |
| `POST` | `/webhook/set/{instance}` | Set Webhook |  | 404 |
