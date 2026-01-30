import streamlit as st
import google.generativeai as genai
import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pathlib import Path

# --- CONFIGURATION ---
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY", "")
DATA_DIR = Path(__file__).parent / "data"
JOURNAL_DIR = DATA_DIR / "journal"
CONTEXT_FILE = DATA_DIR / "context.md"
TASKS_FILE = DATA_DIR / "tasks.json"
CHAT_HISTORY_FILE = DATA_DIR / "chat_history.json"
STREAK_FILE = DATA_DIR / "streak.json"
ENERGY_FILE = DATA_DIR / "energy.json"

# Life areas
CATEGORIES = {
    "work": "💼 Work",
    "health": "🏃 Health",
    "personal_brand": "🎯 Personal Brand", 
    "daily_chores": "🏠 Daily Chores",
    "learning": "📚 Learning"
}

# Ensure directories exist
JOURNAL_DIR.mkdir(parents=True, exist_ok=True)

# Setup Gemini
if API_KEY:
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel('gemini-2.0-flash')
else:
    model = None

# --- HELPER FUNCTIONS ---
def get_today():
    return datetime.now().strftime("%Y-%m-%d")

def get_time_of_day():
    hour = datetime.now().hour
    if hour < 12:
        return "morning"
    elif hour < 17:
        return "afternoon"
    else:
        return "evening"

def read_context():
    if not CONTEXT_FILE.exists():
        default = """# About Me

## Working Style
- Deep work best in: [morning/afternoon/evening]
- Energy patterns: [describe]
- Preferred work blocks: [duration]

## Life Areas

### Work
- Role: [your role]
- Current project: [project]
- Key focus: [focus areas]

### Health Goals
- Workout: [goals]
- Diet: [approach]
- Sleep: [target hours]

### Personal Brand
- Platforms: [LinkedIn, blog, etc.]
- Content themes: [topics]
- Posting frequency: [target]

### Notes
- Add anything else the AI should know
"""
        CONTEXT_FILE.write_text(default)
    return CONTEXT_FILE.read_text()

def save_context(content):
    CONTEXT_FILE.write_text(content)

# --- TASK MANAGEMENT ---
def read_tasks():
    if not TASKS_FILE.exists():
        default = {
            "recurring": [],  # Daily tasks that reset
            "tasks": []       # One-time tasks
        }
        TASKS_FILE.write_text(json.dumps(default, indent=2))
        return default
    return json.loads(TASKS_FILE.read_text())

def save_tasks(data):
    TASKS_FILE.write_text(json.dumps(data, indent=2))

def add_task(task_text, category="work", is_recurring=False, priority="medium"):
    data = read_tasks()
    task = {
        "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),  # Unique ID
        "task": task_text,
        "category": category,
        "priority": priority,
        "status": "todo",
        "created": get_today()
    }
    
    if is_recurring:
        task["recurring"] = True
        data["recurring"].append(task)
    else:
        data["tasks"].append(task)
    
    save_tasks(data)
    return task["id"]

def complete_task(task_id, is_recurring=False):
    data = read_tasks()
    task_list = "recurring" if is_recurring else "tasks"
    
    for t in data[task_list]:
        if t["id"] == task_id:
            if is_recurring:
                # For recurring, mark today's completion
                if "completions" not in t:
                    t["completions"] = []
                t["completions"].append(get_today())
            else:
                t["status"] = "done"
                t["completed"] = get_today()
            break
    
    save_tasks(data)

def delete_task(task_id, is_recurring=False):
    data = read_tasks()
    task_list = "recurring" if is_recurring else "tasks"
    data[task_list] = [t for t in data[task_list] if t["id"] != task_id]
    save_tasks(data)

def get_open_tasks():
    data = read_tasks()
    return [t for t in data["tasks"] if t["status"] == "todo"]

def get_recurring_tasks():
    data = read_tasks()
    today = get_today()
    result = []
    for t in data["recurring"]:
        done_today = today in t.get("completions", [])
        result.append({**t, "done_today": done_today})
    return result

# --- ENERGY TRACKING ---
def read_energy():
    if not ENERGY_FILE.exists():
        return {}
    return json.loads(ENERGY_FILE.read_text())

def log_energy(level, note=""):
    data = read_energy()
    today = get_today()
    timestamp = datetime.now().strftime("%H:%M")
    
    if today not in data:
        data[today] = []
    
    data[today].append({
        "time": timestamp,
        "level": level,
        "note": note
    })
    
    ENERGY_FILE.write_text(json.dumps(data, indent=2))

def get_today_energy():
    data = read_energy()
    return data.get(get_today(), [])

def get_latest_energy():
    today_energy = get_today_energy()
    if today_energy:
        return today_energy[-1]
    return None

# --- JOURNAL ---
def get_journal_path(date=None):
    date = date or get_today()
    return JOURNAL_DIR / f"{date}.md"

def read_today_journal():
    path = get_journal_path()
    if path.exists():
        return path.read_text()
    return ""

def append_journal(entry):
    path = get_journal_path()
    timestamp = datetime.now().strftime("%H:%M")
    
    if path.exists():
        content = path.read_text()
    else:
        content = f"# Journal: {get_today()}\n\n"
    
    content += f"**{timestamp}** - {entry}\n\n"
    path.write_text(content)

# --- CHAT ---
def load_chat_history():
    if not CHAT_HISTORY_FILE.exists():
        return []
    data = json.loads(CHAT_HISTORY_FILE.read_text())
    return data.get(get_today(), [])

def save_chat_history(messages):
    today = get_today()
    if CHAT_HISTORY_FILE.exists():
        data = json.loads(CHAT_HISTORY_FILE.read_text())
    else:
        data = {}
    data[today] = messages
    CHAT_HISTORY_FILE.write_text(json.dumps(data, indent=2))

# --- STREAK ---
def get_streak():
    if not STREAK_FILE.exists():
        return {"current": 0, "last_checkin": None, "start_date": get_today()}
    return json.loads(STREAK_FILE.read_text())

def update_streak():
    streak = get_streak()
    today = get_today()
    
    if streak["last_checkin"] == today:
        return streak
    
    if streak["last_checkin"]:
        last = datetime.strptime(streak["last_checkin"], "%Y-%m-%d")
        diff = (datetime.now() - last).days
        
        if diff == 1:
            streak["current"] += 1
        elif diff > 1:
            streak["current"] = 1
    else:
        streak["current"] = 1
    
    streak["last_checkin"] = today
    STREAK_FILE.write_text(json.dumps(streak, indent=2))
    return streak

# --- AI RESPONSE ---
def get_ai_response(user_input):
    if not model:
        return "⚠️ No API key set. Add GEMINI_API_KEY to your .env file."
    
    context = read_context()
    journal = read_today_journal()
    open_tasks = get_open_tasks()
    recurring = get_recurring_tasks()
    energy = get_latest_energy()
    time_of_day = get_time_of_day()
    streak = get_streak()
    
    # Group tasks by category
    tasks_by_cat = {}
    for t in open_tasks:
        cat = t.get("category", "work")
        if cat not in tasks_by_cat:
            tasks_by_cat[cat] = []
        tasks_by_cat[cat].append(t["task"])
    
    system_prompt = f"""You are a thoughtful daily standup assistant. Be conversational, brief, and supportive.

CURRENT TIME: {datetime.now().strftime("%H:%M")} ({time_of_day})
STREAK: Day {streak['current']}
LATEST ENERGY: {energy['level'] if energy else 'Not logged today'} {('- ' + energy['note']) if energy and energy.get('note') else ''}

USER CONTEXT:
{context}

TODAY'S JOURNAL:
{journal if journal else "No entries yet."}

OPEN TASKS BY AREA:
{json.dumps(tasks_by_cat, indent=2) if tasks_by_cat else "No open tasks."}

DAILY HABITS (Recurring):
{', '.join([f"{'✓' if t['done_today'] else '○'} {t['task']}" for t in recurring]) if recurring else "None set up yet."}

USER SAYS: {user_input}

INSTRUCTIONS:
- Respond naturally and briefly (2-3 sentences usually)
- Consider their energy level when suggesting tasks
- In morning: help set intentions based on energy
- In evening: help reflect on the day
- Be encouraging but real
- If energy is low, suggest lighter tasks or breaks
- DO NOT add tasks yourself - the user does that via the UI
- DO NOT output any special tags or commands
- Just have a helpful conversation
"""
    
    response = model.generate_content(system_prompt)
    return response.text

# --- STREAMLIT UI ---
st.set_page_config(page_title="Daily Standup", page_icon="🎯", layout="wide")

streak = update_streak()

# Header
col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    st.title("🎯 Daily Standup")
with col2:
    if streak["current"] <= 21:
        st.metric("Building Habit", f"Day {streak['current']}/21")
    else:
        st.metric("🔥 Streak", f"{streak['current']} days")
with col3:
    latest_energy = get_latest_energy()
    if latest_energy:
        energy_emoji = {"high": "🔋", "medium": "🔋", "low": "🪫"}
        st.metric("Energy", f"{energy_emoji.get(latest_energy['level'], '❓')} {latest_energy['level'].title()}")
    else:
        st.metric("Energy", "Not logged")

# Initialize
if "messages" not in st.session_state:
    st.session_state.messages = load_chat_history()

# --- SIDEBAR ---
with st.sidebar:
    # Energy Check-in
    st.header("🔋 Energy Check")
    energy_cols = st.columns(3)
    with energy_cols[0]:
        if st.button("🔋 High", use_container_width=True):
            log_energy("high")
            append_journal("Energy: High")
            st.rerun()
    with energy_cols[1]:
        if st.button("🔋 Med", use_container_width=True):
            log_energy("medium")
            append_journal("Energy: Medium")
            st.rerun()
    with energy_cols[2]:
        if st.button("🪫 Low", use_container_width=True):
            log_energy("low")
            append_journal("Energy: Low")
            st.rerun()
    
    energy_note = st.text_input("Energy note (optional)", placeholder="Why this energy level?")
    if energy_note and st.button("Log with note"):
        log_energy("medium", energy_note)
        append_journal(f"Energy note: {energy_note}")
        st.rerun()
    
    st.divider()
    
    # Daily Habits (Recurring)
    st.header("📅 Daily Habits")
    recurring = get_recurring_tasks()
    
    if recurring:
        for t in recurring:
            col1, col2 = st.columns([4, 1])
            with col1:
                icon = CATEGORIES.get(t.get("category", "work"), "📌").split()[0]
                status = "✅" if t["done_today"] else "○"
                st.write(f"{status} {icon} {t['task']}")
            with col2:
                if not t["done_today"]:
                    if st.button("✓", key=f"rec_{t['id']}"):
                        complete_task(t["id"], is_recurring=True)
                        append_journal(f"✓ {t['task']}")
                        st.rerun()
    else:
        st.caption("No daily habits yet")
    
    # Add recurring task
    with st.expander("+ Add daily habit"):
        new_habit = st.text_input("Habit", key="new_habit", placeholder="e.g., Morning workout")
        habit_cat = st.selectbox("Category", list(CATEGORIES.keys()), format_func=lambda x: CATEGORIES[x], key="habit_cat")
        if st.button("Add Habit") and new_habit:
            add_task(new_habit, category=habit_cat, is_recurring=True)
            st.rerun()
    
    st.divider()
    
    # Context editor
    with st.expander("⚙️ Edit Context"):
        new_context = st.text_area("Your context", value=read_context(), height=300, label_visibility="collapsed")
        if st.button("Save Context"):
            save_context(new_context)
            st.success("Saved!")

# --- MAIN AREA: Tabs for different views ---
tab_chat, tab_tasks, tab_journal = st.tabs(["💬 Chat", "📋 Tasks", "📝 Journal"])

with tab_chat:
    # Quick actions
    st.write("**Quick check-in:**")
    qcols = st.columns(4)
    with qcols[0]:
        if st.button("🌅 Morning start", use_container_width=True):
            st.session_state.quick_prompt = "Good morning! Let's plan the day."
    with qcols[1]:
        if st.button("🎯 What's next?", use_container_width=True):
            st.session_state.quick_prompt = "Based on my energy and tasks, what should I focus on next?"
    with qcols[2]:
        if st.button("💭 Brain dump", use_container_width=True):
            st.session_state.quick_prompt = "I need to dump some thoughts"
    with qcols[3]:
        if st.button("🌙 Day wrap-up", use_container_width=True):
            st.session_state.quick_prompt = "Let's wrap up the day - what did I accomplish?"
    
    st.divider()
    
    # Chat display
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Handle input
    if "quick_prompt" in st.session_state:
        prompt = st.session_state.quick_prompt
        del st.session_state.quick_prompt
    else:
        prompt = st.chat_input("What's on your mind?")
    
    if prompt:
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with st.spinner("Thinking..."):
            response = get_ai_response(prompt)
        
        with st.chat_message("assistant"):
            st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})
        
        save_chat_history(st.session_state.messages)
        st.rerun()
    
    # Welcome message
    if not st.session_state.messages:
        greetings = {"morning": "Good morning", "afternoon": "Good afternoon", "evening": "Good evening"}
        with st.chat_message("assistant"):
            if streak["current"] == 1:
                st.markdown(f"{greetings[get_time_of_day()]}! 👋 Welcome to your first standup. Start by logging your energy, then let's chat about your day.")
            else:
                st.markdown(f"{greetings[get_time_of_day()]}! Day {streak['current']} - how are you feeling? Log your energy and let's plan.")

with tab_tasks:
    st.subheader("Add New Task")
    
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        new_task = st.text_input("Task", placeholder="What needs to be done?", label_visibility="collapsed")
    with col2:
        task_category = st.selectbox("Category", list(CATEGORIES.keys()), format_func=lambda x: CATEGORIES[x], label_visibility="collapsed")
    with col3:
        if st.button("Add Task", use_container_width=True) and new_task:
            add_task(new_task, category=task_category)
            append_journal(f"Added task: {new_task}")
            st.rerun()
    
    st.divider()
    
    # Display tasks by category
    open_tasks = get_open_tasks()
    
    for cat_key, cat_name in CATEGORIES.items():
        cat_tasks = [t for t in open_tasks if t.get("category") == cat_key]
        if cat_tasks:
            st.subheader(cat_name)
            for t in cat_tasks:
                col1, col2, col3 = st.columns([5, 1, 1])
                with col1:
                    st.write(f"• {t['task']}")
                    st.caption(f"Added: {t['created']}")
                with col2:
                    if st.button("✓", key=f"done_{t['id']}"):
                        complete_task(t["id"])
                        append_journal(f"Completed: {t['task']}")
                        st.rerun()
                with col3:
                    if st.button("🗑", key=f"del_{t['id']}"):
                        delete_task(t["id"])
                        st.rerun()
    
    if not open_tasks:
        st.info("No open tasks. Add one above or chat with your assistant!")
    
    # Show completed today
    data = read_tasks()
    completed_today = [t for t in data["tasks"] if t.get("completed") == get_today()]
    if completed_today:
        with st.expander(f"✅ Completed today ({len(completed_today)})"):
            for t in completed_today:
                st.write(f"~~{t['task']}~~ ({CATEGORIES.get(t.get('category', 'work'), 'Other')})")

with tab_journal:
    st.subheader(f"📝 Journal - {get_today()}")
    
    # Quick journal entry
    quick_entry = st.text_area("Quick thought", placeholder="Capture a thought, insight, or note...", height=100)
    if st.button("Add Entry") and quick_entry:
        append_journal(quick_entry)
        st.rerun()
    
    st.divider()
    
    # Display today's journal
    journal_content = read_today_journal()
    if journal_content:
        st.markdown(journal_content)
    else:
        st.info("No journal entries yet today. Start by logging your energy or adding a thought!")
    
    # Past journals
    st.divider()
    with st.expander("📚 Past Journals"):
        journal_files = sorted(JOURNAL_DIR.glob("*.md"), reverse=True)[:7]
        for jf in journal_files:
            if jf.stem != get_today():
                st.write(f"**{jf.stem}**")
                st.caption(jf.read_text()[:200] + "..." if len(jf.read_text()) > 200 else jf.read_text())