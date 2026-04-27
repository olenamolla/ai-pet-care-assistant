# Model Card — Lexa & Friends AI Agent

## Model Details

| Field | Value |
|---|---|
| Model used | `llama-3.3-70b-versatile` |
| Provider | Groq API (free tier) |
| Interface | Tool use / function calling (OpenAI-compatible format) |
| Role in app | Primary interface — creates pets, manages tasks, generates care plans, resolves conflicts |
| Max iterations per turn | 10 (hard cap in `run_agent()`) |

---

## Intended Use

Lexa & Friends is designed for a single pet owner managing daily care tasks for one or more pets. The model receives a system prompt containing the full current state (owner, pets, tasks) and responds to natural-language requests by calling structured tool functions that mutate in-memory application state.

**Intended inputs:** conversational descriptions of pets and care needs, task modification requests, schedule questions.

**Intended outputs:** natural-language confirmation of what was done, verified against the actual state via read-only tool calls.

---

## How the Agent Is Prompted

The system prompt is rebuilt before every LLM call and contains:
- The owner's name and daily time budget
- Every pet's profile (species, breed, age, special instructions)
- Every task for every pet (category, duration, priority, recurrence, due date)
- 8 behavioural rules including mandatory self-verification after every mutation

The model is explicitly instructed to summarise only what it changed — not repeat the full state — and to never re-add a pet or task that already exists.

---

## Tools Available to the Model

| Tool | Type | What it does |
|---|---|---|
| `create_pet` | Mutation | Adds a pet; rejects duplicates by name |
| `add_task` | Mutation | Adds a task; rejects duplicates; redirects to `update_task` |
| `update_task` | Mutation | Modifies task fields (duration, priority, time, recurrence) |
| `delete_task` | Mutation | Removes a task from a pet |
| `generate_care_plan` | Mutation + sub-LLM | Calls LLM again to generate a JSON task list, then adds all tasks |
| `optimize_schedule` | Mutation | Detects time conflicts; moves lower-priority tasks; up to 3 rounds |
| `list_tasks` | Read-only | Lists all tasks for a pet — used for self-verification |
| `get_pet_info` | Read-only | Returns pet profile summary — used for self-verification |

---

## Guardrails and Error Handling

- **Duplicate prevention** — `create_pet` and `add_task` both check for existing names before writing and return a clear rejection message to the model
- **Loop cap** — the agentic loop runs at most 10 iterations per user message to prevent runaway behaviour
- **Tool exception handling** — `_execute_tool()` wraps every tool in `try/except`; errors are returned as strings back into the conversation rather than crashing the app
- **Self-verification rule** — the system prompt requires the model to call a read-only tool after every mutation and correct itself if the result does not match intent
- **Persistence safety** — `load_owners()` catches `JSONDecodeError` and `KeyError`; `_dict_to_pet()` deduplicates tasks by name on load in case of legacy corrupt data

---

## Known Limitations

**The model does not reliably follow all instructions on its own.** During development the model was observed to:

- Re-describe the full pet profile after a small change instead of summarising only what changed — required explicit rules and counter-examples in the system prompt
- Attempt to re-add a pet or task that already existed, especially across long multi-turn conversations — required duplicate checking at the tool layer, not just in the prompt
- Skip the self-verification step when handling multiple tool calls in a single turn — required making the verification rule more explicit
- Miss edge cases silently — for example, generating tasks without a `preferred_time` in a way that would later cause scheduling conflicts, without flagging the risk

**The takeaway:** AI agent behaviour requires active engineering, not just prompting. Guardrails, verification loops, and logging all exist because the model cannot be trusted to behave correctly in every case without structural constraints. Manual review of the agent's output is essential — you cannot assume it did exactly what you asked.

---

## Observability

All agent activity is written to `lexa.log` (DEBUG level, gitignored):

- Every LLM call: iteration number, message count, response time, finish reason, tool call count
- Every tool dispatch: tool name, arguments, result (truncated to 300 chars)
- Every mutation: pet created, task added/updated/deleted, schedule generated
- Warnings: duplicate rejected, pet or task not found
- Errors: JSON parse failures, unhandled exceptions with full traceback

---

## Reflection

### What this project taught me about AI

Working with an AI agent as the primary interface — rather than just an autocomplete tool — reveals a fundamental shift in how you design software. Instead of writing code that follows a fixed path, you are writing constraints and verification steps around a system that makes its own decisions. The challenge is not getting the AI to produce output; it is getting it to produce the *right* output consistently.

The most useful mental model I developed: **treat the AI like a capable but overconfident junior developer.** It will complete the task, but it will take shortcuts, miss edge cases, and sometimes do something slightly different from what you asked — without flagging it. Your job as the engineer is to design the guardrails: duplicate prevention in tools, mandatory self-verification steps, a cap on loop iterations, error handling that returns human-readable messages back into the conversation, and a logging system that makes behaviour auditable.

### What this project taught me about problem-solving

Switching API providers three times (Anthropic → Gemini → Groq) under time pressure taught a practical lesson about dependencies: always understand what your critical path relies on, and have a fallback. The architecture — thin agent layer over a stable core domain — made the switch easier because the scheduling logic, persistence, and tests had no dependency on the AI provider at all.

Building incrementally and testing at each step also made a significant difference. When the agent started producing duplicate tasks, the problem was immediately isolatable to the tool layer because the scheduler tests were already passing. Without that foundation, debugging would have been much harder.

The project is not finished — user authentication, database storage, and a multi-step onboarding flow are deferred. But it is a working, tested, observable system that demonstrates the full cycle: design, implement, test, debug, and ship.
