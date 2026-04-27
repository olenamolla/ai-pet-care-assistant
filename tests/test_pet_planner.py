from datetime import date
from pet_planner_system import Pet, Task, Owner, Scheduler, ScheduledSlot
# ── Existing tests ──────────────────────────────────────────────────


def test_mark_complete_changes_status():
    task = Task(name="Walk", category="walk", duration=30, priority="high", frequency=2)
    assert task.is_completed == 0
    assert not task.is_fully_done()

    task.mark_complete()
    assert task.is_completed == 1
    assert not task.is_fully_done()

    task.mark_complete()
    assert task.is_completed == 2
    assert task.is_fully_done()

    # Should not increment past frequency
    task.mark_complete()
    assert task.is_completed == 2


def test_add_task_increases_pet_task_count():
    pet = Pet(name="Bella", species="dog", breed="Labrador", age=4, color="black")
    assert len(pet.tasks) == 0

    pet.add_task(Task(name="Walk", category="walk", duration=30, priority="high"))
    assert len(pet.tasks) == 1

    pet.add_task(Task(name="Feeding", category="feeding", duration=10, priority="medium"))
    assert len(pet.tasks) == 2


# ── Sorting Correctness ────────────────────────────────────────────


def test_sort_by_time_returns_chronological_order():
    """Tasks scheduled by priority should be reordered chronologically after sort_by_time()."""
    pet = Pet(name="Buddy", species="dog", breed="Poodle", age=3, color="white")
    # Low-priority task gets a later time, high-priority gets an earlier time,
    # but we add them in reverse order to the plan so sort has work to do.
    low = Task(name="Grooming", category="grooming", duration=20, priority="low")
    high = Task(name="Meds", category="meds", duration=10, priority="high")
    pet.add_task(low)
    pet.add_task(high)

    owner = Owner(name="Ana", available_minutes=120)
    owner.add_pet(pet)

    scheduler = Scheduler(owner, day_start="08:00")
    scheduler.generate_plan()

    # After generate_plan, high should be first (priority order).
    # Manually verify, then sort by time and confirm order stays chronological.
    sorted_plan = scheduler.sort_by_time()
    times = [slot.start_time for slot in sorted_plan]
    assert times == sorted(times), "Plan should be in chronological order after sort_by_time()"


def test_sort_by_time_with_same_start_time():
    """Two slots at the same start_time should not crash or lose entries."""
    task_a = Task(name="Walk", category="walk", duration=30, priority="high")
    task_b = Task(name="Feed", category="feeding", duration=15, priority="high")

    scheduler = Scheduler(Owner(name="Ana", available_minutes=120))
    scheduler.daily_plan = [
        ScheduledSlot(task=task_a, start_time="08:00"),
        ScheduledSlot(task=task_b, start_time="08:00"),
    ]

    sorted_plan = scheduler.sort_by_time()
    assert len(sorted_plan) == 2
    assert sorted_plan[0].start_time == "08:00"
    assert sorted_plan[1].start_time == "08:00"


def test_sort_by_time_empty_plan():
    """Sorting an empty plan should return an empty list without errors."""
    scheduler = Scheduler(Owner(name="Ana", available_minutes=60))
    assert scheduler.sort_by_time() == []


# ── Recurrence Logic ───────────────────────────────────────────────


def test_daily_recurrence_creates_next_day_task():
    """Completing a daily task should create a new task due the following day."""
    pet = Pet(name="Milo", species="cat", breed="Siamese", age=2, color="cream")
    task = Task(
        name="Feed",
        category="feeding",
        duration=10,
        priority="high",
        frequency=1,
        recurrence="daily",
        due_date=date(2026, 3, 29),
    )
    pet.add_task(task)

    owner = Owner(name="Ana", available_minutes=60)
    owner.add_pet(pet)
    scheduler = Scheduler(owner)

    next_task = scheduler.mark_task_complete(pet, task)

    assert next_task is not None
    assert next_task.due_date == date(2026, 3, 30)
    assert next_task.is_completed == 0
    assert next_task.recurrence == "daily"
    assert next_task in pet.tasks


def test_weekly_recurrence_creates_task_seven_days_later():
    """Completing a weekly task should create a new task due 7 days later."""
    pet = Pet(name="Milo", species="cat", breed="Siamese", age=2, color="cream")
    task = Task(
        name="Grooming",
        category="grooming",
        duration=45,
        priority="medium",
        frequency=1,
        recurrence="weekly",
        due_date=date(2026, 3, 29),
    )
    pet.add_task(task)

    owner = Owner(name="Ana", available_minutes=120)
    owner.add_pet(pet)
    scheduler = Scheduler(owner)

    next_task = scheduler.mark_task_complete(pet, task)

    assert next_task is not None
    assert next_task.due_date == date(2026, 4, 5)
    assert next_task.is_completed == 0


def test_non_recurring_task_returns_none():
    """A non-recurring task should return None after completion — no new task created."""
    pet = Pet(name="Milo", species="cat", breed="Siamese", age=2, color="cream")
    task = Task(
        name="Vet Visit",
        category="meds",
        duration=60,
        priority="high",
        frequency=1,
        recurrence="none",
    )
    pet.add_task(task)

    owner = Owner(name="Ana", available_minutes=120)
    owner.add_pet(pet)
    scheduler = Scheduler(owner)

    next_task = scheduler.mark_task_complete(pet, task)

    assert next_task is None
    assert len(pet.tasks) == 1  # no new task was added


def test_multi_frequency_recurrence_requires_all_completions():
    """A frequency-2 daily task should only create the next occurrence after both completions."""
    pet = Pet(name="Rex", species="dog", breed="Boxer", age=5, color="brown")
    task = Task(
        name="Walk",
        category="walk",
        duration=30,
        priority="high",
        frequency=2,
        recurrence="daily",
        due_date=date(2026, 3, 29),
    )
    pet.add_task(task)

    owner = Owner(name="Ana", available_minutes=120)
    owner.add_pet(pet)
    scheduler = Scheduler(owner)

    # First completion — not fully done yet
    result = scheduler.mark_task_complete(pet, task)
    assert result is None
    assert len(pet.tasks) == 1

    # Second completion — now fully done, next occurrence created
    result = scheduler.mark_task_complete(pet, task)
    assert result is not None
    assert result.due_date == date(2026, 3, 30)
    assert len(pet.tasks) == 2


def test_recurring_task_with_no_due_date_returns_none():
    """A daily task missing a due_date should return None instead of crashing."""
    pet = Pet(name="Milo", species="cat", breed="Siamese", age=2, color="cream")
    task = Task(
        name="Feed",
        category="feeding",
        duration=10,
        priority="high",
        frequency=1,
        recurrence="daily",
        due_date=None,
    )
    pet.add_task(task)

    owner = Owner(name="Ana", available_minutes=60)
    owner.add_pet(pet)
    scheduler = Scheduler(owner)

    next_task = scheduler.mark_task_complete(pet, task)
    assert next_task is None


# ── Conflict Detection ─────────────────────────────────────────────


def test_detect_conflicts_flags_overlapping_slots():
    """Two slots that overlap in time should produce exactly one conflict warning."""
    task_a = Task(name="Walk", category="walk", duration=30, priority="high")
    task_b = Task(name="Feed", category="feeding", duration=30, priority="medium")

    scheduler = Scheduler(Owner(name="Ana", available_minutes=120))
    scheduler.daily_plan = [
        ScheduledSlot(task=task_a, start_time="08:00"),
        ScheduledSlot(task=task_b, start_time="08:15"),
    ]

    warnings = scheduler.detect_conflicts()
    assert len(warnings) == 1
    assert "15 min" in warnings[0]


def test_detect_conflicts_flags_identical_start_times():
    """Two slots starting at the exact same time should be flagged as a conflict."""
    task_a = Task(name="Walk", category="walk", duration=30, priority="high")
    task_b = Task(name="Meds", category="meds", duration=20, priority="high")

    scheduler = Scheduler(Owner(name="Ana", available_minutes=120))
    scheduler.daily_plan = [
        ScheduledSlot(task=task_a, start_time="09:00"),
        ScheduledSlot(task=task_b, start_time="09:00"),
    ]

    warnings = scheduler.detect_conflicts()
    assert len(warnings) == 1
    assert "20 min" in warnings[0]  # shorter task is fully overlapped


def test_detect_conflicts_adjacent_slots_no_conflict():
    """Back-to-back slots (no overlap) should produce zero warnings."""
    task_a = Task(name="Walk", category="walk", duration=30, priority="high")
    task_b = Task(name="Feed", category="feeding", duration=15, priority="medium")

    scheduler = Scheduler(Owner(name="Ana", available_minutes=120))
    scheduler.daily_plan = [
        ScheduledSlot(task=task_a, start_time="08:00"),
        ScheduledSlot(task=task_b, start_time="08:30"),
    ]

    warnings = scheduler.detect_conflicts()
    assert len(warnings) == 0


def test_detect_conflicts_empty_plan():
    """An empty plan should return no conflicts."""
    scheduler = Scheduler(Owner(name="Ana", available_minutes=60))
    assert scheduler.detect_conflicts() == []


# ── Scheduling Edge Cases ──────────────────────────────────────────


def test_pet_with_no_tasks_produces_empty_plan():
    """An owner whose pet has no tasks should get an empty schedule."""
    pet = Pet(name="Ghost", species="cat", breed="Persian", age=1, color="white")
    owner = Owner(name="Ana", available_minutes=120)
    owner.add_pet(pet)

    scheduler = Scheduler(owner)
    plan = scheduler.generate_plan()

    assert plan == []
    assert scheduler.get_unscheduled_tasks() == []


def test_zero_available_minutes_drops_all_tasks():
    """An owner with zero available time should have everything unscheduled."""
    pet = Pet(name="Buddy", species="dog", breed="Poodle", age=3, color="white")
    pet.add_task(Task(name="Walk", category="walk", duration=5, priority="high"))

    owner = Owner(name="Ana", available_minutes=0)
    owner.add_pet(pet)

    scheduler = Scheduler(owner)
    plan = scheduler.generate_plan()

    assert plan == []
    assert len(scheduler.get_unscheduled_tasks()) == 1


def test_budget_exactly_fits_all_tasks():
    """When available_minutes exactly equals total task time, everything should be scheduled."""
    pet = Pet(name="Buddy", species="dog", breed="Poodle", age=3, color="white")
    pet.add_task(Task(name="Walk", category="walk", duration=30, priority="high"))
    pet.add_task(Task(name="Feed", category="feeding", duration=10, priority="medium"))

    owner = Owner(name="Ana", available_minutes=40)  # exactly 30 + 10
    owner.add_pet(pet)

    scheduler = Scheduler(owner)
    plan = scheduler.generate_plan()

    assert len(plan) == 2
    assert scheduler.get_unscheduled_tasks() == []
