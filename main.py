from datetime import date

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich import box

from pet_planner_system import Owner, Pet, Task, Scheduler, ScheduledSlot
from agent import optimize_schedule  # pure Python — no API call needed

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

# ── 8. CONFLICT OPTIMIZER ────────────────────────────────────────────────────

console.print(Rule("[bold]STEP 8 — Conflict Optimizer (auto-resolve overlapping tasks)[/bold]"))
console.print()

# Build a fresh owner with tasks that have overlapping preferred_times
opt_owner = Owner(name="Demo", available_minutes=999)

opt_bella = Pet(name="Bella", species="dog", breed="Golden Retriever", age=3, color="golden")
opt_bella.add_task(Task(
    name="Morning Walk", category="walk", duration=30, priority="high",
    preferred_time="08:00",  # 08:00–08:30
))
opt_bella.add_task(Task(
    name="Feeding", category="feeding", duration=10, priority="high",
    preferred_time="08:10",  # 08:10–08:20  ← overlaps walk
))
opt_bella.add_task(Task(
    name="Vitamins", category="meds", duration=5, priority="medium",
    preferred_time="09:00",  # 09:00–09:05  ← no overlap
))

opt_milo = Pet(name="Milo", species="cat", breed="Siamese", age=5, color="cream")
opt_milo.add_task(Task(
    name="Grooming", category="grooming", duration=20, priority="medium",
    preferred_time="08:15",  # 08:15–08:35  ← overlaps walk and feeding
))
opt_milo.add_task(Task(
    name="Dental Treats", category="meds", duration=5, priority="low",
    preferred_time="09:10",  # 09:10–09:15  ← no overlap
))

opt_owner.add_pet(opt_bella)
opt_owner.add_pet(opt_milo)

# Show the conflicted schedule BEFORE optimization
opt_sched = Scheduler(owner=opt_owner, day_start="08:00")
opt_sched.generate_plan()
opt_sched.sort_by_time()

console.print("[bold]Before optimization:[/bold]")
before_table = Table(box=box.ROUNDED, header_style="bold blue")
before_table.add_column("Start")
before_table.add_column("End")
before_table.add_column("Task")
before_table.add_column("Pet", style="cyan")
before_table.add_column("Priority")

for slot in opt_sched.daily_plan:
    end_min = opt_sched._time_to_minutes(slot.start_time) + slot.task.duration
    end_str = opt_sched._minutes_to_time(end_min)
    color   = PRIORITY_COLORS.get(slot.task.priority, "white")
    pet_name = next(p.name for p in opt_owner.pets if slot.task in p.tasks)
    before_table.add_row(
        slot.start_time, end_str, slot.task.name, pet_name,
        f"[{color}]{slot.task.priority}[/{color}]",
    )

console.print(before_table)

before_conflicts = opt_sched.detect_conflicts()
console.print(f"  [red]⚠ {len(before_conflicts)} conflict(s) detected:[/red]")
for w in before_conflicts:
    console.print(f"    [red]{w}[/red]")

# Run the optimizer
console.print()
console.print("[bold]Running optimize_schedule()...[/bold]")
result = optimize_schedule(opt_owner, day_start="08:00")

# Show the resolved schedule AFTER optimization
opt_sched2 = Scheduler(owner=opt_owner, day_start="08:00")
opt_sched2.generate_plan()
opt_sched2.sort_by_time()

console.print()
console.print("[bold]After optimization:[/bold]")
after_table = Table(box=box.ROUNDED, header_style="bold blue")
after_table.add_column("Start")
after_table.add_column("End")
after_table.add_column("Task")
after_table.add_column("Pet", style="cyan")
after_table.add_column("Priority")

for slot in opt_sched2.daily_plan:
    end_min = opt_sched2._time_to_minutes(slot.start_time) + slot.task.duration
    end_str = opt_sched2._minutes_to_time(end_min)
    color   = PRIORITY_COLORS.get(slot.task.priority, "white")
    pet_name = next(p.name for p in opt_owner.pets if slot.task in p.tasks)
    after_table.add_row(
        slot.start_time, end_str, slot.task.name, pet_name,
        f"[{color}]{slot.task.priority}[/{color}]",
    )

console.print(after_table)

after_conflicts = opt_sched2.detect_conflicts()
if after_conflicts:
    console.print(f"  [yellow]⚠ {len(after_conflicts)} conflict(s) remain.[/yellow]")
else:
    console.print("  [green]✓ All conflicts resolved.[/green]")

console.print()
for line in result.splitlines():
    console.print(f"  [dim]{line}[/dim]")

# ── 9. AI AGENT (runs via Streamlit) ─────────────────────────────────────────

console.print()
console.print(Rule("[bold]STEP 9 — AI Agent (Lexa)[/bold]"))
console.print()
console.print(Panel(
    "\n"
    "  The AI agent is the primary interface of this app and runs inside [bold cyan]Streamlit[/bold cyan].\n"
    "  It cannot be demonstrated in a standalone script because it requires\n"
    "  live Groq API calls and Streamlit session state.\n\n"
    "  [bold]To run the full agent demo:[/bold]\n\n"
    "    [green]streamlit run app.py[/green]\n\n"
    "  Then open [cyan]http://localhost:8501[/cyan] and try:\n"
    "    • [italic]'Add my dog Bella, 3-year-old golden retriever'[/italic]\n"
    "    • [italic]'Generate a full care plan for Bella'[/italic]\n"
    "    • [italic]'Fix any schedule conflicts'[/italic]\n\n"
    "  [bold]What the agent does (agentic loop):[/bold]\n"
    "    1. Builds a system prompt with live owner + pet + task state\n"
    "    2. Sends user message + 8 tool schemas to Groq (llama-3.3-70b-versatile)\n"
    "    3. Executes whichever tools the model calls (mutates Owner/Pet/Task in memory)\n"
    "    4. Feeds tool results back — model self-verifies with list_tasks / get_pet_info\n"
    "    5. If mismatch → model corrects itself immediately\n"
    "    6. Loop repeats (max 10 iterations) until no more tool calls\n"
    "    7. Returns final natural-language response; app auto-saves + rebuilds schedule\n\n"
    "  All agent activity is logged to [bold]lexa.log[/bold] (DEBUG level).\n"
    "  Watch it live:  [green]tail -f lexa.log[/green]\n",
    title="[bold cyan]Lexa — AI Agent[/bold cyan]",
    border_style="cyan",
))

console.print()
console.print(Panel.fit(
    "[bold green]Demo complete.[/bold green] All algorithmic features verified across both pets.",
    border_style="green",
))
console.print()
