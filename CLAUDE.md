# Lexa & Friends — Project Intelligence

## What we are building
A Streamlit pet care planning app where an AI agent is the primary interface.
The owner types in a chat window — the agent creates pets, generates care plans,
adds tasks, and validates its own work. No manual forms for pet/task creation.
The existing tabs (schedule, progress, task list) are for viewing and acting on
data the agent populated.

Owner: Olena Molla (albemoll18@gmail.com)

---

## Current Phase: Working MVP (agent + JSON persistence + Groq)

Done:
- AI agentic loop with 8 tools, self-verification, self-correction
- JSON persistence (auto-load on startup, auto-save after every action)
- Full Streamlit UI with AI Assistant as primary tab
- 36 passing tests across 3 test files
- Schedule conflict optimizer (agent tool + UI button)
- Python logging to `lexa.log` — DEBUG/INFO/WARNING/ERROR across agent and app

Deferred: Supabase/database, user authentication, multi-step UI forms.

---

## Tech Stack

| Layer | Choice | Reason |
|---|---|---|
| UI | Streamlit | Already built, session state works well |
| AI | Groq SDK (`groq>=0.11`) + llama-3.3-70b-versatile | Free tier, fast, reliable tool use |
| Persistence | JSON (`pawpal_data.json`) | No infrastructure needed |
| CLI output | `rich>=13.0` | Color tables and panels for main.py |
| Tests | `pytest>=7.0` | Already in use |
| Env vars | `python-dotenv>=1.0` | Load GROQ_API_KEY from .env |

API provider history: tried Anthropic (no credits), Gemini 2.5 Flash (rate limits), switched to Groq (free, working).

---

## Architecture: The Agentic Loop

The agent uses Groq tool use (function calling) with llama-3.3-70b-versatile.
It calls real Python functions that mutate in-memory application state.

### The loop (per user message)
1. Build system prompt: current owner + all pets + all tasks injected as context
2. Send message + tool schemas to Groq
3. Execute whichever tools the model calls (real Python mutations on Owner/Pet/Task)
4. Feed tool results back into the conversation
5. Model calls verification tool (list_tasks or get_pet_info) to check its work
6. If mismatch → model calls correction tool (self-correction step)
7. Loop continues until model stops calling tools (max 10 iterations)
8. Return final natural-language response to user
9. app.py auto-saves and auto-regenerates schedule, then st.rerun()

### Tool registry

| Tool | What it does |
|---|---|
| `create_pet` | Adds Pet to owner. Rejects duplicates by name. |
| `add_task` | Adds Task to pet. Rejects duplicates by name — redirects to update_task. |
| `generate_care_plan` | Sub-calls LLM to generate JSON task list for a pet description, then calls add_task for each. |
| `list_tasks` | Read-only. Used for self-verification after mutations. |
| `get_pet_info` | Read-only. Used for self-verification after create_pet. |
| `update_task` | Modifies task fields (duration, priority, recurrence, preferred_time, etc.). |
| `delete_task` | Removes task from pet. |
| `optimize_schedule` | Detects time conflicts; moves lower-priority tasks to start after the blocking task ends. Up to 3 rounds. Also callable directly from UI "Fix Conflicts" button. |

### Self-verification rule (enforced in system prompt)
After every mutation, model MUST call a read-only tool to verify.
If result doesn't match intent → correct immediately.
Model is instructed to summarise ONLY what it changed, not the full profile state.

---

## Persistence (JSON)

File: `pawpal_data.json` at project root (gitignored).
Module: `persistence.py`

- `save_owners(owners, path)` — serialises Owner → Pet → Task graph to JSON
- `load_owners(path)` — deserialises; returns {} on missing/corrupt file
- `date` fields: ISO 8601 strings; `None` → JSON null
- Auto-loaded on app startup in session state init
- Auto-saved after every agent action and every task completion click

---

## UI Structure (current state)

### Sidebar
- Owner name + time budget slider + Save Owner button
- Switch Owner dropdown
- Pet summary list (read-only, managed by agent)
- Save Data button

### Tabs (in order)
1. **AI Assistant** — chat interface, primary data entry point
2. **Today's Schedule** — generate/view plan, conflicts, reasoning expander
3. **Track Progress** — progress bars, mark complete (reruns on both partial and full completion)
4. **All Tasks** — filterable table by pet and status
5. **All Owners** — side-by-side overview with schedule summaries

### Auto-behaviours
- After every agent message: auto-save JSON + auto-regenerate schedule + st.rerun()
- After marking task complete: auto-save + st.rerun() (both partial and full completion)

---

## File Structure

```
ai-pet-care-assistant/
  pet_planner_system.py    — unchanged core dataclasses + Scheduler
  persistence.py           — JSON save/load
  agent.py                 — Groq tool use agentic loop + 8 tool functions + logging setup
  app.py                   — Streamlit UI (5 tabs, AI-first) + app-level logging
  main.py                  — CLI demo (not yet updated with rich output)
  requirements.txt         — groq, streamlit, rich, python-dotenv, pytest, tabulate
  .env                     — gitignored, contains GROQ_API_KEY
  .gitignore               — .env, pawpal_data.json, lexa.log, .venv, __pycache__, etc.
  CLAUDE.md                — this file
  README.md                — setup guide, usage, logging instructions
  explanation.md           — original project brief (do not modify)
  lexa.log                 — runtime log file (gitignored, created automatically on first run)
  tests/
    conftest.py            — sys.path fix so imports work from any directory
    test_pet_planner.py    — 17 original scheduling tests (do not modify)
    test_agent_tools.py    — 14 tests for all 7 tool functions (no API calls)
    test_persistence.py    — 5 JSON round-trip tests
```

---

## Testing

Run all: `pytest tests/ -v` → 36 tests, all pass.

| File | Count | What it covers |
|---|---|---|
| test_pet_planner.py | 17 | Scheduling, recurrence, conflicts, filtering — do not modify |
| test_agent_tools.py | 14 | Each tool in isolation, duplicate rejection, error cases |
| test_persistence.py | 5 | Round-trip, missing file, date serialization, null date, corrupt file |

---

## Environment Variables (.env — never commit)

```
GROQ_API_KEY=gsk_...
```

---

## Logging

Module: `agent.py` sets up the `lexa` logger hierarchy on first import.
File: `lexa.log` at project root (gitignored, created automatically).

| Level | Destination | What is captured |
|---|---|---|
| DEBUG | File only | Every LLM call, iteration count, tool dispatch, full tool results (truncated 300 chars) |
| INFO | File only | User message, each tool call + result, pet/task mutations, schedule events, save events |
| WARNING | File + console | Duplicate rejected, pet/task not found |
| ERROR | File + console | JSON parse failures, unhandled exceptions with traceback |

To watch in real time while the app runs:
```bash
tail -f lexa.log
```

Logger names: `lexa.agent` (agentic loop + tools), `lexa.app` (Streamlit UI events).

---

## Key Decisions (do not revisit without user confirmation)

- **Groq over Anthropic/Gemini**: Anthropic had no credits; Gemini hit rate limits; Groq free tier works reliably
- **llama-3.3-70b-versatile**: best Groq model for tool use quality
- **No Supabase/database**: JSON sufficient for prototype scope
- **No user auth**: deferred
- **Agent is the only way to add/edit pets and tasks**: sidebar forms removed
- **Duplicate prevention in tools**: add_task and create_pet both guard against duplicates
- **Auto-schedule regeneration**: schedule rebuilds after every agent action so Today's Schedule tab is always current
- **Streamlit kept**: rewrite to React/FastAPI deferred, sufficient for MVP
- **Python logging over print**: file-based DEBUG log + console WARNING+; file gitignored so it never pollutes the repo

---

## Known Gaps / Next Steps

- UI redesign (multi-step pet onboarding, owner profile screen) — deferred
- Supabase auth + database — deferred
- main.py rich output improvements — low priority, not yet done
- Agent integration tests with mocked Groq — stretch goal
- Log rotation (currently lexa.log grows unbounded) — low priority for MVP
