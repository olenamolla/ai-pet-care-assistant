import json
import logging
import os
import time
from datetime import date

from groq import Groq
from dotenv import load_dotenv

from pet_planner_system import Owner, Pet, Task, Scheduler, PRIORITY_ORDER

load_dotenv()

# ── Logging setup ─────────────────────────────────────────────────────────────
# File handler attached once to the "lexa" hierarchy; child loggers inherit it.
# File: DEBUG (everything). Console: WARNING+ only (avoids Streamlit noise).
_lexa_logger = logging.getLogger("lexa")
if not _lexa_logger.handlers:
    _lexa_logger.setLevel(logging.DEBUG)

    _fh = logging.FileHandler("lexa.log", encoding="utf-8")
    _fh.setLevel(logging.DEBUG)
    _fh.setFormatter(logging.Formatter(
        "%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    _lexa_logger.addHandler(_fh)

    _ch = logging.StreamHandler()
    _ch.setLevel(logging.WARNING)
    _ch.setFormatter(logging.Formatter("%(levelname)s [%(name)s] %(message)s"))
    _lexa_logger.addHandler(_ch)

logger = logging.getLogger("lexa.agent")

# ── Tool schemas (OpenAI / Groq format) ───────────────────────────────────────

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "create_pet",
            "description": "Add a new pet to the owner's profile. After calling this, always call get_pet_info to verify.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "species": {"type": "string", "enum": ["dog", "cat", "bird", "rabbit", "other"]},
                    "breed": {"type": "string"},
                    "age": {"type": "integer"},
                    "color": {"type": "string"},
                    "special_instructions": {"type": "string"},
                },
                "required": ["name", "species", "breed", "age", "color"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_task",
            "description": "Add a single care task to a pet. After adding all tasks, call list_tasks to verify.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pet_name": {"type": "string"},
                    "task_name": {"type": "string"},
                    "category": {"type": "string", "enum": ["walk", "feeding", "meds", "enrichment", "grooming"]},
                    "duration": {"type": "integer", "description": "Minutes per occurrence"},
                    "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                    "frequency": {"type": "integer", "description": "Times per day, default 1"},
                    "recurrence": {"type": "string", "enum": ["none", "daily", "weekly"]},
                    "preferred_time": {"type": "string", "description": "Optional HH:MM start time"},
                },
                "required": ["pet_name", "task_name", "category", "duration", "priority"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_care_plan",
            "description": "Generate and add a full recommended set of care tasks for a pet from a plain-text description. After calling this, always call list_tasks to verify.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pet_name": {"type": "string"},
                    "description": {"type": "string", "description": "Free-text: breed, age, health, lifestyle, special needs"},
                },
                "required": ["pet_name", "description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": "List all tasks for a pet. Use after adding or modifying tasks to verify.",
            "parameters": {
                "type": "object",
                "properties": {"pet_name": {"type": "string"}},
                "required": ["pet_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pet_info",
            "description": "Get a summary of a pet's profile. Use after creating a pet to verify.",
            "parameters": {
                "type": "object",
                "properties": {"pet_name": {"type": "string"}},
                "required": ["pet_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_task",
            "description": "Modify one or more fields of an existing task for a pet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pet_name": {"type": "string"},
                    "task_name": {"type": "string"},
                    "duration": {"type": "integer"},
                    "priority": {"type": "string", "enum": ["high", "medium", "low"]},
                    "frequency": {"type": "integer"},
                    "recurrence": {"type": "string", "enum": ["none", "daily", "weekly"]},
                    "preferred_time": {"type": "string"},
                },
                "required": ["pet_name", "task_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_task",
            "description": "Remove a task from a pet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pet_name": {"type": "string"},
                    "task_name": {"type": "string"},
                },
                "required": ["pet_name", "task_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "optimize_schedule",
            "description": (
                "Detect and automatically resolve time conflicts in the schedule. "
                "Higher-priority tasks keep their slots; lower-priority tasks are "
                "moved to start immediately after the conflicting task ends. "
                "Call this when the user reports conflicts or asks to fix/optimize the schedule."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "day_start": {
                        "type": "string",
                        "description": "Day start time in HH:MM format, default '08:00'",
                    },
                },
                "required": [],
            },
        },
    },
]


# ── Tool execution functions ───────────────────────────────────────────────────

def _find_pet(owner: Owner, pet_name: str) -> Pet:
    for pet in owner.pets:
        if pet.name.lower() == pet_name.lower():
            return pet
    raise ValueError(f"Pet '{pet_name}' not found. Available: {[p.name for p in owner.pets]}")


def _tool_create_pet(owner: Owner, name: str, species: str, breed: str,
                     age: int, color: str, special_instructions: str = "") -> str:
    for p in owner.pets:
        if p.name.lower() == name.lower():
            logger.warning("create_pet: duplicate rejected — '%s' already exists for owner '%s'", name, owner.name)
            return f"Pet '{name}' already exists."
    owner.add_pet(Pet(
        name=name, species=species, breed=breed,
        age=int(age), color=color, special_instructions=special_instructions,
    ))
    logger.info("create_pet: created '%s' (%s, %s, %syo, %s) for owner '%s'",
                name, species, breed, age, color, owner.name)
    return f"Created pet '{name}' ({species}, {breed}, {age}yo, {color})."


def _tool_add_task(owner: Owner, pet_name: str, task_name: str, category: str,
                   duration: int, priority: str, frequency: int = 1,
                   recurrence: str = "none", preferred_time: str = None) -> str:
    try:
        pet = _find_pet(owner, pet_name)
    except ValueError as e:
        logger.warning("add_task: pet lookup failed — %s", e)
        return str(e)
    for existing in pet.tasks:
        if existing.name.lower() == task_name.lower():
            logger.warning("add_task: duplicate rejected — '%s' already exists on '%s'", task_name, pet_name)
            return f"Task '{task_name}' already exists for {pet.name}. Use update_task to change it."
    pet.add_task(Task(
        name=task_name, category=category, duration=int(duration),
        priority=priority, frequency=int(frequency), recurrence=recurrence,
        due_date=date.today() if recurrence != "none" else None,
        preferred_time=preferred_time,
    ))
    rec = f", repeats {recurrence}" if recurrence != "none" else ""
    logger.info("add_task: added '%s' to '%s' (%s, %smin, %s%s)",
                task_name, pet_name, category, duration, priority, rec)
    return f"Added '{task_name}' to {pet.name} ({category}, {duration}min, {priority}{rec})."


def _tool_list_tasks(owner: Owner, pet_name: str) -> str:
    try:
        pet = _find_pet(owner, pet_name)
    except ValueError as e:
        logger.warning("list_tasks: pet lookup failed — %s", e)
        return str(e)
    if not pet.tasks:
        logger.debug("list_tasks: '%s' has no tasks", pet_name)
        return f"{pet.name} has no tasks yet."
    lines = [f"{pet.name}'s tasks ({len(pet.tasks)} total):"]
    for t in pet.tasks:
        due = f" | due {t.due_date}" if t.due_date else ""
        pt = f" | at {t.preferred_time}" if t.preferred_time else ""
        lines.append(f"  - {t.name}: {t.category}, {t.duration}min, {t.priority}, {t.recurrence}{due}{pt}")
    logger.debug("list_tasks: returning %d tasks for '%s'", len(pet.tasks), pet_name)
    return "\n".join(lines)


def _tool_get_pet_info(owner: Owner, pet_name: str) -> str:
    try:
        pet = _find_pet(owner, pet_name)
    except ValueError as e:
        logger.warning("get_pet_info: pet lookup failed — %s", e)
        return str(e)
    result = f"{pet.summary()} | {len(pet.tasks)} task(s)"
    logger.debug("get_pet_info: '%s' — %s", pet_name, result)
    return result


def _tool_update_task(owner: Owner, pet_name: str, task_name: str, **kwargs) -> str:
    try:
        pet = _find_pet(owner, pet_name)
    except ValueError as e:
        logger.warning("update_task: pet lookup failed — %s", e)
        return str(e)
    for task in pet.tasks:
        if task.name.lower() == task_name.lower():
            task.update(**kwargs)
            logger.info("update_task: updated '%s' on '%s' with %s", task_name, pet_name, kwargs)
            return f"Updated '{task_name}' for {pet.name}: {kwargs}"
    logger.warning("update_task: task '%s' not found on '%s'", task_name, pet_name)
    return f"Task '{task_name}' not found for {pet.name}."


def _tool_delete_task(owner: Owner, pet_name: str, task_name: str) -> str:
    try:
        pet = _find_pet(owner, pet_name)
    except ValueError as e:
        logger.warning("delete_task: pet lookup failed — %s", e)
        return str(e)
    for task in pet.tasks:
        if task.name.lower() == task_name.lower():
            pet.remove_task(task)
            logger.info("delete_task: removed '%s' from '%s'", task_name, pet_name)
            return f"Deleted task '{task_name}' from {pet.name}."
    logger.warning("delete_task: task '%s' not found on '%s'", task_name, pet_name)
    return f"Task '{task_name}' not found for {pet.name}."


def _tool_generate_care_plan(owner: Owner, pet_name: str, description: str) -> str:
    try:
        pet = _find_pet(owner, pet_name)
    except ValueError as e:
        logger.warning("generate_care_plan: pet lookup failed — %s", e)
        return str(e)

    logger.info("generate_care_plan: calling LLM for '%s' — description: %.120s...", pet_name, description)

    existing_names = [t.name for t in pet.tasks]
    existing_time = sum(t.total_time() for t in pet.tasks)
    remaining_budget = owner.available_minutes - existing_time

    api_key = get_api_key()
    client = Groq(api_key=api_key)
    prompt = f"""You are a veterinary care expert. Return a JSON array of recommended care tasks.

Pet: {pet.summary()}
Description: {description}

Owner's daily time budget: {owner.available_minutes} minutes
Already scheduled: {existing_time} minutes ({', '.join(existing_names) if existing_names else 'none'})
Remaining budget: {remaining_budget} minutes

IMPORTANT:
- Total duration * frequency of ALL tasks you generate must not exceed {remaining_budget} minutes.
- Do NOT include any task whose name matches an existing task: {existing_names if existing_names else '[]'}
- If remaining budget is 0 or negative, return an empty array [].

Return ONLY a valid JSON array (no markdown, no explanation). Each object must have:
- "task_name": string
- "category": one of ["walk", "feeding", "meds", "enrichment", "grooming"]
- "duration": integer (minutes)
- "priority": one of ["high", "medium", "low"]
- "frequency": integer (times per day)
- "recurrence": one of ["daily", "weekly", "none"]"""

    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
    )
    raw = resp.choices[0].message.content.strip()
    logger.debug("generate_care_plan: raw LLM response (first 400 chars): %.400s", raw)

    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
        if "```" in raw:
            raw = raw[: raw.rfind("```")]
    raw = raw.strip()

    try:
        tasks_data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error("generate_care_plan: JSON parse failed — %s | raw: %.200s", e, raw)
        return f"Could not parse care plan. Raw: {raw[:300]}"

    logger.info("generate_care_plan: parsed %d tasks for '%s'", len(tasks_data), pet_name)

    added = []
    skipped = []
    for t in tasks_data:
        result = _tool_add_task(owner, pet_name, t["task_name"], t["category"],
                                t["duration"], t["priority"],
                                t.get("frequency", 1), t.get("recurrence", "none"))
        logger.debug("generate_care_plan: add_task result — %s", result)
        if result.startswith("Added"):
            added.append(t["task_name"])
        else:
            skipped.append(f"{t['task_name']} ({result})")

    logger.info("generate_care_plan: done — %d added, %d skipped for '%s'", len(added), len(skipped), pet_name)
    summary = f"Added {len(added)} care tasks for {pet_name}: {', '.join(added) if added else 'none'}."
    if skipped:
        summary += f" Skipped {len(skipped)} (already exist or error): {', '.join(skipped)}."
    return summary


def optimize_schedule(owner: Owner, day_start: str = "08:00") -> str:
    """
    Resolve schedule conflicts by adjusting preferred_time on lower-priority tasks.
    Iterates up to 3 rounds. Returns a human-readable summary of changes made.
    Public so app.py can call it directly from the Fix Conflicts button.
    """
    logger.info("optimize_schedule: starting for owner '%s', day_start=%s", owner.name, day_start)

    scheduler = Scheduler(owner=owner, day_start=day_start)
    scheduler.generate_plan()
    scheduler.sort_by_time()

    initial_conflicts = scheduler.detect_conflicts()
    if not initial_conflicts:
        logger.info("optimize_schedule: no conflicts found — schedule already clean")
        return "No conflicts found — schedule is already conflict-free."

    initial_count = len(initial_conflicts)
    logger.info("optimize_schedule: found %d conflict(s) — beginning resolution", initial_count)
    changes: list[str] = []

    for round_num in range(3):
        conflicts = scheduler.detect_conflicts()
        if not conflicts:
            logger.info("optimize_schedule: all conflicts resolved after round %d", round_num)
            break

        slots = scheduler.daily_plan
        resolved = False

        for i in range(len(slots)):
            for j in range(i + 1, len(slots)):
                if slots[i].task is slots[j].task:
                    continue

                start_a = scheduler._time_to_minutes(slots[i].start_time)
                end_a = start_a + slots[i].task.duration
                start_b = scheduler._time_to_minutes(slots[j].start_time)
                end_b = start_b + slots[j].task.duration

                if not (start_a < end_b and start_b < end_a):
                    continue

                pri_a = PRIORITY_ORDER.get(slots[i].task.priority, 99)
                pri_b = PRIORITY_ORDER.get(slots[j].task.priority, 99)

                if pri_a <= pri_b:
                    new_time = scheduler._minutes_to_time(end_a)
                    slots[j].task.preferred_time = new_time
                    change = (
                        f"Moved '{slots[j].task.name}' → {new_time} "
                        f"(was overlapping '{slots[i].task.name}')"
                    )
                else:
                    new_time = scheduler._minutes_to_time(end_b)
                    slots[i].task.preferred_time = new_time
                    change = (
                        f"Moved '{slots[i].task.name}' → {new_time} "
                        f"(was overlapping '{slots[j].task.name}')"
                    )

                changes.append(change)
                logger.info("optimize_schedule [round %d]: %s", round_num + 1, change)
                resolved = True
                break
            if resolved:
                break

        scheduler = Scheduler(owner=owner, day_start=day_start)
        scheduler.generate_plan()
        scheduler.sort_by_time()

    final_conflicts = scheduler.detect_conflicts()

    if not final_conflicts:
        summary = (
            f"Resolved all {initial_count} conflict(s) with {len(changes)} adjustment(s):\n"
            + "\n".join(f"  - {c}" for c in changes)
            + "\nSchedule is now conflict-free."
        )
        logger.info("optimize_schedule: fully resolved — %d adjustment(s) made", len(changes))
    else:
        summary = (
            f"Partially resolved: {initial_count - len(final_conflicts)} fixed, "
            f"{len(final_conflicts)} remaining.\n"
            + "\n".join(f"  - {c}" for c in changes)
            + f"\nStill conflicting: {len(final_conflicts)} pair(s). "
            "Try reducing task durations."
        )
        logger.warning("optimize_schedule: partially resolved — %d still conflicting", len(final_conflicts))

    return summary


def _tool_optimize_schedule(owner: Owner, day_start: str = "08:00") -> str:
    return optimize_schedule(owner, day_start)


def _execute_tool(name: str, inputs: dict, owner: Owner) -> str:
    logger.debug("execute_tool: dispatching '%s' with args %s", name, inputs)
    try:
        if name == "create_pet":
            result = _tool_create_pet(owner, **inputs)
        elif name == "add_task":
            result = _tool_add_task(owner, **inputs)
        elif name == "list_tasks":
            result = _tool_list_tasks(owner, **inputs)
        elif name == "get_pet_info":
            result = _tool_get_pet_info(owner, **inputs)
        elif name == "update_task":
            pet_name = inputs.pop("pet_name")
            task_name = inputs.pop("task_name")
            result = _tool_update_task(owner, pet_name, task_name, **inputs)
        elif name == "delete_task":
            result = _tool_delete_task(owner, **inputs)
        elif name == "generate_care_plan":
            result = _tool_generate_care_plan(owner, **inputs)
        elif name == "optimize_schedule":
            result = _tool_optimize_schedule(owner, **inputs)
        else:
            logger.error("execute_tool: unknown tool '%s'", name)
            result = f"Unknown tool: {name}"
        logger.debug("execute_tool: '%s' result — %.300s", name, result)
        return result
    except Exception as e:
        logger.error("execute_tool: unhandled exception in '%s' — %s", name, e, exc_info=True)
        return f"Tool error in '{name}': {e}"


# ── System prompt ─────────────────────────────────────────────────────────────

def build_system_prompt(owner: Owner) -> str:
    lines = [
        f"You are Lexa, an AI pet care assistant from Lexa & Friends, helping {owner.name} manage their pets.",
        f"Owner: {owner.name} | Daily time budget: {owner.available_minutes} minutes",
        "",
        "CURRENT STATE:",
    ]
    if not owner.pets:
        lines.append("  No pets registered yet.")
    else:
        for pet in owner.pets:
            lines.append(f"  Pet: {pet.summary()}")
            if pet.tasks:
                for t in pet.tasks:
                    due = f" | due {t.due_date}" if t.due_date else ""
                    lines.append(f"    - {t.name}: {t.category}, {t.duration}min, {t.priority}, {t.recurrence}{due}")
            else:
                lines.append("    - No tasks yet")
    lines += [
        "",
        "RULES:",
        "1. After creating a pet, call get_pet_info to verify.",
        "2. After adding or modifying tasks, call list_tasks to verify.",
        "3. If verification shows something wrong, correct it immediately.",
        "4. If the request is ambiguous (e.g. no duration), ask ONE clarifying question before acting.",
        "5. In your final summary, describe ONLY what you just changed — not the full profile state.",
        "   Good: 'I updated the foot massage start time to 19:00.'",
        "   Bad: 'Bella has a walk, meds, and foot massage. Here is her full profile...'",
        "6. You may call multiple tools in sequence to complete one request.",
        "7. Never make up data — only report what tool results confirm.",
        "8. Never re-add a pet or task that already exists. Check current state first.",
        "9. Never call generate_care_plan for a pet that already has tasks. Use update_task, delete_task, or optimize_schedule instead.",
        f"10. The owner's total daily budget is {owner.available_minutes} minutes. When adding tasks, ensure the total duration * frequency of all tasks stays within this budget.",
    ]
    return "\n".join(lines)


# ── Main agentic loop ─────────────────────────────────────────────────────────

def run_agent(
    user_message: str,
    owner: Owner,
    chat_history: list[dict],
    api_key: str,
) -> str:
    """
    Perceive → Plan/Act → Check → Reflect agentic loop using Groq + Llama.
    Tools mutate owner in place. Self-verifies after every mutation.
    Returns the final natural-language response as a string.
    """
    t_start = time.perf_counter()
    logger.info(
        "run_agent: START — owner='%s', pets=%d, tasks=%d | message: %.120s",
        owner.name, len(owner.pets), len(owner.get_all_tasks()), user_message,
    )

    client = Groq(api_key=api_key)

    messages = [{"role": "system", "content": build_system_prompt(owner)}]
    for msg in chat_history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})

    final_content = "Done — all actions completed successfully."

    for iteration in range(10):
        logger.debug("run_agent: iteration %d — sending %d messages to LLM", iteration + 1, len(messages))

        t_llm = time.perf_counter()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
        )
        llm_ms = int((time.perf_counter() - t_llm) * 1000)

        assistant_msg = response.choices[0].message
        finish_reason = response.choices[0].finish_reason
        tool_call_count = len(assistant_msg.tool_calls) if assistant_msg.tool_calls else 0

        logger.debug(
            "run_agent: iteration %d — LLM responded in %dms | finish_reason=%s | tool_calls=%d",
            iteration + 1, llm_ms, finish_reason, tool_call_count,
        )

        messages.append(assistant_msg)

        if not assistant_msg.tool_calls:
            final_content = assistant_msg.content or "Done — all actions completed successfully."
            logger.info(
                "run_agent: no more tool calls at iteration %d — final response: %.150s",
                iteration + 1, final_content,
            )
            break

        for tool_call in assistant_msg.tool_calls:
            tool_name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            logger.info("run_agent: tool call — %s(%s)", tool_name, args)

            result = _execute_tool(tool_name, args, owner)

            logger.info("run_agent: tool result [%s] — %.200s", tool_name, result)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })

    elapsed_ms = int((time.perf_counter() - t_start) * 1000)
    logger.info(
        "run_agent: END — owner='%s', total_time=%dms, pets=%d, tasks=%d",
        owner.name, elapsed_ms, len(owner.pets), len(owner.get_all_tasks()),
    )

    return final_content


def get_api_key() -> str | None:
    load_dotenv()
    return os.environ.get("GROQ_API_KEY")
