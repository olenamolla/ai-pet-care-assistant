from datetime import date
import pytest

from pet_planner_system import Owner, Pet, Task
from agent import (
    _tool_create_pet,
    _tool_add_task,
    _tool_list_tasks,
    _tool_get_pet_info,
    _tool_update_task,
    _tool_delete_task,
)


@pytest.fixture
def owner():
    o = Owner(name="Jordan", available_minutes=90)
    bella = Pet(name="Bella", species="dog", breed="Labrador", age=3, color="black")
    o.add_pet(bella)
    return o


def test_create_pet_adds_to_owner(owner):
    result = _tool_create_pet(owner, name="Milo", species="cat",
                              breed="Siamese", age=2, color="cream")
    assert "Created" in result
    assert len(owner.pets) == 2
    assert owner.pets[1].name == "Milo"


def test_create_pet_duplicate_rejected(owner):
    result = _tool_create_pet(owner, name="Bella", species="dog",
                              breed="Poodle", age=1, color="white")
    assert "already exists" in result
    assert len(owner.pets) == 1


def test_add_task_correct_fields(owner):
    result = _tool_add_task(owner, pet_name="Bella", task_name="Morning walk",
                            category="walk", duration=30, priority="high",
                            recurrence="daily")
    assert "Added" in result
    assert len(owner.pets[0].tasks) == 1
    t = owner.pets[0].tasks[0]
    assert t.name == "Morning walk"
    assert t.duration == 30
    assert t.priority == "high"
    assert t.recurrence == "daily"
    assert t.due_date == date.today()


def test_add_task_unknown_pet_returns_error(owner):
    result = _tool_add_task(owner, pet_name="Ghost", task_name="Walk",
                            category="walk", duration=20, priority="low")
    assert "not found" in result.lower()
    assert len(owner.pets[0].tasks) == 0


def test_add_task_no_recurrence_no_due_date(owner):
    _tool_add_task(owner, pet_name="Bella", task_name="Vitamins",
                   category="meds", duration=5, priority="medium")
    t = owner.pets[0].tasks[0]
    assert t.due_date is None


def test_list_tasks_returns_correct_format(owner):
    _tool_add_task(owner, pet_name="Bella", task_name="Walk",
                   category="walk", duration=30, priority="high")
    result = _tool_list_tasks(owner, pet_name="Bella")
    assert "Bella" in result
    assert "Walk" in result
    assert "1 total" in result


def test_list_tasks_empty_pet(owner):
    result = _tool_list_tasks(owner, pet_name="Bella")
    assert "no tasks" in result.lower()


def test_list_tasks_unknown_pet(owner):
    result = _tool_list_tasks(owner, pet_name="Ghost")
    assert "not found" in result.lower()


def test_get_pet_info_returns_summary(owner):
    result = _tool_get_pet_info(owner, pet_name="Bella")
    assert "Bella" in result
    assert "Labrador" in result


def test_get_pet_info_unknown_pet(owner):
    result = _tool_get_pet_info(owner, pet_name="Ghost")
    assert "not found" in result.lower()


def test_update_task_modifies_field(owner):
    _tool_add_task(owner, pet_name="Bella", task_name="Walk",
                   category="walk", duration=30, priority="high")
    result = _tool_update_task(owner, "Bella", "Walk", duration=45)
    assert "Updated" in result
    assert owner.pets[0].tasks[0].duration == 45


def test_update_task_unknown_task(owner):
    result = _tool_update_task(owner, "Bella", "Nonexistent", duration=10)
    assert "not found" in result.lower()


def test_delete_task_removes_from_pet(owner):
    _tool_add_task(owner, pet_name="Bella", task_name="Walk",
                   category="walk", duration=30, priority="high")
    assert len(owner.pets[0].tasks) == 1
    result = _tool_delete_task(owner, pet_name="Bella", task_name="Walk")
    assert "Deleted" in result
    assert len(owner.pets[0].tasks) == 0


def test_delete_task_unknown_task(owner):
    result = _tool_delete_task(owner, pet_name="Bella", task_name="Ghost task")
    assert "not found" in result.lower()
