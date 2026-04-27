# PawPal+ — Project Intelligence

## What we are building
A Streamlit pet care planning app where an AI agent is the primary interface.
The owner types in a chat window — the agent creates pets, generates care plans,
adds tasks, and validates its own work. No manual forms for pet/task creation.
The existing tabs (schedule, progress, task list) are for viewing and acting on
data the agent populated.

Owner: Olena Molla (albemoll18@gmail.com)

---

## Current Phase: Agent + JSON persistence (no auth, no database)

Deferred to later: Supabase, user authentication, multi-step UI forms.
Focus right now: working AI agent + JSON save/load so data survives refresh.

---

## Tech Stack

| Layer | Choice | Reason |
|---|---|---|
| UI | Streamlit | Already built, session state works well |
| AI | Anthropic SDK (`anthropic>=0.28`) with tool use | Claude Sonnet 4.6, tool calling for agentic loop |
| Persistence | JSON (`pawpal_data.json`) | No infrastructure needed, sufficient for prototype |
| CLI output | `rich>=13.0` | Color tables and panels for main.py |
| Tests | `pytest>=7.0` | Already in use |
| Env vars | `python-dotenv>=1.0` | Load ANTHROPIC_API_KEY from .env |

---

## Architecture: The Agentic Loop

The agent uses Claude **tool use** (function calling). Claude does not just advise —
it calls real Python functions that mutate in-memory application state.

### The loop (per user message)
1. User types anything in the chat input
2. Build context: current owner + all pets + all tasks → injected into system prompt
3. Call Claude with tool_use enabled, passing the tool registry
4. Claude returns one or more tool_use blocks → execute each tool (real Python calls)
5. Return tool results back to Claude
6. Claude calls verification tool (`list_tasks` or `get_pet_info`) to check its own work
7. If result does not match intent → Claude calls a correction tool (self-correction step)
8. Stream final natural language response to user
9. `st.rerun()` so all other tabs reflect the updated state

### Tool registry (functions Claude can call)

| Tool | What it does |
|---|---|
| `create_pet(name, species, breed, age, color, special_instructions)` | Adds a new Pet to the owner |
| `add_task(pet_name, task_name, category, duration, priority, frequency, recurrence, preferred_time)` | Creates and adds a Task to a pet |
| `generate_care_plan(pet_name, description)` | Asks Claude (sub-prompt) to decide appropriate tasks for a pet type/age/conditions, then calls add_task for each |
| `list_tasks(pet_name)` | Returns current task list — used for self-verification |
| `get_pet_info(pet_name)` | Returns pet summary — used for self-verification |
| `update_task(pet_name, task_name, **kwargs)` | Modifies task fields |
| `delete_task(pet_name, task_name)` | Removes a task from a pet |

### Example: care plan generation (Option A)
Owner says: "Add Bella, 3yo golden retriever, needs daily exercise, takes thyroid meds"
1. Claude calls `create_pet(name="Bella", species="dog", breed="Golden Retriever", age=3, ...)`
2. Claude calls `generate_care_plan(pet_name="Bella", description="3yo golden retriever, daily exercise, thyroid meds")`
   - Sub-prompt determines: morning walk 30min, evening walk 20min, meds 5min daily, grooming 20min weekly, enrichment 15min
3. Claude calls `add_task(...)` for each recommended task
4. Claude calls `list_tasks("Bella")` → verifies count and fields match intent
5. Reports full profile to owner for review/confirmation

### Example: natural language task management (Option C)
Owner says: "Milo needs flea medicine every Friday"
1. Claude classifies intent: add_task
2. Extracts fields: pet=Milo, name="Flea medicine", category="meds", recurrence="weekly"
3. Duration not specified → Claude asks ONE clarifying question before acting
4. After clarification → calls `add_task(...)`, then `list_tasks("Milo")` to confirm
5. Reports what was added

### Self-correction rule
After any mutation, Claude MUST call a read-only verification tool.
If the verification result does not match what was requested:
- Claude calls the correction tool (update_task or delete then recreate)
- Re-verifies
- Maximum 2 correction attempts, then reports the discrepancy to the user

---

## Persistence (JSON)

File: `pawpal_data.json` at project root (gitignored).
Module: `persistence.py`

Functions:
- `save_owners(owners: dict[str, Owner], path="pawpal_data.json") -> None`
- `load_owners(path="pawpal_data.json") -> dict[str, Owner]` — returns {} if missing

Auto-load on app startup in session state init block.
Save: sidebar "Save Data" button + auto-save after every agent mutation.

Date fields: stored as ISO 8601 strings ("2026-04-26"), loaded with `date.fromisoformat()`.
None values: stored as JSON null.

---

## UI: What changes and what stays

### What stays (viewing layer — do not touch during agent phase)
- Tab 1: Today's Schedule (generate plan, view slots, conflicts, reasoning)
- Tab 2: Track Progress (progress bars, mark complete)
- Tab 3: All Tasks (filterable table)
- Tab 4: All Owners (overview)

### What changes
- **Sidebar**: strip out pet and task forms entirely. Keep only owner name + time budget + Save Data button.
- **New Tab 5: AI Assistant** — chat interface. This is now the only way to add/edit pets and tasks.
  - Message history displayed above
  - Text input at the bottom
  - Agent response streams in real time
  - After any mutation: `st.rerun()` so other tabs update

### UI redesign (deferred to after agent works)
- Multi-step pet onboarding
- Owner profile / registration screen
- Supabase auth integration

---

## File Structure (target state for current phase)

```
ai-pet-care-assistant/
  pet_planner_system.py    — unchanged (core dataclasses + Scheduler)
  persistence.py           — NEW: save_owners / load_owners (JSON)
  agent.py                 — NEW: tool registry + agentic loop
  app.py                   — MODIFIED: strip pet/task sidebar forms, add AI tab, wire persistence
  main.py                  — MODIFIED: rich color tables (lower priority)
  requirements.txt         — MODIFIED: add anthropic, rich, python-dotenv
  .env                     — user-created, gitignored
  .gitignore               — add .env, pawpal_data.json, __pycache__, .venv
  CLAUDE.md                — this file
  tests/
    conftest.py            — NEW: sys.path fix
    test_pet_planner.py    — existing 17 tests (do not modify)
    test_agent_tools.py    — NEW: tool functions tested in isolation
    test_persistence.py    — NEW: JSON round-trip tests
```

---

## Testing Strategy

### Existing (do not modify)
`tests/test_pet_planner.py` — 17 tests, all pass.

### New: `tests/test_agent_tools.py`
Tests each tool function directly — no Claude API call needed.
- `test_create_pet_adds_to_owner()`
- `test_add_task_correct_fields()`
- `test_add_task_unknown_pet_raises_error()`
- `test_list_tasks_returns_correct_format()`
- `test_delete_task_removes_from_pet()`
- `test_update_task_modifies_field()`

### New: `tests/test_persistence.py`
- `test_save_and_load_round_trip()` — owner + 2 pets + 3 tasks survive save/load
- `test_load_missing_file_returns_empty_dict()`
- `test_date_field_survives_serialization()`
- `test_null_due_date_survives_serialization()`

### Agent integration tests (stretch goal)
Mock the Anthropic client to inject tool_use responses without real API calls.
- `test_agent_creates_pet_on_natural_language_input()`
- `test_agent_self_corrects_after_wrong_task_added()`

---

## Implementation Order (current phase)

1. `tests/conftest.py` — sys.path fix (10 min)
2. `requirements.txt` — add anthropic, rich, python-dotenv (5 min)
3. `persistence.py` + `tests/test_persistence.py` (45 min)
4. `agent.py` — tool registry + agentic loop (3-4 hrs) ← core feature
5. `tests/test_agent_tools.py` (1 hr)
6. `app.py` — wire persistence + add AI Assistant tab + strip sidebar forms (2 hrs)
7. `main.py` — rich output (30 min, lowest priority)

---

## Key Decisions (do not revisit without user confirmation)

- No Supabase/database in current phase — JSON is sufficient
- No user auth in current phase
- Claude Sonnet 4.6 (not Haiku) — quality matters for care plan generation
- Agent is the ONLY way to add/edit pets and tasks — sidebar forms removed
- Agent is advisory + acting: it mutates state AND explains what it did
- Self-verification is mandatory after every mutation (not optional)
- No autonomous mutations without showing the user a summary of what was done

---

## Environment Variables (.env — never commit)

```
ANTHROPIC_API_KEY=sk-ant-...
```
