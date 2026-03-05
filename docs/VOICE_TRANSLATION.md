# Voice Translation Layer

A second LLM pass that rewrites RAG responses in the writing style of a specific person (or the whole group), based on a corpus of real group chat messages.

## How It Works

```
User question
     │
     ▼
RAG Pipeline (retrieve → generate)
     │
     ▼ factual response
Voice Translator (retrieve examples → style transfer prompt → LLM)
     │
     ▼ response in target voice
User sees it
```

1. The RAG pipeline runs normally and produces a factual answer.
2. That answer is embedded and used to search for stylistically similar messages from the target person.
3. The retrieved messages become few-shot examples in a style transfer prompt.
4. A second LLM call rewrites the factual answer in the target voice.
5. The translated response streams back to the user.

> **Key design decision:** The RAG *response* (not the user's question) is the embedding query for voice retrieval. This finds examples that are topically similar to the *answer*, making the style transfer more natural.

> **Streaming note:** When voice is active, the RAG step runs synchronously first (to collect the full factual text), then the translation step streams. This causes a brief pause before streaming begins — a necessary trade-off since the translation prompt needs the complete response as input.

---

## App Structure

```
apps/voice/
    models.py               — VoiceMember, VoiceMessage
    translation.py          — VoiceTranslator pipeline
    admin.py                — Admin for members and messages
    views.py                — member_list, member_detail
    urls.py                 — /voice/
    management/commands/
        fetch_groupme.py    — Pull messages from GroupMe API
        import_voice_corpus.py — Embed and store a JSON corpus
        reembed_voice.py    — Re-embed messages after model changes
    templates/voice/
        member_list.html
        member_detail.html
```

---

## Models

### VoiceMember
Represents a person in the group chat.

| Field | Type | Notes |
|---|---|---|
| `name` | CharField (unique) | Raw GroupMe `user_id` — read-only, never edit |
| `display_name` | CharField (blank) | Friendly name shown in UI, set via admin |
| `message_count` | IntegerField | Updated on import |
| `is_active` | BooleanField | Controls visibility in voice selector |

`label` property returns `display_name` if set, falls back to `name`.

### VoiceMessage
An individual message from the corpus, embedded for retrieval.

| Field | Type | Notes |
|---|---|---|
| `member` | FK → VoiceMember | CASCADE |
| `content` | TextField | URL-stripped message text |
| `embedding` | VectorField (768d) | OpenAI `text-embedding-3-small` |
| `original_timestamp` | DateTimeField (nullable) | From GroupMe API |

Messages are stored individually (not chunked) since chat messages are already short.

### Conversation (modified)
Two new fields on the existing `Conversation` model:

| Field | Type | Notes |
|---|---|---|
| `voice` | FK → VoiceMember (nullable) | Active voice for this conversation |
| `voice_blend` | BooleanField | If True, blend all active voices |

---

## Translation Pipeline (`translation.py`)

**`VoiceTranslator`** class:

- **`retrieve_examples(text, member, blend)`** — Embeds the text, runs L2 similarity search against `VoiceMessage`. Filtered by member, or all active members in blend mode. Returns top N examples (default 10, set via `VOICE_NUM_EXAMPLES`).
- **`build_translation_prompt(rag_response, examples, member, blend)`** — Constructs system + user messages for the style transfer. Instructs the LLM to preserve all facts while adopting the voice's tone, slang, and patterns.
- **`translate(rag_response, member, blend, stream)`** — Orchestrates retrieve → prompt → LLM call. Returns original response unchanged if no voice selected (passthrough).

**`RAGPipeline.query_with_voice()`** — Added to `apps/chat/rag.py`. When voice is active it calls `query()` synchronously then pipes the result through `voice_translator.translate()`. Falls through to standard `query()` when no voice is set.

---

## Corpus Pipeline

### Step 1 — Fetch from GroupMe

```bash
python manage.py fetch_groupme \
  --token YOUR_TOKEN \
  --group-id YOUR_GROUP_ID \
  --after-id FIRST_MESSAGE_ID \
  --output /app/groupme_messages.json
```

Paginates the GroupMe API (100 msgs/batch, 0.5s delay), strips URLs from text, uses `user_id` as the stable author identifier. Saves on Ctrl+C. Output is a JSON array:

```json
[
  { "creator": "30837253", "text": "...", "create_date": "2022-12-12T20:21:30+00:00" },
  ...
]
```

### Step 2 — Import & Embed

```bash
python manage.py import_voice_corpus /app/groupme_messages.json \
  --author-field creator \
  --content-field text \
  --timestamp-field create_date
```

Options:
- `--dry-run` — preview stats without writing anything
- `--min-length N` — skip messages shorter than N chars (default: 10)
- `--batch-size N` — embedding API batch size (default: 100)

Idempotent — re-running clears and replaces messages for each member.

### Step 3 — Name your members

After import, VoiceMembers are named with numeric GroupMe user IDs. Set friendly names via Django admin at `/admin/voice/voicemember/`. The `name` field is read-only; set `display_name` instead.

Deactivate any bot/system entries (e.g. `system`, `calendar`) so they don't appear in the selector.

### Re-embedding

If the embedding model changes, re-embed without re-fetching:

```bash
python manage.py reembed_voice                  # all members
python manage.py reembed_voice --member 30837253  # one member
```

---

## Configuration

| Setting | Default | Purpose |
|---|---|---|
| `VOICE_NUM_EXAMPLES` | `10` | Few-shot examples retrieved per translation |

---

## UI

The voice selector lives in the chat conversation header bar. It's a form that auto-submits on change (no extra button needed).

- **Dropdown** — select a specific VoiceMember by display name
- **Group Blend checkbox** — retrieve examples from all active members
- **None** — disables translation, standard RAG response returned
- Active voice shown as a blue badge

Voice selection is stored per-conversation on the `Conversation` model, so each chat can have a different voice.

---

## Production Notes

- **Cost:** ~$0.02–0.05 to embed 91k messages at `text-embedding-3-small` pricing (~$0.02/1M tokens).
- **Time:** ~15–20 minutes to embed a 91k message corpus at batch size 100.
- **Each translated response** adds one extra LLM call (Groq) and one extra embedding call (OpenAI) on top of the normal RAG cost.
- **Latency:** Voice adds ~1–3s before streaming begins (synchronous RAG step + example retrieval + translation LLM warmup).
