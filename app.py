import streamlit as st
from datetime import date

from studypath.models import Task, SchedulingProblem
from studypath.astar import astar_schedule
from studypath.cost import evaluate


# =========================================================
# PAGE SETUP
# =========================================================

# sets up the browser tab and page layout
# wide layout gives us more room for the dashboard design
st.set_page_config(
    page_title="StudyPath",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =========================================================
# CUSTOM STYLING
# =========================================================

# Streamlit already handles light/dark mode,
# so the CSS here mainly changes spacing, buttons, cards, and typography
# without forcing a specific background color
st.markdown(
    """
    <style>

    /* gives the main page more room and matches the Figma spacing better */
    .block-container {
        padding-top: 2.2rem;
        padding-bottom: 3rem;
        max-width: 1400px;
    }

    /* main page title */
    .study-title {
        font-size: 2.25rem;
        font-weight: 750;
        line-height: 1.15;
        margin-bottom: 0.35rem;
        color: var(--text-color);
    }

    /* subtitle underneath the main page title */
    .study-subtitle {
        opacity: 0.65;
        font-size: 1rem;
        margin-bottom: 1.5rem;
    }

    /* small purple heading used above the page title */
    .eyebrow {
        color: #6750C9;
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04rem;
        margin-bottom: 0.6rem;
    }

    /* rounds the buttons so they feel more modern */
    div.stButton > button,
    div.stFormSubmitButton > button {
        border-radius: 10px;
        font-weight: 600;
        min-height: 42px;
    }

    /* gives metric boxes a card-like appearance */
    div[data-testid="stMetric"] {
        border: 1px solid rgba(128, 128, 128, 0.18);
        border-radius: 14px;
        padding: 1rem 1.1rem;
        background-color: var(--secondary-background-color);
    }

    /* makes forms look more like the cards in the Figma */
    div[data-testid="stForm"] {
        border: 1px solid rgba(128, 128, 128, 0.18);
        border-radius: 16px;
        padding: 1.2rem;
        background-color: var(--secondary-background-color);
    }

    /* rounds Streamlit containers that use border=True */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 16px;
    }

    /* adds a divider between the sidebar and main page */
    section[data-testid="stSidebar"] {
        border-right: 1px solid rgba(128, 128, 128, 0.16);
    }

    /* reduces extra space around dividers */
    hr {
        margin-top: 1rem;
        margin-bottom: 1rem;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# SESSION STATE
# =========================================================

# Streamlit reruns the entire file every time something changes
# session state makes it easier to keep user data even after reruns

# stores all assignments the user adds
if "tasks" not in st.session_state:
    st.session_state.tasks = []

# stores the most recently generated schedule
if "schedule" not in st.session_state:
    st.session_state.schedule = None

# stores the SchedulingProblem used to generate the schedule
if "problem" not in st.session_state:
    st.session_state.problem = None

# controls whether we show the task list or the Add Task page
if "show_add_task" not in st.session_state:
    st.session_state.show_add_task = False

# saves the user's availability values
# default value is 2 hours per day
for short_day in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
    key = f"availability_{short_day}"

    if key not in st.session_state:
        st.session_state[key] = 2


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def get_availability():
    """
    Converts the Streamlit availability inputs into the dictionary
    format expected by SchedulingProblem.
    """

    return {
        "Mon": st.session_state.availability_Mon,
        "Tue": st.session_state.availability_Tue,
        "Wed": st.session_state.availability_Wed,
        "Thu": st.session_state.availability_Thu,
        "Fri": st.session_state.availability_Fri,
        "Sat": st.session_state.availability_Sat,
        "Sun": st.session_state.availability_Sun,
    }


def total_workload():
    """
    Adds up the estimated hours for all assignments.
    """

    return sum(task.hours for task in st.session_state.tasks)


def priority_label(priority):
    """
    Converts the numeric priority into something easier
    for the user to understand.
    """

    labels = {
        1: "Very low",
        2: "Low",
        3: "Medium",
        4: "High",
        5: "Very high",
    }

    return labels.get(priority, "Medium")


def difficulty_label(difficulty):
    """
    Converts the numeric difficulty into a readable label.
    """

    labels = {
        1: "Very easy",
        2: "Easy",
        3: "Medium",
        4: "Hard",
        5: "Very hard",
    }

    return labels.get(difficulty, "Medium")


def invalidate_schedule():
    """
    If the user changes their assignments or availability,
    the previous schedule is no longer based on the current data.
    """

    st.session_state.schedule = None
    st.session_state.problem = None


# =========================================================
# SIDEBAR
# =========================================================

# sidebar is used as the main navigation instead of tabs
# this matches the Figma better and keeps the workflow simple
with st.sidebar:

    st.markdown("## ✦ StudyPath")

    st.caption("A* powered study scheduling")

    st.divider()

    st.caption("YOUR WORKSPACE")

    # navigation between the three main parts of the app
    page = st.radio(
        "Navigation",
        [
            "Assignments",
            "Availability",
            "Study plan",
        ],
        label_visibility="collapsed",
    )

    st.divider()

    st.caption("THIS SEMESTER")

    st.markdown("**Fall 2026**")

    # shows hm assignments the user entered
    st.caption(
        f"{len(st.session_state.tasks)} active task"
        f"{'s' if len(st.session_state.tasks) != 1 else ''}"
    )

    st.divider()

    # small motivational card inspired by the Figma sidebar
    with st.container(border=True):
        st.markdown("### ✦")
        st.markdown("**A little structure.**")
        st.markdown("**A lot less stress.**")
        st.caption("Make room for your life.")

    st.write("")

    st.caption("A* powered scheduling")


# =========================================================
# ASSIGNMENTS PAGE
# =========================================================

if page == "Assignments":

    # =====================================================
    # ADD TASK PAGE
    # =====================================================

    # when the user clicks Add Task,
    # this page replaces the normal assignments view
    if st.session_state.show_add_task:

        st.caption("StudyPath / Add task")

        st.markdown(
            '<div class="eyebrow">One less thing to keep in your head</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            '<div class="study-title">Make it part of the plan.</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            '<div class="study-subtitle">'
            "Add the details. We'll make room for the work."
            "</div>",
            unsafe_allow_html=True,
        )

        # keeps the form centered and narrower like the Figma modal
        form_left, form_center, form_right = st.columns([1, 2.2, 1])

        with form_center:

            # using form keeps all values together until the user submits
            with st.form("add_task_form"):

                task_name = st.text_input(
                    "Task name",
                    placeholder="e.g. CPSC 481 project",
                )

                col1, col2 = st.columns(2)

                with col1:

                    due_date = st.date_input(
                        "Due date",
                        value=date.today(),
                        min_value=date.today(),
                    )

                with col2:

                    study_hours = st.number_input(
                        "Estimated study time",
                        min_value=1,
                        max_value=50,
                        value=2,
                        step=1,
                    )

                st.write("")

                priority = st.slider(
                    "Priority",
                    min_value=1,
                    max_value=5,
                    value=3,
                    help="1 = least urgent, 5 = most important",
                )

                st.caption(
                    f"Selected: {priority} · {priority_label(priority)}"
                )

                difficulty = st.slider(
                    "Difficulty",
                    min_value=1,
                    max_value=5,
                    value=3,
                    help="1 = light review, 5 = deep focus",
                )

                st.caption(
                    f"Selected: {difficulty} · "
                    f"{difficulty_label(difficulty)}"
                )

                st.write("")

                # explains why these values matter to A*
                st.info(
                    "✦ Your deadline, study time, priority, and "
                    "difficulty help A* find a plan that fits your "
                    "available hours."
                )

                submitted = st.form_submit_button(
                    "＋ Add task",
                    type="primary",
                    use_container_width=True,
                )

            # form submitted => create a Task object
            # using the same data structure expected by the backend
            if submitted:

                if not task_name.strip():

                    st.warning("Please enter a task name.")

                else:

                    new_task = Task(
                        name=task_name.strip(),
                        due=due_date,
                        hours=int(study_hours),
                        priority=int(priority),
                        difficulty=int(difficulty),
                    )

                    # saves task in session state so it stays on the page
                    st.session_state.tasks.append(new_task)

                    # if tasks change => old generated sched is no longer valid
                    invalidate_schedule()

                    # return back to the task list after adding
                    st.session_state.show_add_task = False

                    st.rerun()

            # lets the user go back without adding anything
            if st.button(
                "Cancel",
                use_container_width=True,
            ):
                st.session_state.show_add_task = False
                st.rerun()


    # =====================================================
    # NORMAL ASSIGNMENTS PAGE
    # =====================================================

    else:

        st.caption("My workspace  ›  Assignments")

        # splits the heading so the title is on the left
        # and Add Task button is on the right
        header_left, header_right = st.columns([4, 1])

        with header_left:

            st.markdown(
                '<div class="eyebrow">Plan ahead. Stress less.</div>',
                unsafe_allow_html=True,
            )

            st.markdown(
                '<div class="study-title">A clearer path to done.</div>',
                unsafe_allow_html=True,
            )

            st.markdown(
                '<div class="study-subtitle">'
                "Bring your deadlines together. Make space for what matters."
                "</div>",
                unsafe_allow_html=True,
            )

        with header_right:

            st.write("")
            st.write("")

            if st.button(
                "＋ Add task",
                type="primary",
                use_container_width=True,
            ):
                st.session_state.show_add_task = True
                st.rerun()

        # ----------------------------------------------
        # ASSIGNMENT SUMMARY
        # ----------------------------------------------

        availability = get_availability()

        # total number of hrs the student has available in one week
        weekly_capacity = sum(availability.values())

        # total estimated work from all current assignments
        work_hours = total_workload()

        metric1, metric2, metric3 = st.columns(3)

        metric1.metric(
            "Active tasks",
            len(st.session_state.tasks),
        )

        metric2.metric(
            "Study time needed",
            f"{work_hours} h",
        )

        metric3.metric(
            "Weekly availability",
            f"{weekly_capacity} h",
            delta=f"{weekly_capacity - work_hours} h remaining",
            delta_color="normal",
        )

        st.write("")

        # ----------------------------------------------
        # CURRENT ASSIGNMENTS
        # ----------------------------------------------

        with st.container(border=True):

            list_header, list_action = st.columns([4, 1])

            with list_header:
                st.markdown("### Your assignments")

            with list_action:
                st.caption(
                    f"{len(st.session_state.tasks)} task"
                    f"{'s' if len(st.session_state.tasks) != 1 else ''}"
                )

            # show empty message if the user has not added anything yet
            if not st.session_state.tasks:

                st.info(
                    "You do not have any assignments yet. "
                    "Add your first task to start planning."
                )

            else:

                # header row for the assignment table
                head1, head2, head3, head4, head5, head6 = st.columns(
                    [3, 2, 1.4, 1.4, 1.4, 0.8]
                )

                head1.caption("TASK")
                head2.caption("DUE DATE")
                head3.caption("STUDY TIME")
                head4.caption("PRIORITY")
                head5.caption("DIFFICULTY")
                head6.caption("")

                st.divider()

                # display every task the user added
                for index, task in enumerate(st.session_state.tasks):

                    row1, row2, row3, row4, row5, row6 = st.columns(
                        [3, 2, 1.4, 1.4, 1.4, 0.8]
                    )

                    with row1:
                        st.markdown(f"**{task.name}**")

                    with row2:
                        st.write(task.due.strftime("%b %d, %Y"))

                    with row3:
                        st.write(f"◷ {task.hours} h")

                    with row4:
                        st.write(priority_label(task.priority))

                    with row5:
                        st.write(difficulty_label(task.difficulty))

                    with row6:

                        # remove the selected assignment from the list
                        if st.button(
                            "×",
                            key=f"delete_task_{index}",
                            help="Remove this task",
                        ):

                            st.session_state.tasks.pop(index)

                            # remove previous schedule too
                            # bc the task list has changed
                            invalidate_schedule()

                            st.rerun()

                    st.divider()

                st.caption(
                    f"{total_workload()} total study hours"
                )

        st.write("")

        # ----------------------------------------------
        # BOTTOM STATUS CARD
        # ----------------------------------------------

        # gives student a quick warning/success message depending
        # on whether their weekly availability can handle the workload
        with st.container(border=True):

            cta_text, cta_button = st.columns([4, 1.4])

            with cta_text:

                if work_hours <= weekly_capacity:

                    st.markdown(
                        "### ✦ Your week has room to breathe."
                    )

                    st.caption(
                        f"{work_hours} h of work, "
                        f"{weekly_capacity} h available. "
                        "Let A* find a balanced path."
                    )

                else:

                    st.markdown(
                        "### ✦ This week is looking busy."
                    )

                    st.caption(
                        f"You need {work_hours} h but currently have "
                        f"{weekly_capacity} h available."
                    )

            with cta_button:

                st.write("")

                if st.button(
                    "✦ Review availability",
                    use_container_width=True,
                ):
                    st.info(
                        "Select Availability from the sidebar "
                        "to adjust your study hours."
                    )


# =========================================================
# AVAILABILITY PAGE
# =========================================================

elif page == "Availability":

    st.caption("My workspace  ›  Availability")

    st.markdown(
        '<div class="eyebrow">Make room for focus</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="study-title">Your time, on your terms.</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="study-subtitle">'
        "Choose how much time you can study. "
        "StudyPath works around the rest."
        "</div>",
        unsafe_allow_html=True,
    )

    # splits the main availability controls and summary card
    availability_main, availability_summary = st.columns(
        [3.2, 1.25],
        gap="large",
    )

    with availability_main:

        with st.container(border=True):

            st.markdown("### Weekly availability")

            st.caption(
                "Set the number of study hours you normally have "
                "available each day."
            )

            # backend uses short weekday names,
            # so keep both the short and full versions here
            days = [
                ("Mon", "Monday"),
                ("Tue", "Tuesday"),
                ("Wed", "Wednesday"),
                ("Thu", "Thursday"),
                ("Fri", "Friday"),
                ("Sat", "Saturday"),
                ("Sun", "Sunday"),
            ]

            # put days into two columns so page doesnt feel too long
            left_days, right_days = st.columns(2)

            for index, (short_day, full_day) in enumerate(days):

                target_column = (
                    left_days if index < 4 else right_days
                )

                with target_column:

                    st.number_input(
                        full_day,
                        min_value=0,
                        max_value=12,
                        step=1,
                        key=f"availability_{short_day}",
                        help=(
                            "How many hours are you usually "
                            "available to study on this day?"
                        ),
                    )

            # rebuild availability after inputs update
            current_availability = get_availability()

    with availability_summary:

        # total weekly study capacity
        weekly_capacity = sum(current_availability.values())

        # current total assignment workload
        needed = total_workload()

        with st.container(border=True):

            st.markdown("### Your weekly capacity")

            st.metric(
                "Hours available",
                weekly_capacity,
            )

            st.caption("A little every day adds up.")

            st.divider()

            # show a simple bar for each day's available hours
            for short_day, full_day in [
                ("Mon", "Mon"),
                ("Tue", "Tue"),
                ("Wed", "Wed"),
                ("Thu", "Thu"),
                ("Fri", "Fri"),
                ("Sat", "Sat"),
                ("Sun", "Sun"),
            ]:

                hours = current_availability[short_day]

                label_col, bar_col, hours_col = st.columns(
                    [0.6, 2.2, 0.5]
                )

                label_col.caption(full_day)

                with bar_col:
                    st.progress(hours / 12)

                hours_col.caption(f"{hours} h")

        with st.container(border=True):

            st.markdown("### ✦ Flexible by design")

            st.caption(
                "A* schedules within these hours and balances "
                "your workload against each deadline."
            )

            st.markdown("**You stay in control.**")

    st.write("")

    # give the student a quick warning if they may not have enough time
    if needed == 0:

        st.info(
            "Add assignments first so StudyPath can compare "
            "your workload with your availability."
        )

    elif weekly_capacity >= needed:

        st.success(
            f"✓ {needed} h needed · "
            f"{weekly_capacity} h available. "
            "You're ready to plan."
        )

    else:

        st.warning(
            f"{needed} h needed · "
            f"{weekly_capacity} h available. "
            "Your schedule may contain missed or late work."
        )

    st.caption(
        "Your availability is saved automatically while this app is open."
    )


# =========================================================
# STUDY PLAN PAGE
# =========================================================

elif page == "Study plan":

    st.caption("My workspace  ›  Study plan")

    header_left, header_right = st.columns([4, 1.4])

    with header_left:

        st.markdown(
            '<div class="eyebrow">'
            "A little focus. A lot of progress."
            "</div>",
            unsafe_allow_html=True,
        )

        st.markdown(
            '<div class="study-title">'
            "Your week, thoughtfully planned."
            "</div>",
            unsafe_allow_html=True,
        )

        st.markdown(
            '<div class="study-subtitle">'
            "A balanced path through your deadlines, "
            "with time left for you."
            "</div>",
            unsafe_allow_html=True,
        )

    with header_right:

        st.write("")
        st.write("")

        generate_clicked = st.button(
            "✦ Generate plan",
            type="primary",
            use_container_width=True,
        )

    availability = get_availability()

    # ----------------------------------------------
    # RUN A* ALGORITHM
    # ----------------------------------------------

    if generate_clicked:

        # user needs at least one assignment before A* can run
        if not st.session_state.tasks:

            st.warning(
                "Add at least one assignment before generating a plan."
            )

        # scheduler also needs at least some available study time
        elif sum(availability.values()) == 0:

            st.warning(
                "Add some study availability before generating a plan."
            )

        else:

            try:

                # builds scheduling problem using tasks
                # and availability entered by user
                problem = SchedulingProblem(
                    tasks=st.session_state.tasks,
                    start=date.today(),
                    availability=availability,
                )

                # run the A* algo from the backend
                with st.spinner(
                    "A* is finding a balanced study plan..."
                ):

                    schedule = astar_schedule(problem)

                # store results so they stay visible after reruns
                st.session_state.problem = problem
                st.session_state.schedule = schedule

            except Exception as error:

                # prevents the app from fully crashing
                # if something unexpected happens in the backend
                st.error(
                    f"StudyPath could not generate a schedule: {error}"
                )


    # ----------------------------------------------
    # EMPTY SCHEDULE STATE
    # ----------------------------------------------

    # show this before a schedule has been generated
    if st.session_state.schedule is None:

        with st.container(border=True):

            st.markdown("### No study plan yet")

            st.caption(
                "Once your assignments and availability are ready, "
                "generate a plan to let A* organize your study time."
            )

            left, middle, right = st.columns(3)

            left.metric(
                "Tasks",
                len(st.session_state.tasks),
            )

            middle.metric(
                "Study time needed",
                f"{total_workload()} h",
            )

            right.metric(
                "Weekly availability",
                f"{sum(availability.values())} h",
            )


    # ----------------------------------------------
    # GENERATED SCHEDULE
    # ----------------------------------------------

    # ONLY show results after a schedule has been generated
    else:

        schedule = st.session_state.schedule
        problem = st.session_state.problem

        # evaluate generated sched using backend cost function
        metrics = evaluate(
            problem,
            schedule.assignment,
        )

        # total hours actually placed into the schedule
        scheduled_hours = (
            total_workload() - int(metrics["missed_hours"])
        )

        # total number of available study hours for the week
        capacity = sum(availability.values())

        # remaining unused study capacity
        free_hours = max(
            0,
            capacity - scheduled_hours,
        )

        # ------------------------------------------
        # PERFORMANCE OVERVIEW
        # ------------------------------------------

        summary1, summary2, summary3, summary4 = st.columns(4)

        summary1.metric(
            "Study time scheduled",
            f"{scheduled_hours} h",
        )

        summary2.metric(
            "Free time remaining",
            f"{free_hours} h",
        )

        summary3.metric(
            "Missed study hours",
            int(metrics["missed_hours"]),
        )

        summary4.metric(
            "Tasks on time",
            f'{int(metrics["tasks_on_time"])}/{int(metrics["tasks"])}',
        )

        st.write("")

        plan_main, plan_side = st.columns(
            [3.2, 1.25],
            gap="large",
        )

        # ------------------------------------------
        # DAILY STUDY SCHEDULE
        # ------------------------------------------

        with plan_main:

            with st.container(border=True):

                st.markdown("### Your study schedule")

                # convert raw schedule into easier format:
                # each date maps to tasks and how many hours should be studied
                schedule_by_day = schedule.by_day()

                if not schedule_by_day:

                    st.warning(
                        "There were no study sessions to display."
                    )

                else:

                    # display one section for each day in the schedule
                    for day, tasks_for_day in sorted(
                        schedule_by_day.items()
                    ):

                        st.markdown(
                            f"#### {day.strftime('%A, %B %d')}"
                        )

                        for task_name, hours in tasks_for_day.items():

                            with st.container(border=True):

                                task_col, hour_col = st.columns(
                                    [4, 1]
                                )

                                with task_col:
                                    st.markdown(
                                        f"**{task_name}**"
                                    )

                                with hour_col:
                                    st.markdown(
                                        f"**{hours} h**"
                                    )

                        st.write("")

        # ------------------------------------------
        # PLAN EXPLANATION
        # ------------------------------------------

        with plan_side:

            with st.container(border=True):

                st.caption("FIRST UP")

                first_day = None
                first_task = None

                schedule_by_day = schedule.by_day()

                # shows the first scheduled task as a quick summary
                if schedule_by_day:

                    first_day = sorted(
                        schedule_by_day.keys()
                    )[0]

                    first_task = next(
                        iter(schedule_by_day[first_day])
                    )

                    st.markdown(
                        f"### {first_day.strftime('%A, %b %d')}"
                    )

                    st.markdown(
                        f"**{first_task}**"
                    )

                    st.caption(
                        f"{schedule_by_day[first_day][first_task]} "
                        "study hour(s)"
                    )

            # gives normal users a simple explanation
            # without exposing all of the algorithm details right away
            with st.container(border=True):

                st.markdown("### ✦ A smarter path, explained.")

                st.markdown("**✓ Deadlines come first**")

                st.caption(
                    "The scheduler considers each task's deadline "
                    "when deciding where study time should go."
                )

                st.markdown("**✓ Hard work, broken down**")

                st.caption(
                    "Assignments can be spread across multiple days "
                    "instead of being left until the deadline."
                )

                st.markdown("**✓ Priorities matter**")

                st.caption(
                    "Higher-priority tasks receive larger penalties "
                    "when they are late or missed."
                )

        st.write("")

        # ------------------------------------------
        # ALGORITHM DETAILS
        # ------------------------------------------

        # hidden by default so regular users
        # are not overwhelmed by the AI/debugging info
        with st.expander(
            "How did A* make this plan?"
        ):

            detail1, detail2, detail3, detail4 = st.columns(4)

            detail1.metric(
                "Schedule cost",
                f'{metrics["total"]:.2f}',
            )

            detail2.metric(
                "States explored",
                schedule.expanded,
            )

            detail3.metric(
                "Runtime",
                f"{schedule.runtime_s:.3f}s",
            )

            detail4.metric(
                "Optimal",
                "Yes" if schedule.optimal else "No",
            )

            st.divider()

            st.markdown("#### Cost breakdown")

            cost1, cost2, cost3, cost4 = st.columns(4)

            cost1.metric(
                "Late cost",
                f'{metrics["late_cost"]:.2f}',
            )

            cost2.metric(
                "Missed cost",
                f'{metrics["missed_cost"]:.2f}',
            )

            cost3.metric(
                "Cramming cost",
                f'{metrics["cram_cost"]:.2f}',
            )

            cost4.metric(
                "Early study cost",
                f'{metrics["early_cost"]:.2f}',
            )

        st.caption(
            "Generated with A* search · "
            "Based on deadlines, priority, difficulty, "
            "workload, and availability."
        )