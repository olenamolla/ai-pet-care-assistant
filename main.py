from datetime import date
from pet_planner_system import Pet, Task, Owner, Scheduler, ScheduledSlot

# Create owner
owner = Owner(name="Olena", available_minutes=90, preferences="walks first")

# Create pets
bella = Pet(name="Bella", species="dog", breed="Golden Retriever", age=3, color="golden")
milo = Pet(name="Milo", species="cat", breed="Siamese", age=5, color="cream")

owner.add_pet(bella)
owner.add_pet(milo)

today = date.today()

# Add tasks OUT OF ORDER — mixing pets, priorities, and recurrence types
milo.add_task(Task(name="Play time", category="enrichment", duration=15, priority="low"))
bella.add_task(Task(
    name="Feeding", category="feeding", duration=10, priority="high",
    frequency=2, recurrence="daily", due_date=today,
))
milo.add_task(Task(
    name="Grooming", category="grooming", duration=20, priority="medium",
    recurrence="weekly", due_date=today,
))
bella.add_task(Task(
    name="Morning walk", category="walk", duration=30, priority="high",
    recurrence="daily", due_date=today,
))
bella.add_task(Task(name="Vitamins", category="meds", duration=5, priority="medium"))

# Generate schedule
scheduler = Scheduler(owner=owner, day_start="07:00")
scheduler.generate_plan()

# --- Print schedule ---
print(f"Owner: {owner.name} | Available: {owner.available_minutes} min")
print(f"Pets: {bella.summary()}")
print(f"      {milo.summary()}")
print()
print("=== Schedule (sorted by priority) ===")
for slot in scheduler.daily_plan:
    label = f" (#{slot.occurrence})" if slot.task.frequency > 1 else ""
    due = f" [due {slot.task.due_date}]" if slot.task.due_date else ""
    print(f"  {slot.start_time} — {slot.task.name}{label} [{slot.task.category}] ({slot.task.duration} min){due}")

# --- Conflict check on a clean schedule (should find none) ---
print()
print("=== Conflict Check (clean schedule) ===")
conflicts = scheduler.detect_conflicts()
if conflicts:
    for warning in conflicts:
        print(f"  ⚠ {warning}")
else:
    print("  No conflicts detected.")

# --- Sort by time ---
scheduler.sort_by_time()
print()
print("=== Schedule (sorted by time) ===")
for slot in scheduler.daily_plan:
    label = f" (#{slot.occurrence})" if slot.task.frequency > 1 else ""
    print(f"  {slot.start_time} — {slot.task.name}{label} [{slot.task.category}] ({slot.task.duration} min)")

# --- Show dropped tasks ---
unscheduled = scheduler.get_unscheduled_tasks()
if unscheduled:
    print()
    print("=== Could Not Fit ===")
    for task in unscheduled:
        print(f"  {task.name} — {task.total_time()} min needed ({task.priority} priority)")

# ============================================================
# CONFLICT DETECTION DEMO — manually inject overlapping slots
# to simulate two tasks scheduled at the same time
# ============================================================
print()
print("=" * 50)
print("  CONFLICT DETECTION DEMO")
print("=" * 50)

# Create a fresh schedule with manually overlapping slots
conflict_scheduler = Scheduler(owner=owner, day_start="07:00")

# Same pet, same time: Bella's walk and feeding both at 07:00
walk_task = Task(name="Morning walk", category="walk", duration=30, priority="high")
feed_task = Task(name="Feeding", category="feeding", duration=10, priority="high")

# Different pets, overlapping time: Milo's grooming starts during Bella's walk
groom_task = Task(name="Grooming", category="grooming", duration=20, priority="medium")

# A task that does NOT overlap with anything
vitamin_task = Task(name="Vitamins", category="meds", duration=5, priority="medium")

conflict_scheduler.daily_plan = [
    ScheduledSlot(task=walk_task,    start_time="07:00"),  # 07:00–07:30
    ScheduledSlot(task=feed_task,    start_time="07:00"),  # 07:00–07:10  ← overlaps walk
    ScheduledSlot(task=groom_task,   start_time="07:15"),  # 07:15–07:35  ← overlaps walk
    ScheduledSlot(task=vitamin_task, start_time="08:00"),  # 08:00–08:05  ← no overlap
]

print()
print("--- Injected schedule with overlapping slots ---")
for slot in conflict_scheduler.daily_plan:
    end = conflict_scheduler._minutes_to_time(
        conflict_scheduler._time_to_minutes(slot.start_time) + slot.task.duration
    )
    print(f"  {slot.start_time}–{end}  {slot.task.name} [{slot.task.category}] ({slot.task.duration} min)")

# Run conflict detection
print()
print("=== Conflict Check (overlapping schedule) ===")
conflicts = conflict_scheduler.detect_conflicts()
if conflicts:
    for warning in conflicts:
        print(f"  ⚠ {warning}")
else:
    print("  No conflicts detected.")

# ============================================================
# RECURRENCE DEMO
# ============================================================
print()
print("=" * 50)
print("  RECURRENCE DEMO")
print("=" * 50)

# Show Bella's tasks BEFORE completing any
print()
print(f"--- Bella's tasks BEFORE completion ({len(bella.tasks)} tasks) ---")
for t in bella.tasks:
    due = f" | due {t.due_date}" if t.due_date else ""
    print(f"  {t.name} ({t.recurrence}) — {t.is_completed}/{t.frequency} done{due}")

# Complete Bella's daily Feeding (frequency=2, so mark twice)
feeding = bella.tasks[0]
print(f"\n> Completing '{feeding.name}' occurrence 1 of {feeding.frequency}...")
scheduler.mark_task_complete(bella, feeding)
print(f"  is_fully_done = {feeding.is_fully_done()}")

print(f"> Completing '{feeding.name}' occurrence 2 of {feeding.frequency}...")
next_feeding = scheduler.mark_task_complete(bella, feeding)
print(f"  is_fully_done = {feeding.is_fully_done()}")
if next_feeding:
    print(f"  -> New task auto-created: '{next_feeding.name}' due {next_feeding.due_date}")

# Complete Bella's daily Morning Walk (frequency=1)
walk = bella.tasks[1]
print(f"\n> Completing '{walk.name}'...")
next_walk = scheduler.mark_task_complete(bella, walk)
print(f"  is_fully_done = {walk.is_fully_done()}")
if next_walk:
    print(f"  -> New task auto-created: '{next_walk.name}' due {next_walk.due_date}")

# Complete Milo's weekly Grooming
grooming = milo.tasks[1]
print(f"\n> Completing '{grooming.name}' (weekly)...")
next_grooming = scheduler.mark_task_complete(milo, grooming)
print(f"  is_fully_done = {grooming.is_fully_done()}")
if next_grooming:
    print(f"  -> New task auto-created: '{next_grooming.name}' due {next_grooming.due_date}")

# Complete Milo's Play time (non-recurring) — should NOT create a new task
play = milo.tasks[0]
print(f"\n> Completing '{play.name}' (non-recurring)...")
next_play = scheduler.mark_task_complete(milo, play)
print(f"  is_fully_done = {play.is_fully_done()}")
print(f"  -> Next occurrence created: {next_play is not None}")

# Show tasks AFTER completions
print()
print(f"--- Bella's tasks AFTER completion ({len(bella.tasks)} tasks) ---")
for t in bella.tasks:
    due = f" | due {t.due_date}" if t.due_date else ""
    status = "DONE" if t.is_fully_done() else "pending"
    print(f"  {t.name} ({t.recurrence}) — {status}{due}")

print()
print(f"--- Milo's tasks AFTER completion ({len(milo.tasks)} tasks) ---")
for t in milo.tasks:
    due = f" | due {t.due_date}" if t.due_date else ""
    status = "DONE" if t.is_fully_done() else "pending"
    print(f"  {t.name} ({t.recurrence}) — {status}{due}")

# --- Filter: only upcoming (incomplete) tasks ---
print()
print("=== Upcoming Tasks (incomplete, all pets) ===")
for pet, task in owner.filter_tasks(completed=False):
    due = f" | due {task.due_date}" if task.due_date else ""
    print(f"  [{pet.name}] {task.name} ({task.recurrence}){due}")

# --- Reasoning ---
print()
print("=== Reasoning ===")
print(scheduler.get_reasoning())
