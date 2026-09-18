# Known issues

Findings from a read of the `views-and-modals` working tree. Nothing here has been fixed —
this is a triage list. Every item marked **confirmed** was reproduced against the working
tree; the rest are flagged by reading and say what is uncertain.

> **Heads up:** an installed copy of the package in `site-packages` currently shadows
> `src/`, so `import discord_self_bot_tester` picks up stale code and the blockers below do
> not show up. Reproduce against the working tree with `PYTHONPATH=src`, or install
> editable (`pip install -e .` / `uv sync`).

---

## Blockers — the package does not import

### 1. `requests/component.py:28` imports a name that does not exist — **confirmed**

```
ImportError: cannot import name 'build_interaction' from
'discord_self_bot_tester.requests.commands'
```

`commands.py` names the factory `_build_interaction` (line 248); `component.py` imports
`build_interaction`. `modal.py:22` already imports the underscored name, so this is a
rename that only got applied in one of the two callers.

Because `assertions/__init__.py` transitively imports `requests`, **the entire public API
is unimportable**, including `Bot`. All of `tests/` fails at collection.

### 2. `requests/__init__.py:18-19,44-45` exports `buttons_of` / `dropdowns_of` — **confirmed**

```
ImportError: cannot import name 'buttons_of' from
'discord_self_bot_tester.requests.component'
```

Both functions existed at `HEAD` and were **deleted** in this working tree, along with
`build_interaction`, `build_app_command`, `_resolve_ids` and
`ModalResponseBuilder.compile_request`, as part of the same refactor. The export list was
not updated to match.

Items 1 and 2 are really one thing: a half-applied rename/removal. Worth walking the whole
`git diff` for other dangling references before fixing them piecemeal.

### 3. `tests/test_core.py:121` calls `ApplicationCommandBuilder` with the old signature — **confirmed**

```
TypeError: ApplicationCommandBuilder.__init__() missing 1 required positional argument: 'name'
```

The constructor gained a leading `interaction_type` parameter. The call passes only
`"attendance"`, which lands in `interaction_type`. Should be
`ApplicationCommandBuilder(InteractionType.APP_COMMAND, "attendance")`. The README had the
same staleness and has been corrected.

---

## Correctness bugs

### 4. `assertions/message.py:183` builds a `MessageFilter` that fails validation — **confirmed**

```
ValidationError: 1 validation error for MessageFilter
message_flags  Field required
```

`MessageFilter.message_flags` (`gateway/_base.py:63`) is declared `int | None` with **no
default**, so pydantic makes it required. The default-filter path in
`MessageAssertion.assert_request` omits it.

This fires on the single most common usage — an assertion with no `filter_by_*` at all,
which the README presents as the normal case. The `filter_by_*` builders all happen to
pass `message_flags=None` explicitly, which is why it has gone unnoticed.

Fix: give `author_id`, `channel_id`, `nonce_id` and `message_flags` defaults of `None`.
They are all "unset means don't check" fields, so the required-ness is unintended
throughout.

### 5. `gateway/_base.py:84-86` — `interaction_is_from_author` is inverted and reads the wrong dict — **confirmed**

```python
if self.interaction_is_from_author and \
    ("interaction_metadata" in data or \
        user_id != msg_data["interaction_metadata"]["user"]["id"]):
    return None
```

Two defects compounding:

* `"interaction_metadata" in data` tests the **dispatch envelope**, but the field lives in
  the message body, `msg_data`. So the test is always False.
* The polarity is backwards. The intent is "reject if the key is *missing*"; as written it
  rejects when present.

Net effect: the guard never short-circuits, so the next line indexes
`msg_data["interaction_metadata"]` unconditionally and raises `KeyError:
'interaction_metadata'` on any ordinary, non-interaction message. Reproduced.

Since `matches` is called from the websocket read loop, that `KeyError` escapes into
`init_ws`, kills the socket, and surfaces as `RuntimeError("Websocket died")` — so
`filter_by_interaction_from_author` currently takes the whole connection down.

Should be `"interaction_metadata" not in msg_data or ...`.

### 6. `gateway/message.py:44` — `mentions` is typed `list[str]` but discord sends user objects — **confirmed**

```
ValidationError: mentions.0  Input should be a valid string
[input_value={'id': '9', 'username': 'bob', ...}]
```

`MESSAGE_CREATE.mentions` is an array of user objects, not id strings. Any message that
mentions anyone fails validation inside the read loop — which, per the note above, kills
the socket.

`mention_roles` *is* a list of snowflake strings, so that one is right.

Note this also affects `MessageAssertion.mentions` (`assertions/message.py:123`) and
`assert_by_mentions`, which compare against id strings. If `Message.mentions` becomes a
list of objects, the comparison needs to map to `.id` — otherwise the assertion silently
never matches.

### 7. `gateway/message.py:43-45` — required fields absent from MESSAGE_UPDATE payloads — **confirmed**

```
ValidationError: 3 validation errors for Message
content / mentions / mention_roles  Field required
```

`content`, `mentions` and `mention_roles` have no defaults, but MESSAGE_UPDATE is a
**partial** payload carrying only what changed. `filter_by_message_update()` is documented
as the way to assert on a deferred command's edit, and `tests/test_core.py:64,114` uses it,
so this path is exercised deliberately.

Fix: default them (`content: str = ""`, `mentions: list[str] = []`,
`mention_roles: list[str] = []`), or model updates separately.

### 8. `gateway/component.py:58` — `ButtonComponent.emoji` typed `str`, discord sends an object — **confirmed**

```
ValidationError: emoji  Input should be a valid string
[input_value={'id': None, 'name': '✅'}]
```

Any button with an emoji on it — extremely common — fails validation. Should be
`Emoji | None`, subject to the next item.

### 9. `shared/emoji.py` — `Emoji` cannot validate a partial emoji object — **confirmed**

```
ValidationError: 2 validation errors for Emoji
roles  Field required
user   Field required
```

`roles: list[str]` and `user: User` are required, but the emoji objects nested in
components and reactions carry only `id`, `name` and sometimes `animated`. So
`SelectOption.emoji` (`gateway/component.py`) fails on any select option with an emoji.

`User` is likewise all-required (`mfa_enabled`, `bio`, `banner`, `accent_color`, …), so it
will not validate the trimmed user objects discord nests either — the same class of bug
that `MessageAuthor` was introduced to avoid.

Fix: default `roles` and `user` to `None`/`[]`, and add `animated: bool | None = None`.

### 10. `requests/commands.py:340` — `compile()` sends the subcommand as the top-level command — **confirmed**

```
data.name='click_for_attendance'   # parent command was 'attendance'
```

`ApplicationCommandBuilder.compile` passes `self.main_command`, but after
`set_main_command` that is the *nested* command. The parent (`self.data`), which holds the
subcommand in its `options`, is discarded.

Two consequences:

* the payload no longer describes a subcommand invocation at all
* `_prepare_app_command` looks up `self.data.name` — now the subcommand's name — in the
  command index, so it raises `SelfBotRequestSetupError: No command with name
  click_for_attendance` even though the parent was indexed fine

Should be `self.data`. Note `tests/test_core.py:121` is a `set_main_command` case, so this
is on the path the new test exercises.

### 11. `assertions/autocomplete.py:37` — the non-exact choice check passes wrong results — **confirmed**

```python
if set(self.choices) > set(gateway_event.choices):  # checks if not subset
```

`>` is proper-superset, not "not a subset". Expected `{A}` against a response of `{B}`
gives `{A} > {B} == False`, so the assertion **passes** on a completely wrong response.
Reproduced: an assertion expecting `expected` accepted a response of only `other`.

Should be `if not set(self.choices) <= set(gateway_event.choices):`.

### 12. `requests/commands.py:30` — `INTERACTION_TIMEOUT = 5000` is seconds, not milliseconds — **confirmed by reading**

```python
await asyncio.wait_for(..., timeout=INTERACTION_TIMEOUT)
```

`asyncio.wait_for` takes seconds, so this waits **83 minutes** for the
INTERACTION_SUCCESS/FAILURE dispatch. The value and name both read as milliseconds.

An interaction whose acknowledgement never arrives therefore hangs the test run rather
than failing it — and it hangs past any assertion deadline, since this wait happens inside
`send`, before the assertion starts waiting on its own. Should be `5`, or be divided by
1000 at the call site.

### 13. `requests/component.py:36` — DM messages produce the literal string `"None"` as guild_id — **confirmed**

```
press_button(dm_message, "Go").guild_id == 'None'
```

`_build` computes `guild_id = None` for a DM, then `_build_interaction` does
`str(guild_id)`. `Interaction.guild_id` is a required `str`, so the None survives as the
four-character string `"None"` and is posted to discord.

Fix: make `Interaction.guild_id` `str | None = None` and let `exclude_none=True` drop it,
which is what discord expects for a DM interaction.

### 14. `gateway/ws.py:230` — `self._ws` may not exist in the `finally` — **confirmed**

```
AttributeError: 'Gateway' object has no attribute '_ws'
```

`_ws` is only assigned at line 153, inside the `async with session.ws_connect(...)`. If the
connect itself fails — no network, DNS failure, discord returning a non-101 — the
`except`/`finally` runs with `_ws` unset, and the `AttributeError` raised in `finally`
**replaces the original exception**, so the real cause is lost and
`Bot._ws_error` holds an `AttributeError` instead.

Fix: declare `_ws: aiohttp.ClientWebSocketResponse | None = None` on the class, or set it
in `__init__`.

### 15. `requests/commands.py:213-218` — interaction status entries leak on timeout

`_interaction_status_events` is a `defaultdict`, so merely reading
`[self.nonce]` creates the entry. If the `wait_for` times out (or the request raises
earlier), the `del` and `pop` never run and both dicts grow for the life of the `Bot`.

Fix: wrap in `try/finally`, and discard both entries there.

---

## Leftovers and lower confidence

### 16. `requests/commands.py:215` and `gateway/ws.py:172` — debug prints left in

```python
print("WOW")            # commands.py:215
print(f"DATA {data}")   # ws.py:172
```

`ws.py:172` prints **every gateway payload** to stdout, duplicating the `logging.debug`
immediately above it. The commit `8c6fe61 remove the cheeky print` removed one of these;
these two came back.

### 17. `requests/commands.py:343` — `submit_modal` is a stub returning `None`

```python
def submit_modal(...) -> Interaction:
    return
```

Declared to return `Interaction`, returns `None`. At `HEAD` it had a body; the refactor
gutted it but left the definition behind. It is no longer exported and
`ModalResponseBuilder.compile` supersedes it, so it looks like dead code to delete.

Same story for `ApplicationCommandBuilder`: `HEAD` had a `compile() -> ApplicationCommand`
alongside `build_app_command`, and the two were merged into today's
`compile(application_id, guild_id, channel_id)`.

### 18. `gateway/_base.py:112-127` — dead duplicate of `PROPERTIES` / `WEBSOCKET_URL`

Both constants are defined identically in `_base.py` and in `ws.py`, and only `ws.py`'s
copy is used. Two copies of the client fingerprint will drift. Annotated in place; worth
deleting from `_base.py` once nothing imports them from there.

### 19. `assertions/modal.py:37` — `self.modal_filter.nonce` on an optional field

`modal_filter` is typed `ModalFilter | None` and assigned through unconditionally. The
builder always supplies one, so this cannot fire today, but it is a type error and would
become an `AttributeError` if a `ModalAssertion` were ever constructed directly.

### 20. `requests/commands.py:208` — the ack posts the nonce where a message id belongs

```python
ACK_URL = ".../channels/{}/messages/{}/ack"
res = await session.post(ACK_URL.format(self.channel_id, self.nonce), ...)
```

A non-200 raises, so if discord rejects an ack for a nonce that is not a real message id
this fails the request. Plausible for MESSAGE_COMPONENT and MODAL_SUBMIT, where the nonce
is not the id of anything that exists yet. **Unverified** — needs a live run to say whether
discord tolerates it. Flagging because the new component/modal paths reach it and the
existing app-command path may simply have been lucky.

### 21. `gateway/ws.py:120-128` — heartbeat opcode and sequence look wrong

Sends `op: 40` with a hardcoded `"seq": 15`, rather than the documented heartbeat `op: 1`
with the last received sequence number. **Unverified**, and it evidently keeps connections
alive in practice, so this may be a deliberate client-specific frame. Noting it because a
fixed `seq` cannot be right across a session, and a silently-failing heartbeat shows up as
a socket that dies after a few minutes.

### 22. `requests/commands.py:314` — `set_arg` labels arguments with `ApplicationCommandType`

Leaf arguments are given `type=ApplicationCommandType.MESSAGE` (3). Discord's *option*
types are a different enum, in which 3 happens to be `STRING` — so it works by coincidence,
as does `CHAT_INPUT` (1) coinciding with `SUB_COMMAND`. It follows that a non-string
`set_arg` value (the signature accepts `bool | int | float`) is still labelled as a string,
which discord may reject. Worth a dedicated option-type enum.

### 23. Stale docstring left by the `compile_request` rename — **fixed**

`ModalResponseBuilder`'s class docstring still showed
`.compile_request(GUILD_ID, CHANNEL_ID)` after the method was merged into `compile`.
Corrected in place, since it was the one example a reader would copy.

### 24. `re.match` versus `re.search` in the content and title assertions

`assert_by_message_content` and `assert_by_modal_title` are named "search pattern" but use
`re.match`, which anchors at the start. Documented as-is rather than changed, since
`tests/test_core.py:72` relies on the anchored behaviour — but the naming invites the
wrong expectation.

### 25. Minor

* `assertions/message.py:183-188` — `assert_request` mutates `self.message_filter`, so a
  compiled assertion reused across two requests keeps the first nonce.
* `requests/component.py:39` — `message.application_id or message.author.id` is guarded by
  an `assert`, which vanishes under `python -O`; and it yields a `str` for a parameter
  typed `int`.
* `requests/component.py:120` — `f"Dropdown {dropdown or selected.custom_id!r} is disabled"`
  binds `!r` to the second operand only, so the name prints unquoted in the common case.
* `requests/modal.py:334-350` — in `_missing_required`, `label` persists across loop
  iterations, so a required component following a `LabelComponent` sibling is reported
  under that sibling's label. Error-message only.
* `bot.py:96` — `RuntimeError(f"Websocket died")` is an f-string with no placeholders, and
  drops the underlying cause from the message (it is still chained via `from`).
* `pyproject.toml` — `[project.optional-dependencies] dev` duplicates
  `[dependency-groups] dev` with different pins (`pytest>=8.0` vs `>=9.1.1`).
* `pyproject.toml` declares `0.4.0` while `dist/` holds `0.0.1` artifacts.
* `gateway/ws.py:192-199` — `case "READY"` rebinds `data` to `data["d"]`, shadowing the
  envelope; harmless today but a trap for anything added after it in that branch.

---

## Suggested order

1. Items 1–3 — nothing runs until the package imports.
2. Items 4–9 — validation and filter bugs; each one kills the websocket, so they present as
   "websocket died" rather than as the schema mismatch they are.
3. Items 10–12 — wrong payloads and a silently-passing assertion, the ones most likely to
   produce a green test run that proves nothing.
4. The rest as cleanup.
