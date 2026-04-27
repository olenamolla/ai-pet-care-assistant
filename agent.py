import json
import os
from datetime import date

from groq import Groq
from dotenv import load_dotenv

from pet_planner_system import Owner, Pet, Task

load_dotenv()

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
            return f"Pet '{name}' already exists."
    owner.add_pet(Pet(
        name=name, species=species, breed=breed,
        age=int(age), color=color, special_instructions=special_instructions,
    ))
    return f"Created pet '{name}' ({species}, {breed}, {age}yo, {color})."


def _tool_add_task(owner: Owner, pet_name: str, task_name: str, category: str,
                   duration: int, priority: str, frequency: int = 1,
                   recurrence: str = "none", preferred_time: str = None) -> str:
    try:
        pet = _find_pet(owner, pet_name)
    except ValueError as e:
        return str(e)
    # Prevent duplicates — if a task with this name already exists, skip it
    for existing in pet.tasks:
        if existing.name.lower() == task_name.lower():
            return f"Task '{task_name}' already exists for {pet.name}. Use update_task to change it."
    pet.add_task(Task(
        name=task_name, category=category, duration=int(duration),
        priority=priority, frequency=int(frequency), recurrence=recurrence,
        due_date=date.today() if recurrence != "none" else None,
        preferred_time=preferred_time,
    ))
    rec = f", repeats {recurrence}" if recurrence != "none" else ""
    return f"Added '{task_name}' to {pet.name} ({category}, {duration}min, {priority}{rec})."


def _tool_list_tasks(owner: Owner, pet_name: str) -> str:
    try:
        pet = _find_pet(owner, pet_name)
    except ValueError as e:
        return str(e)
    if not pet.tasks:
        return f"{pet.name} has no tasks yet."
    lines = [f"{pet.name}'s tasks ({len(pet.tasks)} total):"]
    for t in pet.tasks:
        due = f" | due {t.due_date}" if t.due_date else ""
        pt = f" | at {t.preferred_time}" if t.preferred_time else ""
        lines.append(f"  - {t.name}: {t.category}, {t.duration}min, {t.priority}, {t.recurrence}{due}{pt}")
    return "\n".join(lines)


def _tool_get_pet_info(owner: Owner, pet_name: str) -> str:
    try:
        pet = _find_pet(owner, pet_name)
    except ValueError as e:
        return str(e)
    return f"{pet.summary()} | {len(pet.tasks)} task(s)"


def _tool_update_task(owner: Owner, pet_name: str, task_name: str, **kwargs) -> str:
    try:
        pet = _find_pet(owner, pet_name)
    except ValueError as e:
        return str(e)
    for task in pet.tasks:
        if task.name.lower() == task_name.lower():
            task.update(**kwargs)
            return f"Updated '{task_name}' for {pet.name}: {kwargs}"
    return f"Task '{task_name}' not found for {pet.name}."


def _tool_delete_task(owner: Owner, pet_name: str, task_name: str) -> str:
    try:
        pet = _find_pet(owner, pet_name)
    except ValueError as e:
        return str(e)
    for task in pet.tasks:
        if task.name.lower() == task_name.lower():
            pet.remove_task(task)
            return f"Deleted task '{task_name}' from {pet.name}."
    return f"Task '{task_name}' not found for {pet.name}."


def _tool_generate_care_plan(owner: Owner, pet_name: str, description: str) -> str:
    try:
        pet = _find_pet(owner, pet_name)
    except ValueError as e:
        return str(e)

    api_key = get_api_key()
    client = Groq(api_key=api_key)
    prompt = f"""You are a veterinary care expert. Return a JSON array of recommended care tasks.

Pet: {pet.summary()}
Description: {description}

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

    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
        if "```" in raw:
            raw = raw[: raw.rfind("```")]
    raw = raw.strip()

    try:
        tasks_data = json.loads(raw)
    except json.JSONDecodeError:
        return f"Could not parse care plan. Raw: {raw[:300]}"

    added = []
    for t in tasks_data:
        _tool_add_task(owner, pet_name, t["task_name"], t["category"],
                       t["duration"], t["priority"],
                       t.get("frequency", 1), t.get("recurrence", "none"))
        added.append(t["task_name"])

    return f"Generated and added {len(added)} care tasks for {pet_name}: {', '.join(added)}."


def _execute_tool(name: str, inputs: dict, owner: Owner) -> str:
    try:
        if name == "create_pet":
            return _tool_create_pet(owner, **inputs)
        elif name == "add_task":
            return _tool_add_task(owner, **inputs)
        elif name == "list_tasks":
            return _tool_list_tasks(owner, **inputs)
        elif name == "get_pet_info":
            return _tool_get_pet_info(owner, **inputs)
        elif name == "update_task":
            pet_name = inputs.pop("pet_name")
            task_name = inputs.pop("task_name")
            return _tool_update_task(owner, pet_name, task_name, **inputs)
        elif name == "delete_task":
            return _tool_delete_task(owner, **inputs)
        elif name == "generate_care_plan":
            return _tool_generate_care_plan(owner, **inputs)
        else:
            return f"Unknown tool: {name}"
    except Exception as e:
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
    client = Groq(api_key=api_key)

    messages = [{"role": "system", "content": build_system_prompt(owner)}]
    for msg in chat_history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})

    # Tool-use loop — continues until the model stops calling tools
    for _ in range(10):
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
        )

        assistant_msg = response.choices[0].message
        messages.append(assistant_msg)

        if not assistant_msg.tool_calls:
            break

        # Execute every tool call and add results back into the conversation
        for tool_call in assistant_msg.tool_calls:
            args = json.loads(tool_call.function.arguments)
            result = _execute_tool(tool_call.function.name, args, owner)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })

    return assistant_msg.content or "Done — all actions completed successfully."


def get_api_key() -> str | None:
    load_dotenv()
    return os.environ.get("GROQ_API_KEY")
