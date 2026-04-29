import logging

import streamlit as st
from pet_planner_system import Owner, Scheduler
from persistence import save_owners, load_owners
from agent import run_agent, get_api_key, optimize_schedule  # also sets up lexa logger

logger = logging.getLogger("lexa.app")

PRIORITY_ICONS = {"high": "🔴", "medium": "🟡", "low": "🟢"}
CATEGORY_ICONS = {
    "walk": "🚶", "feeding": "🍽️", "meds": "💊",
    "enrichment": "🧩", "grooming": "✂️",
}

st.set_page_config(page_title="Lexa & Friends", page_icon="🐈", layout="wide")

# ── Session state defaults ────────────────────────────────────────────────────
if "owners" not in st.session_state:
    st.session_state.owners = load_owners()
    logger.info("app startup: loaded %d owner(s) from disk", len(st.session_state.owners))
if "schedulers" not in st.session_state:
    st.session_state.schedulers = {}
if "active_owner" not in st.session_state:
    st.session_state.active_owner = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = {}  # owner_name -> list of {role, content}


# ================================================================
# SIDEBAR — Owner setup only (pets + tasks handled by AI)
# ================================================================
with st.sidebar:
    st.markdown("""
<div style="margin-bottom: 0.25rem;">
    <span style="font-size: 1.6rem; font-weight: 800; color: #3d2b6b; letter-spacing: -0.5px;">
        Lexa <span style="color: #a07cd4;">&</span> Friends
    </span><br>
    <span style="font-size: 1.4rem; letter-spacing: 2px;">🐈 🐈‍⬛ 🐱 🐱</span><br>
    <span style="font-size: 0.8rem; color: #888;">Your AI pet care planning assistant</span>
</div>
""", unsafe_allow_html=True)

    st.header("Owner Setup")
    owner_name = st.text_input("Your name", value="Jordan")
    available_minutes = st.slider(
        "Available minutes per day", min_value=10, max_value=480, value=90, step=5,
    )
    if st.button("Save Owner", use_container_width=True):
        if owner_name.strip() == "":
            st.error("Owner name cannot be empty.")
        elif owner_name in st.session_state.owners:
            st.session_state.owners[owner_name].available_minutes = int(available_minutes)
            st.session_state.schedulers.pop(owner_name, None)
            logger.info("app: updated owner '%s' — available_minutes=%d", owner_name, available_minutes)
            st.success(f"Updated {owner_name} to {available_minutes} min/day")
        else:
            st.session_state.owners[owner_name] = Owner(
                name=owner_name, available_minutes=int(available_minutes),
            )
            st.session_state.chat_history[owner_name] = []
            logger.info("app: created new owner '%s' — available_minutes=%d", owner_name, available_minutes)
            st.success(f"Welcome, {owner_name}! Use the AI Assistant tab to add your pets.")
        st.session_state.active_owner = owner_name
        save_owners(st.session_state.owners)
        logger.info("app: saved all owners to disk (%d owner(s))", len(st.session_state.owners))

    if not st.session_state.owners:
        st.info("Save an owner to get started.")
        st.stop()

    st.divider()

    st.header("Switch Owner")
    owner_names = list(st.session_state.owners.keys())
    active_name = st.selectbox(
        "Active owner",
        owner_names,
        index=owner_names.index(st.session_state.active_owner)
        if st.session_state.active_owner in owner_names else 0,
        key="owner_selector",
    )
    st.session_state.active_owner = active_name
    owner = st.session_state.owners[active_name]

    st.caption(
        f"**{owner.name}** — {owner.available_minutes} min/day | "
        f"{len(owner.pets)} pet(s) | {len(owner.get_all_tasks())} task(s)"
    )

    st.divider()

    if owner.pets:
        st.markdown("**Your pets:**")
        for p in owner.pets:
            st.markdown(f"- {p.summary()}")
        st.caption("Use the AI Assistant tab to add, edit, or remove pets and tasks.")
    else:
        st.info("No pets yet — use the AI Assistant tab to add your first pet.")

    st.divider()

    if st.button("💾 Save Data", use_container_width=True):
        save_owners(st.session_state.owners)
        st.success("Data saved.")


# ================================================================
# MAIN AREA
# ================================================================
owner = st.session_state.owners[st.session_state.active_owner]
active_name = st.session_state.active_owner

# Auto-generate schedule on page load if tasks exist but no scheduler cached
if active_name not in st.session_state.schedulers and owner.get_all_tasks():
    _s = Scheduler(owner=owner, day_start="08:00")
    _s.generate_plan()
    _s.sort_by_time()
    st.session_state.schedulers[active_name] = _s
    logger.info("app: auto-generated schedule for '%s' on page load (%d slots)", active_name, len(_s.daily_plan))

st.markdown(f"""
<div style="background: linear-gradient(135deg, #f5f0ff 0%, #fff0fb 100%);
     border-radius: 14px; padding: 1.2rem 1.8rem; margin-bottom: 1rem;
     display: flex; align-items: center; gap: 1rem;">
    <div>
        <div style="font-size: 2rem; font-weight: 900; color: #3d2b6b;
                    letter-spacing: -1px; line-height: 1.1;">
            Lexa <span style="color: #a07cd4;">&</span> Friends
        </div>
        <div style="font-size: 1.3rem; letter-spacing: 3px; margin: 2px 0 4px 0;">
            🐈 🐈‍⬛ 🐱 🐱
        </div>
        <div style="font-size: 0.9rem; color: #7c5cbf;">
            {owner.name}'s dashboard
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

tab_ai, tab_schedule, tab_progress, tab_tasks, tab_owners = st.tabs([
    "🤖 AI Assistant",
    "📅 Today's Schedule",
    "✅ Track Progress",
    "📋 All Tasks",
    "👥 All Owners",
])


# ── Tab 1: AI Assistant ────────────────────────────────────────────────────────
with tab_ai:
    api_key = get_api_key()

    if not api_key:
        st.error(
            "No API key found. Create a `.env` file in the project folder with:\n\n"
            "```\nGROQ_API_KEY=gsk_...\n```"
        )
        st.stop()

    st.markdown("""
<div style="background: linear-gradient(135deg, #f0f4ff 0%, #fdf0ff 100%);
     border-left: 5px solid #7c5cbf;
     border-radius: 10px;
     padding: 1.2rem 1.6rem;
     margin-bottom: 1rem;">
    <p style="font-size: 1.15rem; font-weight: 600; color: #3d2b6b; margin: 0 0 0.5rem 0;">
        🐾 Chat with your AI care assistant
    </p>
    <p style="font-size: 1rem; color: #555; margin: 0 0 0.75rem 0; line-height: 1.6;">
        Tell it about your pets and it will create their profiles, suggest care plans,
        and manage all tasks for you.
    </p>
    <p style="font-size: 0.88rem; color: #7c5cbf; margin: 0;">
        💡 <em>Try: "Add my dog Bella, she's a 3-year-old golden retriever who needs daily walks and takes thyroid medication"</em>
    </p>
</div>
""", unsafe_allow_html=True)
    st.divider()

    if active_name not in st.session_state.chat_history:
        st.session_state.chat_history[active_name] = []

    history = st.session_state.chat_history[active_name]

    for msg in history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("Tell me about your pet, or ask me to add/change tasks...")

    if user_input:
        with st.chat_message("user"):
            st.markdown(user_input)

        claude_history = [
            {"role": m["role"], "content": m["content"]}
            for m in history
        ]

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                logger.info("app: invoking agent for owner='%s' — message: %.120s", active_name, user_input)
                response = run_agent(
                    user_message=user_input,
                    owner=owner,
                    chat_history=claude_history,
                    api_key=api_key,
                )
            st.markdown(response)

        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": response})

        save_owners(st.session_state.owners)
        logger.info("app: auto-saved after agent action — owner='%s'", active_name)
        # Auto-regenerate schedule so Today's Schedule tab stays current
        if owner.get_all_tasks():
            day_start = st.session_state.get("day_start", "08:00")
            scheduler = Scheduler(owner=owner, day_start=day_start)
            scheduler.generate_plan()
            scheduler.sort_by_time()
            st.session_state.schedulers[active_name] = scheduler
            logger.info("app: auto-regenerated schedule for '%s' (%d slots)", active_name, len(scheduler.daily_plan))
        else:
            st.session_state.schedulers.pop(active_name, None)
        st.rerun()


# ── Tab 2: Today's Schedule ────────────────────────────────────────────────────
with tab_schedule:
    all_tasks = owner.get_all_tasks()
    if not all_tasks:
        st.info("No tasks yet. Use the **AI Assistant** tab to add pets and tasks first.")
    else:
        col_start, col_gen = st.columns([2, 1])
        with col_start:
            day_start = st.text_input("Day starts at", value="08:00", key="day_start")
        with col_gen:
            st.markdown("<br>", unsafe_allow_html=True)
            generate = st.button("Generate Schedule", use_container_width=True, type="primary")

        if generate:
            scheduler = Scheduler(owner=owner, day_start=day_start)
            scheduler.generate_plan()
            scheduler.sort_by_time()
            st.session_state.schedulers[active_name] = scheduler
            logger.info("app: manually generated schedule for '%s' (%d slots, day_start=%s)",
                        active_name, len(scheduler.daily_plan), day_start)

        scheduler = st.session_state.schedulers.get(active_name)

        if scheduler and scheduler.daily_plan:
            total_scheduled = len(scheduler.daily_plan)
            total_minutes = sum(s.task.duration for s in scheduler.daily_plan)
            remaining = owner.available_minutes - total_minutes
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            col_m1.metric("Scheduled", total_scheduled)
            col_m2.metric("Planned", f"{total_minutes} min")
            col_m3.metric("Remaining", f"{remaining} min")
            col_m4.metric("Budget", f"{owner.available_minutes} min")

            st.markdown("---")

            task_to_pet = {id(task): pet for pet, task in owner.get_all_tasks()}

            for slot in scheduler.daily_plan:
                t = slot.task
                cat_icon = CATEGORY_ICONS.get(t.category, "📌")
                pri_icon = PRIORITY_ICONS.get(t.priority, "⚪")
                occ_label = f" (#{slot.occurrence})" if t.frequency > 1 else ""
                rec_label = f" | Repeats {t.recurrence}" if t.recurrence != "none" else ""
                pet = task_to_pet.get(id(t))
                pet_label = f" &nbsp;|&nbsp; 🐾 {pet.name}" if pet else ""

                with st.container():
                    col_time, col_detail = st.columns([1, 4])
                    with col_time:
                        st.markdown(f"### {slot.start_time}")
                    with col_detail:
                        st.markdown(
                            f"**{cat_icon} {t.name}**{occ_label}"
                            + (f" &nbsp;—&nbsp; 🐾 {pet.name}" if pet else "")
                            + f"  \n{pri_icon} {t.priority} &nbsp;|&nbsp; "
                            f"{t.duration} min &nbsp;|&nbsp; "
                            f"{t.category}{rec_label}"
                        )
                    st.divider()

            conflicts = scheduler.detect_conflicts()
            if conflicts:
                st.subheader("⚠️ Schedule Conflicts")
                for warning in conflicts:
                    st.error(f"**Time Overlap Detected**\n\n{warning}")

                if st.button("🔧 Fix Conflicts Automatically", type="primary", use_container_width=True):
                    result = optimize_schedule(owner, day_start)
                    # Rebuild schedule with updated preferred_times
                    scheduler = Scheduler(owner=owner, day_start=day_start)
                    scheduler.generate_plan()
                    scheduler.sort_by_time()
                    st.session_state.schedulers[active_name] = scheduler
                    save_owners(st.session_state.owners)
                    st.success(result)
                    st.rerun()
            else:
                st.success("No scheduling conflicts — you're all set!")

            unscheduled = scheduler.get_unscheduled_tasks()
            if unscheduled:
                st.subheader("Could Not Fit")
                for task in unscheduled:
                    icon = PRIORITY_ICONS.get(task.priority, "⚪")
                    st.warning(
                        f"**{task.name}** ({icon} {task.priority}) needs "
                        f"{task.total_time()} min. Ask the AI to shorten it or free up time."
                    )

            with st.expander("View Scheduling Reasoning"):
                st.code(scheduler.get_reasoning(), language=None)

        elif scheduler:
            st.info("No tasks to schedule. Use the AI Assistant tab to add tasks.")
        else:
            st.info("Click **Generate Schedule** to build your daily plan.")


# ── Tab 3: Track Progress ──────────────────────────────────────────────────────
with tab_progress:
    scheduler = st.session_state.schedulers.get(active_name)

    if not scheduler or not scheduler.daily_plan:
        st.info("Generate a schedule first in the **Today's Schedule** tab.")
    else:
        st.subheader("Mark Tasks Complete")

        for slot in scheduler.daily_plan:
            t = slot.task
            cat_icon = CATEGORY_ICONS.get(t.category, "📌")
            done_ratio = t.is_completed / t.frequency
            status = "✅ Done" if t.is_fully_done() else f"⏳ {t.is_completed}/{t.frequency}"

            col_info, col_bar = st.columns([2, 3])
            with col_info:
                occ_label = f" #{slot.occurrence}" if t.frequency > 1 else ""
                st.markdown(f"**{cat_icon} {t.name}**{occ_label} — {status}")
            with col_bar:
                st.progress(done_ratio)

        st.markdown("---")

        slot_labels = [
            f"{s.start_time} — {s.task.name}"
            + (f" #{s.occurrence}" if s.task.frequency > 1 else "")
            for s in scheduler.daily_plan
        ]
        selected_slot_label = st.selectbox("Select a task to complete", slot_labels)
        if st.button("Mark Complete", type="primary", use_container_width=True):
            slot_idx = slot_labels.index(selected_slot_label)
            slot = scheduler.daily_plan[slot_idx]
            pet = next(p for p in owner.pets for t in p.tasks if t is slot.task)
            next_task = scheduler.mark_task_complete(pet, slot.task)
            if slot.task.is_fully_done():
                logger.info("app: task fully completed — '%s' for pet '%s' (owner '%s')",
                            slot.task.name, pet.name, active_name)
                st.success(f"'{slot.task.name}' fully completed!")
                st.balloons()
                if next_task:
                    logger.info("app: recurrence task created — '%s' due %s", next_task.name, next_task.due_date)
                    st.info(
                        f"Next {slot.task.recurrence} occurrence of "
                        f"'{next_task.name}' auto-created for **{next_task.due_date}**."
                    )
                save_owners(st.session_state.owners)
                st.rerun()
            else:
                logger.info("app: task partial completion — '%s' %d/%d for pet '%s'",
                            slot.task.name, slot.task.is_completed, slot.task.frequency, pet.name)
                st.success(
                    f"'{slot.task.name}' — "
                    f"{slot.task.is_completed}/{slot.task.frequency} completions"
                )
                st.rerun()


# ── Tab 4: All Tasks ───────────────────────────────────────────────────────────
with tab_tasks:
    all_tasks = owner.get_all_tasks()
    if not all_tasks:
        st.info("No tasks yet. Use the **AI Assistant** tab to get started.")
    else:
        st.subheader(f"{owner.name}'s Task List")

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            filter_pet = st.selectbox(
                "Filter by pet", ["All"] + [p.name for p in owner.pets], key="filter_pet"
            )
        with col_f2:
            filter_status = st.selectbox(
                "Filter by status", ["All", "Incomplete", "Complete"], key="filter_status"
            )

        pet_filter = None if filter_pet == "All" else filter_pet
        completed_filter = (
            None if filter_status == "All" else filter_status == "Complete"
        )
        filtered = owner.filter_tasks(pet_name=pet_filter, completed=completed_filter)

        if filtered:
            STATUS_ICONS = {True: "✅", False: "⏳"}
            st.table([
                {
                    "Pet": pet.name,
                    "Task": f"{CATEGORY_ICONS.get(task.category, '📌')} {task.name}",
                    "Priority": f"{PRIORITY_ICONS.get(task.priority, '⚪')} {task.priority}",
                    "Duration": f"{task.duration} min",
                    "Freq.": f"{task.frequency}x/day",
                    "Status": (
                        f"{STATUS_ICONS[task.is_fully_done()]} "
                        f"{'Done' if task.is_fully_done() else f'{task.is_completed}/{task.frequency}'}"
                    ),
                    "Repeats": task.recurrence if task.recurrence != "none" else "-",
                    "Due": str(task.due_date) if task.due_date else "-",
                }
                for pet, task in filtered
            ])

            total = len(filtered)
            done = sum(1 for _, t in filtered if t.is_fully_done())
            st.caption(f"Showing {total} tasks — {done} complete, {total - done} remaining")
        else:
            st.info("No tasks match the current filter.")


# ── Tab 5: All Owners ─────────────────────────────────────────────────────────
with tab_owners:
    st.subheader("All Owners Overview")

    if not st.session_state.owners:
        st.info("No owners yet.")
    else:
        for oname, o in st.session_state.owners.items():
            is_active = oname == active_name
            label = f"**{o.name}** (active)" if is_active else f"**{o.name}**"

            with st.container():
                st.markdown(f"### {label}")
                col_s1, col_s2, col_s3 = st.columns(3)
                col_s1.metric("Available", f"{o.available_minutes} min/day")
                col_s2.metric("Pets", len(o.pets))
                col_s3.metric("Tasks", len(o.get_all_tasks()))

                if o.pets:
                    for p in o.pets:
                        with st.expander(f"{p.name} — {p.species}, {p.breed}"):
                            if p.tasks:
                                st.table([
                                    {
                                        "Task": f"{CATEGORY_ICONS.get(t.category, '📌')} {t.name}",
                                        "Priority": f"{PRIORITY_ICONS.get(t.priority, '⚪')} {t.priority}",
                                        "Duration": f"{t.duration} min",
                                        "Freq.": f"{t.frequency}x/day",
                                        "Repeats": t.recurrence if t.recurrence != "none" else "-",
                                    }
                                    for t in p.tasks
                                ])
                            else:
                                st.caption("No tasks for this pet yet.")

                sched = st.session_state.schedulers.get(oname)
                if sched and sched.daily_plan:
                    with st.expander("View Schedule"):
                        st.table([
                            {
                                "Time": s.start_time,
                                "Task": f"{CATEGORY_ICONS.get(s.task.category, '📌')} {s.task.name}",
                                "Duration": f"{s.task.duration} min",
                                "Priority": f"{PRIORITY_ICONS.get(s.task.priority, '⚪')} {s.task.priority}",
                            }
                            for s in sched.daily_plan
                        ])
                        conflicts = sched.detect_conflicts()
                        if conflicts:
                            for w in conflicts:
                                st.error(w)
                        else:
                            st.success("No conflicts")
                else:
                    st.caption("No schedule generated yet.")

                st.divider()
