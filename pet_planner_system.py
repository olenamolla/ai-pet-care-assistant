from dataclasses import dataclass, field
from datetime import date, timedelta

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
RECURRENCE_DELTAS = {"daily": timedelta(days=1), "weekly": timedelta(weeks=1)}


@dataclass
class Pet:
    name: str
    species: str
    breed: str
    age: int
    color: str
    favorite_activities: list[str] = field(default_factory=list)
    special_instructions: str = ""
    tasks: list["Task"] = field(default_factory=list)

    def add_task(self, task: "Task") -> None:
        """Append a task to this pet's task list."""
        self.tasks.append(task)

    def remove_task(self, task: "Task") -> None:
        """Remove a task from this pet's task list."""
        self.tasks.remove(task)

    def update(self, **kwargs) -> None:
        """Update one or more pet attributes by keyword."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def summary(self) -> str:
        """Return a human-readable one-line description of this pet."""
        base = f"{self.name} — {self.age}-year-old {self.color} {self.breed} ({self.species})"
        if self.special_instructions:
            base += f" | Note: {self.special_instructions}"
        return base


@dataclass
class Task:
    name: str
    category: str  # walk, feeding, meds, enrichment, grooming
    duration: int  # in minutes
    priority: str  # high, medium, low
    frequency: int = 1
    is_completed: int = 0
    recurrence: str = "none"  # "none", "daily", or "weekly"
    due_date: date | None = None  # when this task is due
    preferred_time: str | None = None  # optional "HH:MM" start time

    def update(self, **kwargs) -> None:
        """Update one or more task attributes by keyword."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def mark_complete(self) -> None:
        """Increment completion count by one, up to the task's frequency."""
        if not self.is_fully_done():
            self.is_completed += 1

    def is_fully_done(self) -> bool:
        """Return True if all occurrences of this task are completed."""
        return self.is_completed >= self.frequency

    def total_time(self) -> int:
        """Return total daily time needed: duration * frequency."""
        return self.duration * self.frequency

    def create_next_occurrence(self) -> "Task | None":
        """Create a fresh Task for the next recurrence period.

        Uses timedelta to advance the due_date by 1 day (daily) or 7 days
        (weekly). Returns None for non-recurring tasks or tasks without a
        due_date. The returned Task has is_completed reset to 0.
        """
        delta = RECURRENCE_DELTAS.get(self.recurrence)
        if delta is None or self.due_date is None:
            return None
        return Task(
            name=self.name,
            category=self.category,
            duration=self.duration,
            priority=self.priority,
            frequency=self.frequency,
            recurrence=self.recurrence,
            due_date=self.due_date + delta,
            preferred_time=self.preferred_time,
        )


@dataclass
class ScheduledSlot:
    """A single scheduled occurrence of a task with a start time."""
    task: Task
    start_time: str  # e.g. "08:00"
    occurrence: int = 1  # which occurrence (1st, 2nd, etc.) for repeating tasks


class Owner:
    def __init__(self, name: str, available_minutes: int, preferences: str = ""):
        self.name = name
        self.available_minutes = available_minutes
        self.preferences = preferences
        self.pets: list[Pet] = []

    def update(self, **kwargs) -> None:
        """Update one or more owner attributes by keyword."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def add_pet(self, pet: Pet) -> None:
        """Register a pet under this owner."""
        self.pets.append(pet)

    def remove_pet(self, pet: Pet) -> None:
        """Remove a pet from this owner's list."""
        self.pets.remove(pet)

    def get_all_tasks(self) -> list[tuple[Pet, Task]]:
        """Collect all tasks across all pets as (pet, task) tuples."""
        all_tasks = []
        for pet in self.pets:
            for task in pet.tasks:
                all_tasks.append((pet, task))
        return all_tasks

    def filter_tasks(
        self,
        pet_name: str | None = None,
        completed: bool | None = None,
    ) -> list[tuple[Pet, Task]]:
        """Filter tasks by pet name and/or completion status.

        Args:
            pet_name: If provided, only include tasks belonging to this pet.
            completed: If True, only fully done tasks. If False, only
                       incomplete tasks. If None, include all.

        Returns:
            A filtered list of (pet, task) tuples.
        """
        results = self.get_all_tasks()

        if pet_name is not None:
            results = [
                (pet, task) for pet, task in results
                if pet.name.lower() == pet_name.lower()
            ]

        if completed is not None:
            results = [
                (pet, task) for pet, task in results
                if task.is_fully_done() == completed
            ]

        return results


class Scheduler:
    def __init__(self, owner: Owner, day_start: str = "08:00"):
        self.owner = owner
        self.day_start = day_start
        self.daily_plan: list[ScheduledSlot] = []
        self._unscheduled: list[Task] = []
        self._reasoning: list[str] = []

    def _minutes_to_time(self, total_minutes: int) -> str:
        """Convert total minutes since midnight to 'HH:MM' format."""
        hours = total_minutes // 60
        minutes = total_minutes % 60
        return f"{hours:02d}:{minutes:02d}"

    def _time_to_minutes(self, time_str: str) -> int:
        """Convert 'HH:MM' format to total minutes since midnight."""
        hours, minutes = time_str.split(":")
        return int(hours) * 60 + int(minutes)

    def generate_plan(self) -> list[ScheduledSlot]:
        """Build a daily schedule sorted by priority, fitting within the owner's time budget."""
        self.daily_plan = []
        self._unscheduled = []
        self._reasoning = []

        all_tasks = self.owner.get_all_tasks()
        sorted_tasks = sorted(
            all_tasks,
            key=lambda pt: PRIORITY_ORDER.get(pt[1].priority, 99),
        )

        remaining_minutes = self.owner.available_minutes
        current_minutes = self._time_to_minutes(self.day_start)

        day_end_minutes = 22 * 60  # spread multi-occurrence tasks up to 22:00

        for pet, task in sorted_tasks:
            time_needed = task.total_time()

            if time_needed <= remaining_minutes:
                if task.frequency > 1 and task.preferred_time is None:
                    # Spread occurrences evenly across the remaining day
                    span = max(day_end_minutes - current_minutes, task.frequency * task.duration)
                    interval = span // task.frequency
                    for occ in range(1, task.frequency + 1):
                        occ_start = current_minutes + (occ - 1) * interval
                        self.daily_plan.append(
                            ScheduledSlot(task=task, start_time=self._minutes_to_time(occ_start), occurrence=occ)
                        )
                    current_minutes += task.duration  # only block the first slot
                else:
                    for occ in range(1, task.frequency + 1):
                        if task.preferred_time is not None:
                            start = task.preferred_time
                        else:
                            start = self._minutes_to_time(current_minutes)
                        self.daily_plan.append(
                            ScheduledSlot(task=task, start_time=start, occurrence=occ)
                        )
                        if task.preferred_time is not None:
                            current_minutes = max(
                                current_minutes,
                                self._time_to_minutes(task.preferred_time) + task.duration,
                            )
                        else:
                            current_minutes += task.duration
                remaining_minutes -= time_needed
                self._reasoning.append(
                    f"Scheduled '{task.name}' ({task.priority} priority, "
                    f"{task.frequency}x{task.duration}min) for {pet.name}."
                )
            else:
                self._unscheduled.append(task)
                self._reasoning.append(
                    f"Dropped '{task.name}' ({task.priority} priority, "
                    f"{time_needed}min needed) — only {remaining_minutes}min left."
                )

        return self.daily_plan

    def sort_by_time(self) -> list[ScheduledSlot]:
        """Sort the daily plan chronologically by start_time.

        Uses sorted() with a lambda key that converts each slot's "HH:MM"
        string to total minutes for correct numerical ordering. Mutates
        self.daily_plan in place and returns the sorted list.
        """
        self.daily_plan = sorted(
            self.daily_plan,
            key=lambda slot: self._time_to_minutes(slot.start_time),
        )
        return self.daily_plan

    def mark_task_complete(self, pet: "Pet", task: Task) -> "Task | None":
        """Mark a task complete and auto-schedule the next recurrence.

        Increments the task's completion counter. Once all occurrences for
        the current period are done (is_fully_done), calls
        create_next_occurrence() to generate a new Task with an advanced
        due_date and adds it to the pet's task list.

        Returns the newly created Task, or None if the task is non-recurring
        or not yet fully done.
        """
        task.mark_complete()

        if task.is_fully_done():
            next_task = task.create_next_occurrence()
            if next_task is not None:
                pet.add_task(next_task)
                self._reasoning.append(
                    f"'{task.name}' completed for {pet.name}. "
                    f"Next {task.recurrence} occurrence created for {next_task.due_date}."
                )
                return next_task

        return None

    def detect_conflicts(self) -> list[str]:
        """Detect time overlaps between any two slots in the daily plan.

        Compares every pair of slots (O(n^2)) using interval overlap logic:
        two slots conflict when start_a < end_b and start_b < end_a. For
        each conflict, calculates the exact overlap duration in minutes.

        Returns a list of human-readable warning strings describing each
        conflict. An empty list means no conflicts were found.
        """
        warnings: list[str] = []
        slots = self.daily_plan

        for i in range(len(slots)):
            start_a = self._time_to_minutes(slots[i].start_time)
            end_a = start_a + slots[i].task.duration

            for j in range(i + 1, len(slots)):
                # Skip different occurrences of the same task
                if slots[i].task is slots[j].task:
                    continue

                start_b = self._time_to_minutes(slots[j].start_time)
                end_b = start_b + slots[j].task.duration

                # Overlap exists when each slot starts before the other ends
                if start_a < end_b and start_b < end_a:
                    overlap_start = max(start_a, start_b)
                    overlap_end = min(end_a, end_b)
                    overlap_min = overlap_end - overlap_start

                    warnings.append(
                        f"CONFLICT: '{slots[i].task.name}' "
                        f"({slots[i].start_time}–{self._minutes_to_time(end_a)}) "
                        f"overlaps with '{slots[j].task.name}' "
                        f"({slots[j].start_time}–{self._minutes_to_time(end_b)}) "
                        f"by {overlap_min} min"
                    )

        return warnings

    def get_reasoning(self) -> str:
        """Return a human-readable explanation of all scheduling decisions."""
        return "\n".join(self._reasoning)

    def get_unscheduled_tasks(self) -> list[Task]:
        """Return tasks that were dropped due to insufficient time."""
        return list(self._unscheduled)
