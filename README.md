# Lexa & Friends — AI Pet Care Assistant

An AI-powered pet care planning app built with Streamlit. Instead of filling out forms, you chat with an AI assistant that creates pet profiles, generates personalised care plans, schedules tasks, and checks its own work — all in one conversation.

---

## What it does

- **Chat-first interface** — tell the AI about your pet in plain English; it handles everything else
- **AI agentic loop** — the agent plans, acts, then verifies its own output before responding
- **Care plan generation** — describe your pet and the AI generates a full daily task list
- **Smart scheduling** — tasks are scheduled around your available time budget with conflict detection
- **Conflict resolution** — the AI (or a single button click) fixes overlapping task times automatically
- **Persistent data** — your pets and tasks survive browser refresh via local JSON storage
- **Progress tracking** — mark tasks complete, watch progress bars update in real time

---

## Tech stack

| Layer | Choice |
|---|---|
| UI | Streamlit |
| AI | Groq API + `llama-3.3-70b-versatile` |
| Persistence | JSON (`pawpal_data.json`) |
| Logging | Python `logging` → `lexa.log` |
| Tests | pytest |
| Env vars | python-dotenv |

---

## Setup

### 1. Clone the repository

```bash
git clone <repo-url>
cd ai-pet-care-assistant
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate      # macOS / Linux
.venv\Scripts\activate         # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Get a Groq API key

1. Go to [console.groq.com](https://console.groq.com) and sign up (free)
2. Create an API key under **API Keys**

### 5. Create a `.env` file

In the project root, create a file named `.env`:

```
GROQ_API_KEY=gsk_your_key_here
```

This file is gitignored — it will never be committed.

### 6. Run the app

```bash
streamlit run app.py
```

The app opens in your browser at `http://localhost:8501`.

---

## How to use

1. **Set up an owner** — enter your name and daily time budget in the sidebar, then click **Save Owner**
2. **Open the AI Assistant tab** — this is the primary interface
3. **Tell the AI about your pet** — for example:
   - *"Add my dog Bella, she's a 3-year-old golden retriever who needs daily walks and takes thyroid medication"*
   - *"Generate a full care plan for Bella"*
   - *"Change Bella's morning walk to 30 minutes"*
4. **View Today's Schedule** — the schedule auto-generates after every AI action
5. **Fix conflicts** — if tasks overlap, click **Fix Conflicts Automatically** or ask the AI to optimize the schedule
6. **Track progress** — mark tasks complete in the **Track Progress** tab

---

## Running tests

```bash
pytest tests/ -v
```

36 tests across three files:

| File | Tests | Covers |
|---|---|---|
| `test_pet_planner.py` | 17 | Scheduling, recurrence, conflict detection |
| `test_agent_tools.py` | 14 | All 8 agent tools, duplicate prevention, error cases |
| `test_persistence.py` | 5 | JSON round-trip, missing file, date serialization, corrupt file |

---

## Logging

The app writes a detailed log to **`lexa.log`** in the project root. The file is created automatically on first run and is gitignored.

### Log levels

| Level | Where | What is recorded |
|---|---|---|
| `DEBUG` | File only | Every LLM API call, iteration number, tool dispatch details, full tool results |
| `INFO` | File only | User messages, each tool call and result, pet/task mutations, schedule generation, save events |
| `WARNING` | File + console | Duplicate pet or task rejected, pet or task not found |
| `ERROR` | File + console | JSON parse failures, unhandled exceptions with full traceback |

### Watch logs in real time

Open a second terminal while the app is running:

```bash
tail -f lexa.log
```

### Sample log output

```
2026-04-26 14:32:01 | lexa.app                | INFO     | app startup: loaded 1 owner(s) from disk
2026-04-26 14:32:15 | lexa.app                | INFO     | app: invoking agent for owner='Olena' — message: add my cat Luna...
2026-04-26 14:32:15 | lexa.agent              | INFO     | run_agent: START — owner='Olena', pets=0, tasks=0 | message: add my cat Luna...
2026-04-26 14:32:16 | lexa.agent              | DEBUG    | run_agent: iteration 1 — sending 3 messages to LLM
2026-04-26 14:32:17 | lexa.agent              | DEBUG    | run_agent: iteration 1 — LLM responded in 843ms | finish_reason=tool_calls | tool_calls=1
2026-04-26 14:32:17 | lexa.agent              | INFO     | run_agent: tool call — create_pet({'name': 'Luna', 'species': 'cat', ...})
2026-04-26 14:32:17 | lexa.agent              | INFO     | create_pet: created 'Luna' (cat, domestic shorthair, 2yo, grey) for owner 'Olena'
2026-04-26 14:32:18 | lexa.agent              | INFO     | run_agent: no more tool calls at iteration 3 — final response: I've added Luna...
2026-04-26 14:32:18 | lexa.app                | INFO     | app: auto-saved after agent action — owner='Olena'
2026-04-26 14:32:18 | lexa.app                | INFO     | app: auto-regenerated schedule for 'Olena' (5 slots)
```

### Log file location

```
ai-pet-care-assistant/
  lexa.log    ← created here automatically (gitignored)
```

---

## Project structure

```
ai-pet-care-assistant/
  pet_planner_system.py    — core dataclasses (Owner, Pet, Task) and Scheduler
  persistence.py           — JSON save/load with deduplication on load
  agent.py                 — agentic loop, 8 tool functions, logging setup
  app.py                   — Streamlit UI (5 tabs, AI-first)
  main.py                  — CLI demo
  requirements.txt
  .env                     — gitignored — add your GROQ_API_KEY here
  lexa.log                 — gitignored — runtime log, created on first run
  tests/
    conftest.py
    test_pet_planner.py
    test_agent_tools.py
    test_persistence.py
```

---

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes | Your Groq API key from console.groq.com |
