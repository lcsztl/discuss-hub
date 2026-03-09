# `mail_discuss_hub_llm` — Blueprint Final (Hybrid Architecture)

> Versão: 2.0 — 7 de março de 2026
> Substitui o documento anterior (Design C puro).

---

## 1. Premissa Revisada

A análise original (Design C) propunha usar `llm.thread` apenas como *config container*,
montando contexto externo e chamando `model.chat()` diretamente. Essa abordagem, embora
elegante em teoria, esbarra em **três acoplamentos reais** do código `odoo-llm`:

| # | Acoplamento | Evidência |
|---|-------------|-----------|
| 1 | `llm.provider.chat()` recebe `mail.message` recordset, não listas arbitrárias | `llm_provider.py` L76: `messages: mail.message recordset (Odoo records) to send` |
| 2 | O formatter OpenAI itera `mail.message` e despacha `format_message` por record | `openai_provider.py` L440‑447: `for message in messages: self._dispatch("format_message", record=message, …)` |
| 3 | Tool loop e estado intermediário (`llm_role`, `body_json`, `has_tool_calls()`) vivem em `mail.message` operados pelo `llm.thread` | `llm_assistant/llm_thread.py` L261‑279: while `_should_continue` → `_generate_assistant_response` / `_execute_tool_call` |

O atalho `prepend_messages` (passar histórico inteiro como dicts e `messages` vazio) funciona
tecnicamente mas pula validação (`_validate_and_clean_messages` roda depois do formatting
do recordset vazio) e é uso lateral da API interna — inapropriado para produção.

**Conclusão:** `llm.thread` deve continuar sendo a **engine real de execução**, não apenas
container de configuração. O que muda em relação à abordagem ingênua (sincronização bidirecional
livre) é o padrão de coordenação: **projeção controlada unidirecional** mediada por uma fila
durável.

---

## 2. Três Fontes de Verdade (ownership claro)

```
┌─────────────────────────────────────────────────────────────────────┐
│                       OWNERSHIP MODEL                               │
├──────────────────────┬──────────────────────────────────────────────┤
│ discuss.channel      │ Fonte de verdade da conversa VISÍVEL ao     │
│                      │ cliente. Tudo que o cliente vê/envia.       │
├──────────────────────┼──────────────────────────────────────────────┤
│ mail.discuss.hub.    │ Fonte de verdade da AUTOMAÇÃO assíncrona.   │
│ llm.run              │ Fila durável, idempotente, rastreável.      │
├──────────────────────┼──────────────────────────────────────────────┤
│ llm.thread           │ Fonte de verdade da MEMÓRIA OPERACIONAL     │
│                      │ do bot: prompt, tools, traces, contexto.    │
│                      │ Engine real de geração (chat/tools/stream).  │
└──────────────────────┴──────────────────────────────────────────────┘
```

**Não são dois stores concorrentes.** São três modelos com ownership distinto e fluxo de
dados controlado por **projeção unidirecional**:

```
    WhatsApp          discuss.channel         llm.run           llm.thread
    ───────           ───────────────         ───────           ──────────
       │ inbound             │                   │                  │
       ├────────────────────►│ message_post       │                  │
       │                     │ (user msg)         │                  │
       │                     ├──────────────────► │ CREATE           │
       │                     │                    │ state=pending    │
       │                     │                    │                  │
       │                     │              ┌─────┤ postcommit/cron  │
       │                     │              │     │                  │
       │                     │              │     ├─────────────────►│ message_post
       │                     │              │     │ PROJECT          │ llm_role=user
       │                     │              │     │                  │
       │                     │              │     │                  │ generate_messages()
       │                     │              │     │                  │ ┌─loop─┐
       │                     │              │     │                  │ │tools │
       │                     │              │     │                  │ │stream│
       │                     │              │     │                  │ └──────┘
       │                     │              │     │◄─────────────────┤ final assistant text
       │                     │◄─────────────┤     │ PUBLISH          │
       │◄────────────────────│ message_post │     │                  │
       │  outbound           │ (bot reply)  │     │ state=done       │
       │                     │              └─────┤                  │
```

---

## 3. Modelos

### 3.1 `discuss.channel` (extensão)

Campos adicionados no `discuss.channel` pelo módulo:

```python
class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    llm_thread_id = fields.Many2one(
        "llm.thread",
        string="LLM Thread",
        ondelete="set null",
        index=True,
        copy=False,
    )
    llm_assistant_id = fields.Many2one(
        "llm.assistant",
        string="AI Assistant",
        help="AI assistant assigned to auto-reply in this channel.",
    )
    llm_auto_reply = fields.Boolean(
        string="AI Auto-Reply",
        default=False,
        help="When enabled, inbound customer messages trigger AI generation.",
    )
```

**Decisão de design:** `llm_thread_id` é um FK explícito, não `search(model=…, res_id=…, limit=1)`.
Isso evita a fragilidade do mixin upstream (`llm_assistant_action_mixin.py` L102) e garante
binding 1:1 determinístico.

### 3.2 `mail.discuss.hub.llm.run`

Fila durável de automação. Cada run = uma unidade atômica de trabalho (inbound → project → generate → publish).

```python
class DiscussHubLlmRun(models.Model):
    _name = "mail.discuss.hub.llm.run"
    _description = "Discuss Hub LLM Run"
    _order = "create_date ASC"
    _rec_name = "display_name"

    channel_id = fields.Many2one(
        "discuss.channel",
        required=True,
        ondelete="cascade",
        index=True,
    )
    llm_thread_id = fields.Many2one(
        "llm.thread",
        ondelete="cascade",
        index=True,
    )
    trigger_message_id = fields.Many2one(
        "mail.message",
        string="Trigger Message",
        help="The inbound message that triggered this run.",
        ondelete="set null",
    )
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("projecting", "Projecting"),
            ("generating", "Generating"),
            ("publishing", "Publishing"),
            ("done", "Done"),
            ("suggest", "Awaiting Review"),
            ("error", "Error"),
        ],
        default="pending",
        required=True,
        index=True,
    )
    result_text = fields.Text(
        string="Generated Response",
        help="AI-generated text. Published to channel after review (suggest mode) or immediately.",
    )
    error_message = fields.Text()
    attempt_count = fields.Integer(default=0)
    max_attempts = fields.Integer(default=3)

    # ── Suggest-first fields ──
    suggest_mode = fields.Boolean(
        related="channel_id.llm_suggest_mode",
        store=False,
    )
    reviewed_by = fields.Many2one("res.users", readonly=True)
    reviewed_at = fields.Datetime(readonly=True)
```

#### Estados e transições

```
pending ──► projecting ──► generating ──► publishing ──► done
                                     │
                                     └──► suggest (se suggest_mode)
                                              │
                                              ├──► publishing ──► done  (aprovado)
                                              └──► done            (rejeitado/editado)

Qualquer estado ──► error (em caso de exceção)
```

### 3.3 `llm.thread` (sem modificação)

O `llm.thread` não é modificado. Ele é usado **as-is** como engine de geração, com sua
stack completa de:
- `generate_messages()` (loop de tools + streaming)
- `_generate_assistant_response()` (chat API via provider)
- `_execute_tool_call()` (tool execution)
- `get_llm_messages()` (context retrieval — `mail.message` recordset)
- `_generation_lock()` (PostgreSQL advisory lock)

O módulo apenas **popula** o thread com messages projetadas e **consome** o resultado final.

---

## 4. Regras de Projeção

A projeção é o mecanismo que mantém o `llm.thread` sincronizado com a conversa do canal
**sem** ser uma sincronização bidirecional livre.

### 4.1 Canal → Thread (projeção de entrada)

| Origem no `discuss.channel` | Destino no `llm.thread` | `llm_role` | Quando |
|---|---|---|---|
| Mensagem do cliente (inbound) | `message_post` no thread | `user` | Run state=projecting |
| Mensagem de operador humano enviada com sucesso | `message_post` no thread | `assistant` | Após outbound gateway success |

**Justificativa do mapeamento de operador → assistant:**
Do ponto de vista do LLM, mensagens humanas já enviadas ao cliente são parte do histórico
que o bot deve ter como contexto. O LLM atende como "assistente" — quando um humano
responde, o LLM vê isso como "resposta que o assistente deu" e mantém coerência.

### 4.2 Thread → Canal (projeção de saída)

| Origem no `llm.thread` | Destino no `discuss.channel` | Quando |
|---|---|---|
| Resposta final do assistant (texto) | `channel.message_post()` (dispara outbound gateway) | Run state=publishing |
| Tool messages | **NÃO publicadas** — ficam apenas no thread | Nunca |
| Error messages | Logadas no run, opcionalmente notificadas ao operador | Run state=error |

### 4.3 Regras de não-projeção

- **Tool messages** nunca saem do `llm.thread`. O cliente não vê traces de tools.
- **Mensagens de notificação** (`message_type=notification`) não são projetadas.
- **Mensagens do bot** no canal não são re-projetadas de volta ao thread (já nasceram lá).
  Flag de contexto `llm_bot_message=True` previne loop.

---

## 5. Fluxo Detalhado

### 5.1 Inbound → Auto-Reply

```python
# Em common_inbound.py, após message creation bem-sucedida:

def _handle_message_upsert(self, gateway, dto, channel, author=None):
    # ... código existente até return {"status": "ok", ...}
    result = {"status": "ok", "message_id": message.id, "channel_id": channel.id}

    # ── HOOK: post-inbound processing ──
    self._after_inbound_message(gateway, dto, channel, message)

    return result


# Hook (no-op na base, overridden pelo mail_discuss_hub_llm):
def _after_inbound_message(self, gateway, dto, channel, message):
    """Extension point for post-inbound processing."""
    pass
```

### 5.2 Hook Override no `mail_discuss_hub_llm`

```python
class MailGatewayWhatsappCommonInbound(MailGatewayWhatsappCommonInbound):

    def _after_inbound_message(self, gateway, dto, channel, message):
        """Create LLM run if channel has auto-reply enabled."""
        super()._after_inbound_message(gateway, dto, channel, message)

        if not channel.llm_auto_reply or not channel.llm_assistant_id:
            return

        # Ensure thread exists
        thread = channel.llm_thread_id
        if not thread:
            thread = self._ensure_llm_thread(channel)

        # Dedup: skip if run already exists for this message
        Run = self.env["mail.discuss.hub.llm.run"].sudo()
        existing = Run.search([
            ("trigger_message_id", "=", message.id),
            ("state", "!=", "error"),
        ], limit=1)
        if existing:
            return

        # Create run
        run = Run.create({
            "channel_id": channel.id,
            "llm_thread_id": thread.id,
            "trigger_message_id": message.id,
            "state": "pending",
        })

        # Schedule async processing via postcommit
        dbname = self.env.cr.dbname
        run_id = run.id

        @self.env.cr.postcommit.add
        def _process_run():
            self._process_llm_run_async(dbname, run_id)
```

### 5.3 Worker Assíncrono

```python
def _process_llm_run_async(self, dbname, run_id):
    """Process LLM run in a separate cursor (non-blocking)."""
    from odoo.modules.registry import Registry

    registry = Registry(dbname)
    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        run = env["mail.discuss.hub.llm.run"].browse(run_id)
        if not run.exists() or run.state != "pending":
            return
        try:
            run._execute()
        except Exception:
            _logger.exception("LLM run %s failed", run_id)
            run.write({
                "state": "error",
                "error_message": traceback.format_exc(),
                "attempt_count": run.attempt_count + 1,
            })
            cr.commit()
```

### 5.4 Execução do Run (`_execute`)

```python
class DiscussHubLlmRun(models.Model):
    # ...

    def _execute(self):
        """Main execution flow: project → generate → publish."""
        self.ensure_one()

        # ── STEP 1: Project inbound message to thread ──
        self.write({"state": "projecting"})
        self.env.cr.commit()

        self._project_trigger_message()

        # ── STEP 2: Generate AI response ──
        self.write({"state": "generating"})
        self.env.cr.commit()

        result_text = self._generate_response()

        # ── STEP 3: Publish or suggest ──
        self.write({
            "result_text": result_text,
            "state": "suggest" if self.suggest_mode else "publishing",
        })
        self.env.cr.commit()

        if not self.suggest_mode:
            self._publish_response()
            self.write({"state": "done"})
            self.env.cr.commit()

    def _project_trigger_message(self):
        """Project the inbound message to the llm.thread as a user message."""
        trigger = self.trigger_message_id
        if not trigger:
            return

        # Extract plain text from message body
        body = self._extract_plain_text(trigger.body)
        if not body:
            return

        self.llm_thread_id.message_post(
            body=body,
            llm_role="user",
            author_id=False,  # Let thread generate appropriate email_from
        )

    def _generate_response(self):
        """Run the llm.thread generation engine and capture the final text."""
        thread = self.llm_thread_id

        final_text = ""
        for event in thread.generate_messages():
            # Consume the generator — capture final assistant text
            if event.get("type") == "message_update":
                msg_data = event.get("message", {})
                # The last message_update with assistant role contains final text
                final_text = self._extract_text_from_store(msg_data)
            elif event.get("type") == "error":
                raise RuntimeError(event.get("error", "LLM generation failed"))

        if not final_text:
            # Fallback: read the last assistant message from thread
            last_msg = thread.get_latest_llm_message()
            if last_msg and last_msg.llm_role == "assistant":
                final_text = self._extract_plain_text(last_msg.body)

        return final_text

    def _publish_response(self):
        """Publish the AI response to the discuss.channel (triggers outbound gateway)."""
        if not self.result_text:
            return

        channel = self.channel_id
        gateway = channel.gateway_id

        # Use the gateway's webhook user as author (bot identity)
        bot_user = gateway.webhook_user_id or self.env.ref("base.user_root")
        bot_partner = bot_user.partner_id

        channel.with_user(bot_user).with_context(
            llm_bot_message=True,  # Prevent re-projection loop
        ).message_post(
            author_id=bot_partner.id,
            body=self.result_text,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )
        # The OCA override on discuss.channel.message_post() will create
        # mail.notification + send_gateway() automatically.
```

### 5.5 Projeção de Mensagens de Operador Humano

Quando um operador humano responde no canal (via UI do Odoo), essa mensagem precisa
ser projetada ao `llm.thread` como `assistant` para que o LLM tenha contexto completo.

```python
class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    @api.returns("mail.message", lambda value: value.id)
    def message_post(self, **kwargs):
        message = super().message_post(**kwargs)

        # Skip if: no thread, not gateway channel, notification, or bot message
        if (
            not self.llm_thread_id
            or not self.llm_auto_reply
            or self.env.context.get("no_gateway_notification")
            or self.env.context.get("llm_bot_message")
            or message.message_type == "notification"
        ):
            return message

        # Human operator message → project to thread as assistant
        if message.author_id != self._get_gateway_customer_partner():
            self._project_human_message_to_thread(message)

        return message

    def _project_human_message_to_thread(self, message):
        """Project a human operator's outbound message to the LLM thread."""
        body = self.env["mail.discuss.hub.llm.run"]._extract_plain_text(message.body)
        if not body:
            return
        self.llm_thread_id.message_post(
            body=body,
            llm_role="assistant",
            author_id=False,
        )
```

---

## 6. Sugestão-Primeiro (Suggest Mode)

Quando `llm_suggest_mode = True` no canal (campo novo):

```python
class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    llm_suggest_mode = fields.Boolean(
        string="AI Suggest Mode",
        default=True,
        help="When enabled, AI responses are held for human review before sending.",
    )
```

1. O run para no estado `suggest` com `result_text` preenchido.
2. O operador vê a sugestão (via view ou notificação bus).
3. O operador pode: **aprovar** (publica como está), **editar** (modifica e publica),
   ou **rejeitar** (descarta, run → done sem publicação).

```python
class DiscussHubLlmRun(models.Model):
    # ...

    def action_approve(self):
        """Approve and publish the suggested response."""
        self.ensure_one()
        if self.state != "suggest":
            return
        self.write({
            "state": "publishing",
            "reviewed_by": self.env.uid,
            "reviewed_at": fields.Datetime.now(),
        })
        self._publish_response()
        self.write({"state": "done"})

    def action_reject(self):
        """Reject the suggested response without publishing."""
        self.ensure_one()
        if self.state != "suggest":
            return
        self.write({
            "state": "done",
            "reviewed_by": self.env.uid,
            "reviewed_at": fields.Datetime.now(),
            "result_text": False,
        })

    def action_edit_and_approve(self, new_text):
        """Edit the response and publish."""
        self.ensure_one()
        if self.state != "suggest":
            return
        self.write({
            "result_text": new_text,
            "state": "publishing",
            "reviewed_by": self.env.uid,
            "reviewed_at": fields.Datetime.now(),
        })
        self._publish_response()
        self.write({"state": "done"})
```

---

## 7. Criação e Vinculação do Thread

O `llm.thread` é criado **lazily** na primeira vez que o canal precisa processar uma
mensagem de auto-reply, e vinculado via FK explícito.

```python
def _ensure_llm_thread(self, channel):
    """Create and bind an llm.thread to the channel."""
    assistant = channel.llm_assistant_id
    if not assistant:
        raise UserError(_("No AI assistant configured for this channel."))

    # Use assistant's provider/model (already configured)
    thread = self.env["llm.thread"].sudo().create({
        "model": "discuss.channel",
        "res_id": channel.id,
        "provider_id": assistant.provider_id.id or self._get_default_provider().id,
        "model_id": assistant.model_id.id or self._get_default_model().id,
    })

    # Set assistant (configures tools, prompt, etc.)
    thread.set_assistant(assistant.id)

    # Bind via explicit FK
    channel.sudo().write({"llm_thread_id": thread.id})

    return thread
```

---

## 8. Cron de Segurança

Para runs que falharam no postcommit (crash do processo, timeout), um cron tenta
reprocessar:

```xml
<record id="ir_cron_process_pending_llm_runs" model="ir.cron">
    <field name="name">Process Pending LLM Runs</field>
    <field name="model_id" ref="model_mail_discuss_hub_llm_run"/>
    <field name="state">code</field>
    <field name="code">model._cron_process_pending_runs()</field>
    <field name="interval_number">2</field>
    <field name="interval_type">minutes</field>
    <field name="active" eval="True"/>
    <field name="numbercall">-1</field>
</record>
```

```python
class DiscussHubLlmRun(models.Model):
    # ...

    @api.model
    def _cron_process_pending_runs(self):
        """Process runs stuck in pending state (fallback for postcommit failures)."""
        stale_cutoff = fields.Datetime.subtract(fields.Datetime.now(), minutes=1)
        stuck_runs = self.search([
            ("state", "=", "pending"),
            ("create_date", "<", stale_cutoff),
            ("attempt_count", "<", "max_attempts"),
        ])
        for run in stuck_runs:
            try:
                run._execute()
            except Exception:
                _logger.exception("Cron: LLM run %s failed", run.id)
                run.write({
                    "state": "error",
                    "error_message": traceback.format_exc(),
                    "attempt_count": run.attempt_count + 1,
                })
                self.env.cr.commit()
```

---

## 9. Anti-Loop Guards

### 9.1 Contexto `llm_bot_message`

Quando o run publica a resposta no canal, o `message_post` é feito com
`context(llm_bot_message=True)`. O hook de projeção de operador humano verifica
esse flag e **não** re-projeta:

```python
if self.env.context.get("llm_bot_message"):
    return message  # Don't project bot's own message back to thread
```

### 9.2 Contexto `no_gateway_notification` (inbound)

Mensagens inbound já chegam com `no_gateway_notification=True` pelo pipeline OCA existente.
Portanto, projetar mensagens ao thread **não** dispara outbound gateway acidentalmente
(o thread não é um `discuss.channel` gateway).

### 9.3 Dedup por `trigger_message_id`

Antes de criar um novo run, verificar se já existe um run para a mesma mensagem:

```python
existing = Run.search([
    ("trigger_message_id", "=", message.id),
    ("state", "!=", "error"),
], limit=1)
if existing:
    return  # Already scheduled
```

### 9.4 Advisory Lock no Thread

O `llm.thread.generate()` já usa `pg_try_advisory_lock(thread.id)` internamente
(`_generation_lock`). Se dois runs tentarem gerar simultaneamente no mesmo thread,
o segundo será bloqueado/rejeitado pelo lock. Isso é herdado gratuitamente.

---

## 10. Estrutura do Módulo

```
mail_discuss_hub_llm/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── discuss_channel.py          # Extensão: llm_thread_id, llm_assistant_id, llm_auto_reply,
│   │                               #           llm_suggest_mode, _project_human_message_to_thread
│   ├── discuss_hub_llm_run.py      # Fila durável: states, _execute, _project, _generate, _publish
│   └── common_inbound.py           # Hook: _after_inbound_message → cria run
├── views/
│   ├── discuss_channel_views.xml   # Campos LLM no form do canal gateway
│   └── discuss_hub_llm_run_views.xml  # Tree/form de runs para monitoramento
├── security/
│   └── ir.model.access.csv
├── data/
│   └── ir_cron.xml                 # Cron de segurança
└── README.md
```

### `__manifest__.py`

```python
{
    "name": "Discuss Hub LLM Integration",
    "version": "18.0.1.0.0",
    "category": "Discuss",
    "summary": "AI auto-reply for WhatsApp gateway channels via LLM assistants",
    "depends": [
        "mail_discuss_hub_gateway",
        "mail_gateway_whatsapp_common",
        "llm_assistant",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "views/discuss_channel_views.xml",
        "views/discuss_hub_llm_run_views.xml",
    ],
    "license": "AGPL-3",
    "installable": True,
    "auto_install": False,
}
```

---

## 11. Comparação com Alternativas Descartadas

| Aspecto | Design C puro (anterior) | Sync bidirecional livre | **Híbrido (este)** |
|---|---|---|---|
| `llm.thread` como engine | ❌ Só config | ✅ Sim | ✅ Sim |
| Reutiliza provider/tooling | ❌ Reimplementa | ✅ Sim | ✅ Sim |
| Webhook bloqueante | ❌ | ❌ | ✅ Não-bloqueante |
| Fila durável | ✅ | ❌ | ✅ `llm.run` |
| Ownership claro | ✅ | ❌ Dois stores | ✅ Três stores, projeção controlada |
| Suggest-first | ✅ | Possível | ✅ Nativo no run |
| Tool traces no canal | ❌ | ⚠️ Risco | ✅ Isolados no thread |
| Complexidade | Média-alta | Baixa (mas frágil) | Média |
| Compatibilidade upstream | ⚠️ Uso lateral de API | ✅ | ✅ Usa API normal |

---

## 12. Dependências de Código Upstream

### 12.1 Hook necessário em `common_inbound.py`

**Arquivo:** `mail_gateway_whatsapp_common/models/common_inbound.py`
**Mudança:** Adicionar chamada `_after_inbound_message()` antes do return final de `_handle_message_upsert()`.

```python
# Antes do return {"status": "ok", ...}
self._after_inbound_message(gateway, dto, channel, message)
```

E definir o método base como no-op:

```python
def _after_inbound_message(self, gateway, dto, channel, message):
    """Extension point for post-inbound message processing.
    Override in downstream modules (e.g., mail_discuss_hub_llm) to add behavior.
    """
    pass
```

**Impacto:** Mínimo — é um hook extensível, não altera comportamento existente.

### 12.2 Nenhuma mudança no `odoo-llm`

O módulo não requer nenhuma modificação nos módulos `llm`, `llm_thread`, `llm_assistant`,
`llm_generate`, ou `llm_openai`. Toda a integração é feita por composição:
- Cria `mail.message` no `llm.thread` via `message_post()` (API pública)
- Consome `generate_messages()` generator (API pública)
- Lê resultado via `get_latest_llm_message()` (API pública)

---

## 13. Riscos e Mitigações

| Risco | Probabilidade | Mitigação |
|---|---|---|
| Thread acumula contexto demais (custo de tokens) | Média | `get_llm_messages(limit=25)` já existe; pode ser configurável via assistant |
| Operador e bot respondem simultaneamente | Baixa | Run verifica se uma resposta humana foi enviada entre trigger e publish; se sim, descarta |
| LLM demora mais que timeout do WhatsApp (24h window) | Muito baixa | Run tem `max_attempts` e cron; mensagem fica no canal de qualquer forma |
| Crash do worker durante geração | Baixa | Advisory lock é liberado com a conexão; cron reprocessa runs stuck |
| Mensagens fora de ordem no thread | Baixa | Projeção sempre feita pre-generate; advisory lock serializa |

---

## 14. Roadmap de Implementação

### MVP (Sprint 1)
1. Hook `_after_inbound_message` no `common_inbound.py`
2. Modelo `mail.discuss.hub.llm.run` com states e `_execute()`
3. Campos `llm_thread_id`, `llm_assistant_id`, `llm_auto_reply` no `discuss.channel`
4. Projeção de entrada (inbound → thread user message)
5. Geração via `generate_messages()` (consumir generator)
6. Publicação via `channel.message_post()` (dispara outbound)
7. Cron de segurança
8. Views mínimas de monitoramento

### v1.1 (Sprint 2)
9. Suggest-first mode (`llm_suggest_mode`)
10. Projeção de operador humano (outbound → thread assistant)
11. UI de revisão de sugestões (form/widget)
12. Notificação bus para pendências de revisão

### v1.2 (Sprint 3)
13. Configuração de assistant por gateway (não por canal individual)
14. Métricas: tempo de resposta, taxa de aprovação, custo de tokens
15. Rate limiting por canal/contato
16. Multi-idioma: detecção de idioma do cliente → prompt dinâmico

---

## 15. Referências de Código

| Componente | Arquivo |
|---|---|
| `llm.provider.chat()` | `odoo-llm/llm/models/llm_provider.py` L76 |
| OpenAI formatter | `odoo-llm/llm_openai/models/openai_provider.py` L422‑447 |
| `prepend_messages` concat | `odoo-llm/llm_openai/models/openai_provider.py` L174‑178 |
| `llm.thread.generate()` | `odoo-llm/llm_thread/models/llm_thread.py` L352‑396 |
| `llm.thread.generate_messages()` | `odoo-llm/llm_assistant/models/llm_thread.py` L222‑279 |
| `_generate_assistant_response()` | `odoo-llm/llm_assistant/models/llm_thread.py` L287‑335 |
| `_prepare_chat_kwargs()` | `odoo-llm/llm_assistant/models/llm_thread.py` L337‑345 |
| `get_llm_messages()` | `odoo-llm/llm_assistant/models/llm_thread.py` L348‑381 |
| `_generation_lock()` | `odoo-llm/llm_thread/models/llm_thread.py` L576‑608 |
| `llm_assistant_action_mixin._find_or_create_llm_thread` | `odoo-llm/llm_assistant/models/llm_assistant_action_mixin.py` L95‑175 |
| `message_post` override (llm.thread) | `odoo-llm/llm_thread/models/llm_thread.py` L218‑268 |
| `_handle_message_upsert` | `discuss-hub/mail_gateway_whatsapp_common/models/common_inbound.py` L24 |
| OCA `discuss.channel.message_post` (outbound) | `oca/social/mail_gateway/models/discuss_channel.py` L63‑86 |
| Gateway dispatch `_send_message` | `discuss-hub/mail_gateway_base/models/gateway_dispatch_service.py` L212‑260 |
| `postcommit` pattern ref | `discuss-hub/mail_discuss_hub_gateway/mail_gateway_account_notify/models/account_move_send.py` L404 |
