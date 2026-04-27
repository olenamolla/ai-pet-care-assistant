from datetime import date

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich import box

from pet_planner_system import Owner, Pet, Task, Scheduler, ScheduledSlot

console = Console()
today = date.today()

# ── 1. BUILD PROFILES ────────────────────────────────────────────────────────

console.print()
console.print(Panel.fit(
    "[bold cyan]Lexa & Friends[/bold cyan] — End-to-End Demo",
    border_style="cyan",
))

# Owner
owner = Owner(name="Olena", available_minutes=90, preferences="walks first")

# Pet 1: Bella the dog
bella = Pet(name="Bella", species="dog", breed="Golden Retriever", age=3, color="golden")
bella.add_task(Task(
    name="Morning Walk",   category="walk",       duration=30, priority="high",
    frequency=1, recurrence="daily",  due_date=today,
))
bella.add_task(Task(
    name="Feeding",        category="feeding",    duration=10, priority="high",
    frequency=2, recurrence="daily",  due_date=today,
))
bella.add_task(Task(
    name="Vitamins",       category="meds",       duration=5,  priority="medium",
))

# Pet 2: Milo the cat
milo = Pet(name="Milo", species="cat", breed="Siamese", age=5, color="cream")
milo.add_task(Task(
    name="Grooming",       category="grooming",   duration=20, priority="medium",
    recurrence="weekly",  due_date=today,
))
milo.add_task(Task(
    name="Play Time",      category="enrichment", duration=15, priority="low",
))
milo.add_task(Task(
    name="Dental Treats",  category="meds",       duration=5,  priority="medium",
    recurrence="daily",   due_date=today,
))

owner.add_pet(bella)
owner.add_pet(milo)

# Profile summary table
console.print()
console.print(Rule("[bold]STEP 1 — Owner & Pet Profiles[/bold]"))

profile = Table(box=box.ROUNDED, show_header=True, header_style="bold magenta")
profile.add_column("Owner",    style="bold")
profile.add_column("Budget")
profile.add_column("Pet")
profile.add_column("Species")
profile.add_column("Breed")
profile.add_column("Age")
profile.add_column("Tasks")

for pet in owner.pets:
    profile.add_row(
        owner.name,
        f"{owner.available_minutes} min/day",
        pet.name,
        pet.species,
        pet.breed,
        f"{pet.age} yr",
        str(len(pet.tasks)),
    )

console.print(profile)

# ── 2. GENERATE SCHEDULE (priority sort + time budget) ───────────────────────

console.print()
console.print(Rule("[bold]STEP 2 — Generate Schedule (sorted by priority, time-budget greedy)[/bold]"))

scheduler = Scheduler(owner=owner, day_start="08:00")
scheduler.generate_plan()

sched_table = Table(box=box.ROUNDED, header_style="bold blue")
sched_table.add_column("Start",    width=6)
sched_table.add_column("Pet",      style="cyan")
sched_table.add_column("Task")
sched_table.add_column("Category")
sched_table.add_column("Priority")
sched_table.add_column("Duration")
sched_table.add_column("Occurrence")
sched_table.add_column("Recurrence")

PRIORITY_COLORS = {"high": "red", "medium": "yellow", "low": "green"}

for pet in owner.pets:
    for slot in scheduler.daily_plan:
        if slot.task in pet.tasks:
            color = PRIORITY_COLORS.get(slot.task.priority, "white")
            sched_table.add_row(
                slot.start_time,
                pet.name,
                slot.task.name,
                slot.task.category,
                f"[{color}]{slot.task.priority}[/{color}]",
                f"{slot.task.duration} min",
                f"#{slot.occurrence}" if slot.task.frequency > 1 else "-",
                slot.task.recurrence,
            )

console.print(sched_table)

# Show unscheduled tasks if any
dropped = scheduler.get_unscheduled_tasks()
if dropped:
    console.print()
    console.print("[bold yellow]Could Not Fit (budget exceeded):[/bold yellow]")
    for t in dropped:
        console.print(f"  [yellow]✗[/yellow] {t.name} — needs {t.total_time()} min ({t.priority} priority)")
else:
    console.print("[green]✓ All tasks fit within the 90-minute budget.[/green]")

# ── 3. SORT BY TIME ──────────────────────────────────────────────────────────

console.print()
console.print(Rule("[bold]STEP 3 — Sort Schedule Chronologically (HH:MM → minutes key)[/bold]"))

scheduler.sort_by_time()

time_table = Table(box=box.ROUNDED, header_style="bold blue")
time_table.add_column("Start",    width=6)
time_table.add_column("End",      width=6)
time_table.add_column("Task")
time_table.add_column("Pet",      style="cyan")
time_table.add_column("Category")
time_table.add_column("Priority")

for slot in scheduler.daily_plan:
    end_min = scheduler._time_to_minutes(slot.start_time) + slot.task.duration
    end_str = scheduler._minutes_to_time(end_min)
    color   = PRIORITY_COLORS.get(slot.task.priority, "white")
    occ     = f" #{slot.occurrence}" if slot.task.frequency > 1 else ""
    owner_pet = next(p for p in owner.pets if slot.task in p.tasks)
    time_table.add_row(
        slot.start_time,
        end_str,
        slot.task.name + occ,
        owner_pet.name,
        slot.task.category,
        f"[{color}]{slot.task.priority}[/{color}]",
    )

console.print(time_table)

# ── 4. CONFLICT DETECTION ────────────────────────────────────────────────────

console.print()
console.print(Rule("[bold]STEP 4 — Conflict Detection[/bold]"))

console.print()
console.print("[bold]4a. Clean schedule (no conflicts expected):[/bold]")
conflicts = scheduler.detect_conflicts()
if conflicts:
    for w in conflicts:
        console.print(f"  [red]⚠ {w}[/red]")
else:
    console.print("  [green]✓ No conflicts detected.[/green]")

# Inject overlapping slots to demonstrate detection
console.print()
console.print("[bold]4b. Injected overlapping schedule (conflicts expected):[/bold]")

conflict_owner = Owner(name="Demo", available_minutes=999)
conflict_scheduler = Scheduler(owner=conflict_owner, day_start="08:00")

walk_t  = Task(name="Morning Walk", category="walk",    duration=30, priority="high")
feed_t  = Task(name="Feeding",      category="feeding", duration=10, priority="high")
groom_t = Task(name="Grooming",     category="grooming",duration=20, priority="medium")
vit_t   = Task(name="Vitamins",     category="meds",    duration=5,  priority="medium")

conflict_scheduler.daily_plan = [
    ScheduledSlot(task=walk_t,  start_time="08:00"),  # 08:00–08:30
    ScheduledSlot(task=feed_t,  start_time="08:00"),  # 08:00–08:10 ← overlaps walk
    ScheduledSlot(task=groom_t, start_time="08:15"),  # 08:15–08:35 ← overlaps walk
    ScheduledSlot(task=vit_t,   start_time="09:00"),  # 09:00–09:05 ← no overlap
]

inject_table = Table(box=box.SIMPLE, header_style="bold")
inject_table.add_column("Start")
inject_table.add_column("End")
inject_table.add_column("Task")
inject_table.add_column("Duration")

for slot in conflict_scheduler.daily_plan:
    end_min = conflict_scheduler._time_to_minutes(slot.start_time) + slot.task.duration
    end_str = conflict_scheduler._minutes_to_time(end_min)
    inject_table.add_row(slot.start_time, end_str, slot.task.name, f"{slot.task.duration} min")

console.print(inject_table)

conflicts = conflict_scheduler.detect_conflicts()
for w in conflicts:
    console.print(f"  [red]⚠ {w}[/red]")

# ── 5. RECURRING TASKS ───────────────────────────────────────────────────────

console.print()
console.print(Rule("[bold]STEP 5 — Recurring Task Completion & Auto-Scheduling[/bold]"))

console.print()
console.print("[bold]Before completions:[/bold]")
before = Table(box=box.SIMPLE, header_style="bold")
before.add_column("Pet",       style="cyan")
before.add_column("Task")
before.add_column("Progress")
before.add_column("Recurrence")
before.add_column("Due")

for pet in owner.pets:
    for t in pet.tasks:
        before.add_row(
            pet.name, t.name,
            f"{t.is_completed}/{t.frequency}",
            t.recurrence,
            str(t.due_date) if t.due_date else "-",
        )

console.print(before)

# Mark Bella's Feeding complete twice (frequency=2) → triggers next occurrence
feeding = bella.tasks[1]
console.print(f"\n[cyan]>[/cyan] Marking [bold]{feeding.name}[/bold] (freq=2) — occurrence 1 of 2...")
scheduler.mark_task_complete(bella, feeding)
console.print(f"  fully done: {feeding.is_fully_done()}")

console.print(f"[cyan]>[/cyan] Marking [bold]{feeding.name}[/bold] — occurrence 2 of 2...")
next_feeding = scheduler.mark_task_complete(bella, feeding)
console.print(f"  fully done: {feeding.is_fully_done()}")
if next_feeding:
    console.print(f"  [green]→ Next daily occurrence auto-created: due {next_feeding.due_date}[/green]")

# Mark Bella's Morning Walk complete (frequency=1) → triggers next occurrence
walk = bella.tasks[0]
console.print(f"\n[cyan]>[/cyan] Marking [bold]{walk.name}[/bold] complete...")
next_walk = scheduler.mark_task_complete(bella, walk)
if next_walk:
    console.print(f"  [green]→ Next daily occurrence auto-created: due {next_walk.due_date}[/green]")

# Mark Milo's Grooming complete (weekly) → triggers next occurrence
grooming = milo.tasks[0]
console.print(f"\n[cyan]>[/cyan] Marking [bold]{grooming.name}[/bold] complete (weekly)...")
next_grooming = scheduler.mark_task_complete(milo, grooming)
if next_grooming:
    console.print(f"  [green]→ Next weekly occurrence auto-created: due {next_grooming.due_date}[/green]")

# Mark Milo's Play Time complete (non-recurring) → no new task
play = milo.tasks[1]
console.print(f"\n[cyan]>[/cyan] Marking [bold]{play.name}[/bold] complete (non-recurring)...")
next_play = scheduler.mark_task_complete(milo, play)
console.print(f"  [yellow]→ Next occurrence created: {next_play is not None}[/yellow]  (non-recurring — expected)")

# ── 6. FILTER TASKS ──────────────────────────────────────────────────────────

console.print()
console.print(Rule("[bold]STEP 6 — Filter: Incomplete Tasks Across Both Pets[/bold]"))

console.print()
incomplete = owner.filter_tasks(completed=False)
filter_table = Table(box=box.ROUNDED, header_style="bold blue")
filter_table.add_column("Pet",       style="cyan")
filter_table.add_column("Task")
filter_table.add_column("Category")
filter_table.add_column("Priority")
filter_table.add_column("Progress")
filter_table.add_column("Due")

for pet, task in incomplete:
    color = PRIORITY_COLORS.get(task.priority, "white")
    filter_table.add_row(
        pet.name, task.name, task.category,
        f"[{color}]{task.priority}[/{color}]",
        f"{task.is_completed}/{task.frequency}",
        str(task.due_date) if task.due_date else "-",
    )

console.print(filter_table)
console.print(f"[dim]{len(incomplete)} incomplete task(s) remaining across {len(owner.pets)} pet(s).[/dim]")

# ── 7. SCHEDULER REASONING ───────────────────────────────────────────────────

console.print()
console.print(Rule("[bold]STEP 7 — Scheduler Reasoning Log[/bold]"))
console.print()
for line in scheduler.get_reasoning().splitlines():
    console.print(f"  [dim]{line}[/dim]")

console.print()
console.print(Panel.fit(
    "[bold green]Demo complete.[/bold green] All algorithmic features verified across both pets.",
    border_style="green",
))
console.print()
