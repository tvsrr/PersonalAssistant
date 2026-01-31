import streamlit as st
from openai import OpenAI
import os
import json
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pathlib import Path

# --- CONFIGURATION ---
load_dotenv(Path(__file__).parent / ".env")
API_KEY = os.getenv("OPENAI_API_KEY", "")
DATA_DIR = Path(__file__).parent / "data"
JOURNAL_DIR = DATA_DIR / "journal"
CONTEXT_FILE = DATA_DIR / "context.md"
TASKS_FILE = DATA_DIR / "tasks.json"
CHAT_HISTORY_FILE = DATA_DIR / "chat_history.json"
STREAK_FILE = DATA_DIR / "streak.json"
ENERGY_FILE = DATA_DIR / "energy.json"
WEEKLY_GOALS_FILE = DATA_DIR / "weekly_goals.json"

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

# Setup OpenAI
client = OpenAI(api_key=API_KEY) if API_KEY else None

# --- HELPER FUNCTIONS ---
def get_today():
    return datetime.now().strftime("%Y-%m-%d")

def get_week_number():
    return datetime.now().strftime("%Y-W%W")

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
- Role: [your role]
- Current focus: [main project]
- Working style: [preferences]
"""
        CONTEXT_FILE.write_text(default)
    return CONTEXT_FILE.read_text()

def save_context(content):
    CONTEXT_FILE.write_text(content)

# --- WEEKLY GOALS ---
def read_weekly_goals():
    if not WEEKLY_GOALS_FILE.exists():
        default = {"week": get_week_number(), "goals": []}
        WEEKLY_GOALS_FILE.write_text(json.dumps(default, indent=2))
        return default
    data = json.loads(WEEKLY_GOALS_FILE.read_text())
    if data.get("week") != get_week_number():
        if data.get("goals"):
            archive_weekly_goals(data)
        data = {"week": get_week_number(), "goals": []}
        WEEKLY_GOALS_FILE.write_text(json.dumps(data, indent=2))
    return data

def save_weekly_goals(data):
    WEEKLY_GOALS_FILE.write_text(json.dumps(data, indent=2))

def add_weekly_goal(goal_text, category="work"):
    data = read_weekly_goals()
    goal = {
        "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
        "goal": goal_text,
        "category": category,
        "completed": False,
        "created": get_today()
    }
    data["goals"].append(goal)
    save_weekly_goals(data)

def complete_weekly_goal(goal_id):
    data = read_weekly_goals()
    for g in data["goals"]:
        if g["id"] == goal_id:
            g["completed"] = True
            g["completed_date"] = get_today()
    save_weekly_goals(data)

def archive_weekly_goals(data):
    completed = [g for g in data["goals"] if g["completed"]]
    incomplete = [g for g in data["goals"] if not g["completed"]]
    summary = f"## 📅 Week {data['week']} Summary\n\n"
    summary += f"**Completed ({len(completed)}):**\n"
    for g in completed:
        summary += f"- ✅ {g['goal']}\n"
    summary += f"\n**Not completed ({len(incomplete)}):**\n"
    for g in incomplete:
        summary += f"- ❌ {g['goal']}\n"
    append_journal(summary)

def get_weekly_progress():
    data = read_weekly_goals()
    total = len(data["goals"])
    completed = len([g for g in data["goals"] if g["completed"]])
    return completed, total

# --- TASK MANAGEMENT ---
def read_tasks():
    if not TASKS_FILE.exists():
        default = {"recurring": [], "tasks": []}
        TASKS_FILE.write_text(json.dumps(default, indent=2))
        return default
    return json.loads(TASKS_FILE.read_text())

def save_tasks(data):
    TASKS_FILE.write_text(json.dumps(data, indent=2))

def add_task(task_text, category="work", is_recurring=False):
    data = read_tasks()
    task = {
        "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
        "task": task_text,
        "category": category,
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
                if "completions" not in t:
                    t["completions"] = []
                t["completions"].append(get_today())
            else:
                t["status"] = "done"
                t["completed"] = get_today()
            break
    save_tasks(data)

def complete_task_by_name(task_name):
    """Complete a task by matching its name"""
    data = read_tasks()
    task_name_lower = task_name.lower()
    for t in data["tasks"]:
        if t["status"] == "todo" and task_name_lower in t["task"].lower():
            t["status"] = "done"
            t["completed"] = get_today()
            save_tasks(data)
            return t["task"]
    return None

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
    data[today].append({"time": timestamp, "level": level, "note": note})
    ENERGY_FILE.write_text(json.dumps(data, indent=2))

def get_latest_energy():
    data = read_energy()
    today_energy = data.get(get_today(), [])
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
        content = f"# Journal: {get_today()} ({datetime.now().strftime('%A')})\n\n"
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

def clear_chat_history():
    if CHAT_HISTORY_FILE.exists():
        data = json.loads(CHAT_HISTORY_FILE.read_text())
        today = get_today()
        if today in data:
            del data[today]
        CHAT_HISTORY_FILE.write_text(json.dumps(data, indent=2))

# --- STREAK ---
def get_streak():
    if not STREAK_FILE.exists():
        return {"current": 0, "longest": 0, "last_checkin": None, "start_date": get_today(), "total_days": 0}
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
            streak["total_days"] += 1
            if streak["current"] > streak.get("longest", 0):
                streak["longest"] = streak["current"]
        elif diff > 1:
            streak["current"] = 1
            streak["total_days"] += 1
    else:
        streak["current"] = 1
        streak["total_days"] = 1
    streak["last_checkin"] = today
    STREAK_FILE.write_text(json.dumps(streak, indent=2))
    return streak

# --- AI WITH ACTIONS ---
def process_ai_actions(response_text):
    """Parse AI response for action tags and execute them"""
    actions_taken = []
    
    # Pattern: [ACTION:TYPE:CATEGORY:CONTENT]
    # Examples:
    # [ACTION:TASK:work:Finish chassis validation report]
    # [ACTION:GOAL:health:Exercise 3 times this week]
    # [ACTION:ENERGY:low:Feeling tired after meetings]
    # [ACTION:HABIT:health:Morning meditation]
    # [ACTION:COMPLETE:task:chassis validation]
    # [ACTION:JOURNAL:none:Important insight about project direction]
    
    action_pattern = r'\[ACTION:(\w+):(\w+):([^\]]+)\]'
    matches = re.findall(action_pattern, response_text)
    
    for action_type, category, content in matches:
        action_type = action_type.upper()
        category = category.lower()
        content = content.strip()
        
        if action_type == "TASK":
            add_task(content, category=category)
            actions_taken.append(f"📋 Added task: {content}")
        
        elif action_type == "GOAL":
            add_weekly_goal(content, category=category)
            actions_taken.append(f"🎯 Added weekly goal: {content}")
        
        elif action_type == "HABIT":
            add_task(content, category=category, is_recurring=True)
            actions_taken.append(f"📅 Added daily habit: {content}")
        
        elif action_type == "ENERGY":
            log_energy(category, content)  # category is the level here
            actions_taken.append(f"🔋 Logged energy: {category}")
        
        elif action_type == "COMPLETE":
            completed = complete_task_by_name(content)
            if completed:
                actions_taken.append(f"✅ Completed: {completed}")
        
        elif action_type == "JOURNAL":
            append_journal(f"💡 {content}")
            actions_taken.append(f"📝 Journaled insight")
    
    # Clean action tags from response
    clean_response = re.sub(action_pattern, '', response_text).strip()
    
    return clean_response, actions_taken

def get_ai_response(user_input):
    if not client:
        return "⚠️ No API key set. Add OPENAI_API_KEY to your .env file.", []
    
    context = read_context()
    journal = read_today_journal()
    open_tasks = get_open_tasks()
    recurring = get_recurring_tasks()
    energy = get_latest_energy()
    time_of_day = get_time_of_day()
    streak = get_streak()
    weekly_goals = read_weekly_goals()
    weekly_completed, weekly_total = get_weekly_progress()
    
    tasks_by_cat = {}
    for t in open_tasks:
        cat = t.get("category", "work")
        if cat not in tasks_by_cat:
            tasks_by_cat[cat] = []
        tasks_by_cat[cat].append(t["task"])
    
    system_prompt = f"""You are a personal standup assistant. You help manage the user's day through conversation.

CURRENT DATE/TIME: {datetime.now().strftime("%A, %B %d, %Y at %H:%M")} ({time_of_day})
STREAK: Day {streak['current']} (Longest: {streak.get('longest', 1)}, Total: {streak.get('total_days', 1)})
LATEST ENERGY: {energy['level'] if energy else 'Not logged'} {('- ' + energy.get('note', '')) if energy else ''}

WEEKLY GOALS ({weekly_completed}/{weekly_total}):
{json.dumps([g['goal'] + (' ✓' if g['completed'] else '') for g in weekly_goals.get('goals', [])], indent=2) if weekly_goals.get('goals') else 'None set'}

OPEN TASKS:
{json.dumps(tasks_by_cat, indent=2) if tasks_by_cat else 'None'}

DAILY HABITS:
{', '.join([f"{'✓' if t['done_today'] else '○'} {t['task']}" for t in recurring]) if recurring else 'None set'}

USER CONTEXT:
{context}

---

YOU CAN TAKE ACTIONS by including special tags in your response. The system will automatically execute them.

AVAILABLE ACTIONS (include these tags anywhere in your response):
- [ACTION:TASK:category:task description] - Add a new task
- [ACTION:GOAL:category:goal description] - Add a weekly goal  
- [ACTION:HABIT:category:habit description] - Add a daily habit
- [ACTION:ENERGY:level:note] - Log energy (level: high/medium/low)
- [ACTION:COMPLETE:task:task name] - Mark a task as complete
- [ACTION:JOURNAL:none:insight or note] - Add a journal entry

Categories: work, health, personal_brand, daily_chores, learning

EXAMPLES:
User: "I need to finish the report by Friday"
You: "Got it, I've added that to your work tasks. [ACTION:TASK:work:Finish the report by Friday] What's blocking you from starting?"

User: "Feeling exhausted today"
You: "I hear you. [ACTION:ENERGY:low:Feeling exhausted] On low energy days, maybe focus on smaller tasks. Want me to suggest something light from your list?"

User: "Done with the chassis validation!"
You: "Nice work! 🎉 [ACTION:COMPLETE:task:chassis validation] That's a big one off your plate. What's next?"

User: "My goal this week is to post on LinkedIn twice"  
You: "Great goal for building your personal brand! [ACTION:GOAL:personal_brand:Post on LinkedIn twice this week] Want to brainstorm content ideas?"

---

INSTRUCTIONS:
- Be conversational and brief (2-3 sentences + action if needed)
- Proactively add tasks/goals when user mentions them
- Log energy when user describes how they feel
- Complete tasks when user says they finished something
- Be encouraging but real
- Don't over-explain the actions - just do them naturally
- You can take multiple actions in one response if needed

USER: {user_input}"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ],
            max_tokens=400
        )
        raw_response = response.choices[0].message.content
        clean_response, actions = process_ai_actions(raw_response)
        return clean_response, actions
    except Exception as e:
        return f"⚠️ Error: {str(e)}", []

def generate_day_summary():
    if not client:
        return "No API key set."
    journal = read_today_journal()
    if not journal:
        return "No journal entries to summarize."
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Summarize this day's journal into 3-4 bullet points. Be concise and warm."},
                {"role": "user", "content": journal}
            ],
            max_tokens=250
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error: {str(e)}"

# --- STREAMLIT UI ---
st.set_page_config(page_title="Daily Standup", page_icon="🎯", layout="wide")

streak = update_streak()

# Initialize
if "messages" not in st.session_state:
    st.session_state.messages = load_chat_history()

# --- HEADER ---
col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
with col1:
    st.title("🎯 Daily Standup")
with col2:
    st.metric("🔥 Streak", f"{streak['current']} days")
with col3:
    energy = get_latest_energy()
    if energy:
        emoji = {"high": "🔋", "medium": "🔋", "low": "🪫"}.get(energy['level'], '❓')
        st.metric("Energy", f"{emoji} {energy['level'].title()}")
    else:
        st.metric("Energy", "Not logged")
with col4:
    completed, total = get_weekly_progress()
    open_tasks = len(get_open_tasks())
    st.metric("Tasks", f"{open_tasks} open")

# --- MAIN LAYOUT ---
tab_chat, tab_overview = st.tabs(["💬 Chat", "📊 Overview"])

with tab_chat:
    # Chat container
    chat_container = st.container()
    
    with chat_container:
        # Display chat history
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                if message.get("actions"):
                    with st.expander("Actions taken", expanded=False):
                        for action in message["actions"]:
                            st.caption(action)
        
        # Welcome message
        if not st.session_state.messages:
            with st.chat_message("assistant"):
                greetings = {"morning": "Good morning", "afternoon": "Good afternoon", "evening": "Good evening"}
                if streak["current"] == 1:
                    st.markdown(f"{greetings[get_time_of_day()]}! 👋 I'm your standup assistant. Just talk to me naturally - I'll help organize your tasks, track your energy, and keep you on track. What's on your mind?")
                else:
                    st.markdown(f"{greetings[get_time_of_day()]}! Day {streak['current']} 🔥 How are you feeling today?")
    
    # Chat input
    if prompt := st.chat_input("Talk to me... (I'll manage your tasks, goals, and energy)"):
        # Show user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Get AI response
        with st.spinner(""):
            response, actions = get_ai_response(prompt)
        
        # Show assistant message
        with st.chat_message("assistant"):
            st.markdown(response)
            if actions:
                with st.expander("Actions taken", expanded=True):
                    for action in actions:
                        st.caption(action)
        
        # Save to history
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.messages.append({"role": "assistant", "content": response, "actions": actions})
        
        # Auto-journal
        append_journal(f"💬 {prompt[:80]}{'...' if len(prompt) > 80 else ''}")
        if actions:
            for action in actions:
                append_journal(action)
        
        save_chat_history(st.session_state.messages)
        st.rerun()
    
    # Quick actions at bottom
    st.divider()
    cols = st.columns(5)
    with cols[0]:
        if st.button("🌅 Morning", use_container_width=True):
            st.session_state.auto_prompt = "Good morning! Let's plan my day."
            st.rerun()
    with cols[1]:
        if st.button("🎯 Next?", use_container_width=True):
            st.session_state.auto_prompt = "What should I focus on next?"
            st.rerun()
    with cols[2]:
        if st.button("💭 Dump", use_container_width=True):
            st.session_state.auto_prompt = "I need to brain dump some thoughts..."
            st.rerun()
    with cols[3]:
        if st.button("🌙 Wrap up", use_container_width=True):
            st.session_state.auto_prompt = "Let's wrap up the day."
            st.rerun()
    with cols[4]:
        if st.button("🗑️ Clear", use_container_width=True):
            clear_chat_history()
            st.session_state.messages = []
            st.rerun()
    
    # Handle auto prompts
    if "auto_prompt" in st.session_state:
        prompt = st.session_state.auto_prompt
        del st.session_state.auto_prompt
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.spinner(""):
            response, actions = get_ai_response(prompt)
        
        with st.chat_message("assistant"):
            st.markdown(response)
            if actions:
                with st.expander("Actions taken", expanded=True):
                    for action in actions:
                        st.caption(action)
        
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.messages.append({"role": "assistant", "content": response, "actions": actions})
        append_journal(f"💬 {prompt}")
        if actions:
            for action in actions:
                append_journal(action)
        save_chat_history(st.session_state.messages)

with tab_overview:
    # Stats
    st.subheader(f"📊 {datetime.now().strftime('%A, %B %d, %Y')}")
    
    stat_cols = st.columns(4)
    with stat_cols[0]:
        st.metric("🔥 Streak", f"{streak['current']} days", f"Best: {streak.get('longest', 1)}")
    with stat_cols[1]:
        st.metric("📅 Total Days", streak.get('total_days', 1))
    with stat_cols[2]:
        completed, total = get_weekly_progress()
        st.metric("🎯 Weekly Goals", f"{completed}/{total}" if total > 0 else "None")
    with stat_cols[3]:
        st.metric("📋 Open Tasks", len(get_open_tasks()))
    
    st.divider()
    
    # Two columns
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🎯 Weekly Goals")
        weekly_data = read_weekly_goals()
        if weekly_data["goals"]:
            for g in weekly_data["goals"]:
                status = "✅" if g["completed"] else "⬜"
                cat_icon = CATEGORIES.get(g['category'], '📌').split()[0]
                col_a, col_b = st.columns([6, 1])
                with col_a:
                    st.write(f"{status} {cat_icon} {g['goal']}")
                with col_b:
                    if not g["completed"]:
                        if st.button("✓", key=f"g_{g['id']}"):
                            complete_weekly_goal(g["id"])
                            append_journal(f"✅ Completed goal: {g['goal']}")
                            st.rerun()
        else:
            st.caption("No goals yet. Tell me your goals in chat!")
        
        st.divider()
        
        st.subheader("📅 Daily Habits")
        recurring = get_recurring_tasks()
        if recurring:
            for t in recurring:
                status = "✅" if t["done_today"] else "⬜"
                cat_icon = CATEGORIES.get(t['category'], '📌').split()[0]
                col_a, col_b = st.columns([6, 1])
                with col_a:
                    st.write(f"{status} {cat_icon} {t['task']}")
                with col_b:
                    if not t["done_today"]:
                        if st.button("✓", key=f"h_{t['id']}"):
                            complete_task(t["id"], is_recurring=True)
                            append_journal(f"✅ Habit: {t['task']}")
                            st.rerun()
        else:
            st.caption("No habits yet. Tell me what habits you want to build!")
    
    with col2:
        st.subheader("📋 Open Tasks")
        open_tasks = get_open_tasks()
        if open_tasks:
            for cat_key, cat_name in CATEGORIES.items():
                cat_tasks = [t for t in open_tasks if t.get("category") == cat_key]
                if cat_tasks:
                    st.write(f"**{cat_name}**")
                    for t in cat_tasks:
                        col_a, col_b = st.columns([6, 1])
                        with col_a:
                            st.write(f"• {t['task']}")
                        with col_b:
                            if st.button("✓", key=f"t_{t['id']}"):
                                complete_task(t["id"])
                                append_journal(f"✅ Task: {t['task']}")
                                st.rerun()
        else:
            st.caption("No tasks. Tell me what you need to do!")
        
        st.divider()
        
        st.subheader("📝 Today's Journal")
        journal = read_today_journal()
        if journal:
            st.markdown(journal[:600] + "..." if len(journal) > 600 else journal)
            if st.button("📊 Generate Summary"):
                summary = generate_day_summary()
                append_journal(f"## 📊 Summary\n{summary}")
                st.rerun()
        else:
            st.caption("Journal will fill as you chat...")
    
    # Settings at bottom
    st.divider()
    with st.expander("⚙️ Settings"):
        new_context = st.text_area("About you (AI context)", value=read_context(), height=150)
        if st.button("Save"):
            save_context(new_context)
            st.success("Saved!")
