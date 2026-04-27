import json
import os
from datetime import date

from pet_planner_system import Owner, Pet, Task


def _task_to_dict(task: Task) -> dict:
    return {
        "name": task.name,
        "category": task.category,
        "duration": task.duration,
        "priority": task.priority,
        "frequency": task.frequency,
        "is_completed": task.is_completed,
        "recurrence": task.recurrence,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "preferred_time": task.preferred_time,
    }


def _dict_to_task(d: dict) -> Task:
    due = d.get("due_date")
    return Task(
        name=d["name"],
        category=d["category"],
        duration=d["duration"],
        priority=d["priority"],
        frequency=d.get("frequency", 1),
        is_completed=d.get("is_completed", 0),
        recurrence=d.get("recurrence", "none"),
        due_date=date.fromisoformat(due) if due else None,
        preferred_time=d.get("preferred_time"),
    )


def _pet_to_dict(pet: Pet) -> dict:
    return {
        "name": pet.name,
        "species": pet.species,
        "breed": pet.breed,
        "age": pet.age,
        "color": pet.color,
        "favorite_activities": pet.favorite_activities,
        "special_instructions": pet.special_instructions,
        "tasks": [_task_to_dict(t) for t in pet.tasks],
    }


def _dict_to_pet(d: dict) -> Pet:
    pet = Pet(
        name=d["name"],
        species=d["species"],
        breed=d["breed"],
        age=d["age"],
        color=d["color"],
        favorite_activities=d.get("favorite_activities", []),
        special_instructions=d.get("special_instructions", ""),
    )
    # Deduplicate tasks by name (keep first occurrence) in case of legacy data
    seen: set[str] = set()
    unique_tasks = []
    for t in d.get("tasks", []):
        key = t["name"].lower()
        if key not in seen:
            seen.add(key)
            unique_tasks.append(t)
    pet.tasks = [_dict_to_task(t) for t in unique_tasks]
    return pet


def _owner_to_dict(owner: Owner) -> dict:
    return {
        "name": owner.name,
        "available_minutes": owner.available_minutes,
        "preferences": owner.preferences,
        "pets": [_pet_to_dict(p) for p in owner.pets],
    }


def _dict_to_owner(d: dict) -> Owner:
    owner = Owner(
        name=d["name"],
        available_minutes=d["available_minutes"],
        preferences=d.get("preferences", ""),
    )
    owner.pets = [_dict_to_pet(p) for p in d.get("pets", [])]
    return owner


def save_owners(owners: dict[str, "Owner"], path: str = "pawpal_data.json") -> None:
    data = {"owners": [_owner_to_dict(o) for o in owners.values()]}
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def load_owners(path: str = "pawpal_data.json") -> dict[str, "Owner"]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            data = json.load(f)
        return {o["name"]: _dict_to_owner(o) for o in data.get("owners", [])}
    except (json.JSONDecodeError, KeyError):
        return {}
