import os
from datetime import date

import pytest

from pet_planner_system import Owner, Pet, Task
from persistence import save_owners, load_owners


@pytest.fixture
def sample_owner():
    owner = Owner(name="Jordan", available_minutes=90, preferences="walks first")
    bella = Pet(name="Bella", species="dog", breed="Labrador", age=4, color="black")
    bella.tasks = [
        Task(name="Morning walk", category="walk", duration=30, priority="high",
             recurrence="daily", due_date=date(2026, 4, 26)),
        Task(name="Feeding", category="feeding", duration=10, priority="high",
             frequency=2),
    ]
    milo = Pet(name="Milo", species="cat", breed="Siamese", age=2, color="cream")
    milo.tasks = [
        Task(name="Play time", category="enrichment", duration=15, priority="low"),
    ]
    owner.pets = [bella, milo]
    return owner


def test_round_trip(tmp_path, sample_owner):
    path = str(tmp_path / "data.json")
    save_owners({"Jordan": sample_owner}, path)
    loaded = load_owners(path)

    assert "Jordan" in loaded
    o = loaded["Jordan"]
    assert o.available_minutes == 90
    assert len(o.pets) == 2
    assert o.pets[0].name == "Bella"
    assert len(o.pets[0].tasks) == 2
    assert o.pets[1].name == "Milo"
    assert len(o.pets[1].tasks) == 1


def test_load_missing_file_returns_empty(tmp_path):
    result = load_owners(str(tmp_path / "nonexistent.json"))
    assert result == {}


def test_date_survives_serialization(tmp_path, sample_owner):
    path = str(tmp_path / "data.json")
    save_owners({"Jordan": sample_owner}, path)
    loaded = load_owners(path)

    walk = loaded["Jordan"].pets[0].tasks[0]
    assert walk.due_date == date(2026, 4, 26)
    assert isinstance(walk.due_date, date)


def test_null_due_date_survives_serialization(tmp_path, sample_owner):
    path = str(tmp_path / "data.json")
    save_owners({"Jordan": sample_owner}, path)
    loaded = load_owners(path)

    feeding = loaded["Jordan"].pets[0].tasks[1]
    assert feeding.due_date is None


def test_corrupted_file_returns_empty(tmp_path):
    path = str(tmp_path / "bad.json")
    with open(path, "w") as f:
        f.write("not valid json {{{")
    result = load_owners(path)
    assert result == {}
