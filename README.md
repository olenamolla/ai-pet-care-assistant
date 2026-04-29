# Lexa & Friends — AI Pet Care Assistant

**An AI-powered pet care planning app where you talk to an assistant instead of filling out forms.**
Tell it about your pet in plain English. It builds the profile, generates a personalised care plan, schedules everything around your time budget, and checks its own work — all in one conversation.

Built as a portfolio project to demonstrate AI agent design, agentic loop implementation, and full-stack Python development.

---

## From PawPal+ to Lexa & Friends — Project Origin

This project started as **PawPal+**, built during Modules 1–3. The original goal was to help a busy pet owner stay consistent with pet care by tracking tasks (walks, feeding, meds, enrichment, grooming), scheduling them within a daily time budget, and explaining the reasoning behind each decision. PawPal+ was a Streamlit app with manual forms for entering owner and pet data, a priority-based scheduling engine, conflict detection, and a 17-test suite covering scheduling, recurrence, and edge cases.

For this module, PawPal+ was extended into **Lexa & Friends** — a fully AI-driven version where the agent replaces all manual forms. Users interact exclusively through a chat interface; the AI creates pets, generates care plans, manages tasks, resolves conflicts, and verifies its own output. The scheduling engine from PawPal+ was preserved entirely and is now driven by the agent rather than the UI.

---

## What This Project Does and Why It Matters

Most productivity apps require users to navigate forms, dropdowns, and settings screens. This project explores a different model: **natural language as the only interface**. You describe your pet the same way you would to a vet, and the system handles the rest.

Key capabilities:
- **Conversational pet setup** — describe your pet in plain text; the agent extracts all structured data and creates the profile
- **AI care plan generation** — describe your pet's lifestyle and the agent generates a full daily task list via a second LLM call
- **Agentic self-verification** — after every action the agent reads back what it just wrote and corrects itself if something is wrong
- **Algorithmic scheduling** — priority-based task fitting, chronological sorting, conflict detection, and automated conflict resolution
- **Persistent data** — everything survives browser refresh via local JSON storage
- **Full observability** — every LLM call, tool use, and state mutation is logged to `lexa.log`

This matters because it demonstrates a complete AI engineering stack: prompt design, tool use, agentic loops, self-correction, error handling, persistence, logging, and testing — not just calling an API and displaying the result.

---

## Architecture Overview

The system has four layers that data flows through in sequence:


![System Diagram](assets/pet-planner.drawio.png)

**State Retriever** (`build_system_prompt`) — before every LLM call, the current owner, pets, and tasks are read from memory and injected into the system prompt as live context. The model always knows the full current state.

**AI Agent** (`run_agent`) — a tool-use loop powered by Groq's `llama-3.3-70b-versatile`. The model decides which of 8 tools to call, the tool executor runs real Python functions that mutate in-memory state, and results are fed back into the conversation. The loop runs up to 10 iterations per user message.

**Self-Evaluator** — after every mutation (add pet, add task, update task), the model is instructed to call a read-only verification tool (`list_tasks` or `get_pet_info`) and compare the result to what it intended. If there is a mismatch, it corrects itself immediately before responding.

**Output layer** — the final natural-language response is shown in chat, the schedule is auto-rebuilt, data is auto-saved to JSON, and every event is written to `lexa.log`.

Human review happens at the output layer: the user reads the response, checks the schedule tab, and marks tasks complete. Automated tests (36, via pytest) validate the scheduling engine and tool functions independently of the LLM.

---

## AI Tools

The Lexa & Friends agent has 8 tools it can call during a conversation. Each tool is a real Python function that directly mutates application state — no simulation, no mock data.

| Tool | Purpose |
|---|---|
| `create_pet` | Adds a new pet to the owner's profile. Rejects duplicates by name. |
| `add_task` | Adds a single care task to a pet. Rejects duplicates — redirects to `update_task` if the task already exists. |
| `update_task` | Modifies fields on an existing task (duration, priority, recurrence, preferred start time). |
| `delete_task` | Removes a task from a pet. |
| `generate_care_plan` | Makes a second LLM call to generate a full JSON task list from a plain-text pet description, then calls `add_task` for each item. |
| `optimize_schedule` | Detects time conflicts between tasks; moves lower-priority tasks to start after the blocking task ends. Runs up to 3 resolution rounds. |
| `list_tasks` | Read-only. Lists all tasks for a pet. Called by the agent after every mutation to verify its own output. |
| `get_pet_info` | Read-only. Returns a pet's profile summary. Called after `create_pet` to verify the pet was created correctly. |

The two read-only tools (`list_tasks`, `get_pet_info`) are the self-verification mechanism — the agent is required by its system prompt to call one of them after every change and correct itself if the result does not match what it intended.

---

## Setup Instructions

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

### 4. Get a free Groq API key

1. Go to [console.groq.com](https://console.groq.com) and sign up (free)
2. Create an API key under **API Keys**

### 5. Create a `.env` file

In the project root, create a file named `.env`:

```
GROQ_API_KEY=gsk_your_key_here
```

This file is gitignored and will never be committed.

### 6a. Run the Streamlit app

```bash
streamlit run app.py
```

Opens in your browser at `http://localhost:8501`. Use the **AI Assistant** tab to interact with the agent.

### 6b. Run the CLI demo (no API key needed)

```bash
python main.py
```

Demonstrates all algorithmic features end-to-end: owner setup, schedule generation, conflict detection, conflict resolution, recurring task completion, and task filtering — with formatted rich output. No Groq API call required.

### 7. Run the tests

```bash
pytest tests/ -v
```

---

## Sample Interactions

🎥 **[Watch the full demo on Loom](https://www.loom.com/share/89dbad4b0cea4948bf49a77e58f2e832)**

🎥 **[CLI demo video and logging file](https://www.loom.com/share/a2e8f39cd02e4f54a07711ca429fd32b)**



## Design Decisions

### Groq over Anthropic and Gemini
The project started targeting the Anthropic API but the account could not purchase credits. It was then switched to Gemini 2.5 Flash, which hit rate limits immediately. Groq was chosen as the final provider — it is free, fast, and its `llama-3.3-70b-versatile` model handles tool use reliably. **Trade-off:** dependency on a third-party free tier with no SLA; for production this would need a paid provider.

### Agent as the only way to add data
Sidebar forms for adding pets and tasks were removed entirely. The agent is the only interface for creating and modifying data. **Trade-off:** the app requires an API key to do anything meaningful, which adds a setup step. The benefit is a much simpler UI and a more natural user experience.

### JSON over a database
Data is saved to `pawpal_data.json` on disk rather than Supabase or SQLite. **Trade-off:** not suitable for multiple simultaneous users or production deployment, but it eliminates all infrastructure setup for a prototype and makes the project fully self-contained.

### Self-verification baked into the system prompt
Rather than trusting the model to produce correct output, the system prompt requires the model to call a read-only tool after every mutation and verify its own work. This was added after observing that the model occasionally skipped tasks or mis-named fields. **Trade-off:** adds 1–2 extra API calls per user message, but catches errors before the user sees them.

### Duplicate prevention at the tool layer, not the UI layer
`create_pet` and `add_task` both check for existing names before writing, and return a clear message to the model if a duplicate is detected. This was necessary because the LLM sometimes re-attempted to add a pet or task that already existed (especially across multi-turn conversations). **Trade-off:** requires careful error message wording so the model understands it should call `update_task` instead.

### Python `logging` module for observability
All agent activity is logged to `lexa.log` at DEBUG level. **Trade-off:** the log file grows without rotation (low priority for MVP), but for development it is invaluable — you can watch every LLM call, tool execution, and timing in real time with `tail -f lexa.log`.

---

## Testing Summary

### What the tests cover

| File | Tests | What it covers |
|---|---|---|
| `test_pet_planner.py` | 17 | Scheduling, priority sort, time budget, recurrence (daily/weekly), conflict detection, edge cases |
| `test_agent_tools.py` | 14 | All 8 agent tool functions in isolation, duplicate rejection, pet-not-found errors |
| `test_persistence.py` | 5 | JSON round-trip, missing file, date serialization, null date, corrupt file |

### What worked

The core scheduling logic is thoroughly covered. Tests for recurrence, conflict detection, and the time-budget greedy algorithm all pass and caught real bugs during development — for example, a boundary condition where a task with exactly the remaining budget was incorrectly dropped. The persistence tests caught a date serialization issue with `None` due dates early on.

### What didn't work as expected

**The AI does not reliably follow all instructions on its own.** This was the most important practical lesson of the project. Even with a detailed system prompt, the model would sometimes:

- Re-describe the entire pet profile after a single small change, instead of summarising only what changed (had to add explicit rules and examples to the prompt)
- Re-add a task that already existed instead of updating it (had to add duplicate checking at the tool layer)
- Skip the self-verification step when it was busy with multiple tool calls (had to make the instruction more explicit)

The AI also does not naturally think about edge cases — for example, it would try to add a task with no `preferred_time` in a format that would later cause a conflict, without flagging this. Some of these issues were fixed in the code; others required prompt engineering.

**The takeaway:** AI-generated code and AI agent behaviour both require careful manual review. The AI can produce code that looks correct but creates duplicates, silently ignores instructions, or handles only the happy path. You cannot assume the model did what you asked — you have to verify it.

### What I learned

Writing tests first (or at least in parallel) forces you to think about edge cases the AI will miss. The 36-test suite caught multiple real bugs. More importantly, it gave confidence when refactoring: when the API provider changed from Anthropic to Gemini to Groq, the test suite confirmed the core logic was still intact without manual re-testing.

---

## Project Structure

```
ai-pet-care-assistant/
  pet_planner_system.py    — core dataclasses (Owner, Pet, Task) and Scheduler
  persistence.py           — JSON save/load with deduplication on load
  agent.py                 — agentic loop, 8 tool functions, logging setup
  app.py                   — Streamlit UI (5 tabs, AI-first)
  main.py                  — CLI demo (no API key needed)
  requirements.txt
  .env                     — gitignored — add your GROQ_API_KEY here
  lexa.log                 — gitignored — runtime log, created on first run
  tests/
    conftest.py            — sys.path fix for pytest
    test_pet_planner.py    — 17 scheduling tests (original PawPal+ suite)
    test_agent_tools.py    — 14 agent tool tests
    test_persistence.py    — 5 JSON round-trip tests
```

---

## Logging

The app writes a detailed log to `lexa.log` in the project root. It is created automatically on first run and is gitignored.

| Level | Where | What is recorded |
|---|---|---|
| `DEBUG` | File only | Every LLM call, iteration count, tool dispatch, full tool results |
| `INFO` | File only | User messages, tool calls and results, mutations, schedule events, saves |
| `WARNING` | File + console | Duplicate rejected, pet or task not found |
| `ERROR` | File + console | JSON parse failures, unhandled exceptions with traceback |

Watch logs in real time while the app runs:

```bash
tail -f lexa.log
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes | Free API key from [console.groq.com](https://console.groq.com) |
