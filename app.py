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
BACKLOG_FILE = DATA_DIR / "backlog.json"
CHAT_HISTORY_FILE = DATA_DIR / "chat_history.json"
STREAK_FILE = DATA_DIR / "streak.json"

# Ensure directories exist
JOURNAL_DIR.mkdir(parents=True, exist_ok=True)

# Setup Gemini
if API_KEY:
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
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
- Working style: [fill in]
- Current focus: [fill in]
- Energy patterns: [fill in]

# Goals This Week
- [ ] Goal 1
- [ ] Goal 2
"""
        CONTEXT_FILE.write_text(default)
    return CONTEXT_FILE.read_text()

def save_context(content):
    CONTEXT_FILE.write_text(content)

def read_backlog():
    if not BACKLOG_FILE.exists():
        BACKLOG_FILE.write_text("[]")
        return []
    return json.loads(BACKLOG_FILE.read_text())

def save_backlog(tasks):
    BACKLOG_FILE.write_text(json.dumps(tasks, indent=2))

def add_task(task_text, priority="medium"):
    tasks = read_backlog()
    tasks.append({
        "id": len(tasks) + 1,
        "task": task_text,
        "priority": priority,
        "status": "todo",
        "created": get_today()
    })
    save_backlog(tasks)

def complete_task(task_id):
    tasks = read_backlog()
    for t in tasks:
        if t["id"] == task_id:
            t["status"] = "done"
            t["completed"] = get_today()
    save_backlog(tasks)

def get_journal_path(date=None):
    date = date or get_today()
    return JOURNAL_DIR / f"{date}.md"

def read_today_journal():
    path = get_journal_path()
    if path.exists():
        return path.read_text()
    return ""

def append_journal(entry):
    """Append-only journaling - never overwrites"""
    path = get_journal_path()
    timestamp = datetime.now().strftime("%H:%M")
    
    if path.exists():
        content = path.read_text()
    else:
        content = f"# Journal: {get_today()}\n\n"
    
    content += f"**{timestamp}** - {entry}\n\n"
    path.write_text(content)

def load_chat_history():
    if not CHAT_HISTORY_FILE.exists():
        return []
    data = json.loads(CHAT_HISTORY_FILE.read_text())
    # Only load today's chat
    today = get_today()
    return data.get(today, [])

def save_chat_history(messages):
    today = get_today()
    if CHAT_HISTORY_FILE.exists():
        data = json.loads(CHAT_HISTORY_FILE.read_text())
    else:
        data = {}
    data[today] = messages
    CHAT_HISTORY_FILE.write_text(json.dumps(data, indent=2))

def get_streak():
    if not STREAK_FILE.exists():
        return {"current": 0, "last_checkin": None, "start_date": get_today()}
    return json.loads(STREAK_FILE.read_text())

def update_streak():
    streak = get_streak()
    today = get_today()
    
    if streak["last_checkin"] == today:
        return streak  # Already checked in today
    
    if streak["last_checkin"]:
        last = datetime.strptime(streak["last_checkin"], "%Y-%m-%d")
        diff = (datetime.now() - last).days
        
        if diff == 1:
            streak["current"] += 1
        elif diff > 1:
            streak["current"] = 1  # Reset streak
    else:
        streak["current"] = 1
    
    streak["last_checkin"] = today
    STREAK_FILE.write_text(json.dumps(streak, indent=2))
    return streak

def get_ai_response(user_input):
    """Get AI response with full context"""
    if not model:
        return "⚠️ No API key set. Add GEMINI_API_KEY to your .env file."
    
    context = read_context()
    journal = read_today_journal()
    tasks = read_backlog()
    open_tasks = [t for t in tasks if t["status"] == "todo"]
    time_of_day = get_time_of_day()
    streak = get_streak()
    
    system_prompt = f"""You are a thoughtful daily standup assistant. Be conversational, brief, and supportive.

CURRENT TIME: {datetime.now().strftime("%H:%M")} ({time_of_day})
STREAK: Day {streak['current']}

USER CONTEXT:
{context}

TODAY'S JOURNAL SO FAR:
{journal if journal else "No entries yet today."}

OPEN TASKS ({len(open_tasks)}):
{json.dumps(open_tasks, indent=2) if open_tasks else "No open tasks."}

USER SAYS: {user_input}

INSTRUCTIONS:
- Respond naturally and briefly (2-3 sentences usually enough)
- If they mention a new task, confirm you'll add it
- If they complete something, acknowledge it warmly
- In morning: help them set intentions
- In evening: help them reflect
- Track energy/mood mentions
- Be encouraging but not cheesy

If the user wants to ADD a task, include exactly: [ADD_TASK: task description]
If the user COMPLETES a task, include exactly: [COMPLETE_TASK: task_id]
If something important should be journaled, include exactly: [JOURNAL: the insight or update]
"""
    
    response = model.generate_content(system_prompt)
    return response.text

def process_ai_actions(response_text):
    """Parse and execute any actions from AI response"""
    import re
    
    # Add tasks
    task_matches = re.findall(r'\[ADD_TASK:\s*(.+?)\]', response_text)
    for task in task_matches:
        add_task(task.strip())
    
    # Complete tasks
    complete_matches = re.findall(r'\[COMPLETE_TASK:\s*(\d+)\]', response_text)
    for task_id in complete_matches:
        complete_task(int(task_id))
    
    # Journal entries
    journal_matches = re.findall(r'\[JOURNAL:\s*(.+?)\]', response_text)
    for entry in journal_matches:
        append_journal(entry.strip())
    
    # Clean response for display
    clean = response_text
    clean = re.sub(r'\[ADD_TASK:\s*.+?\]', '', clean)
    clean = re.sub(r'\[COMPLETE_TASK:\s*\d+\]', '', clean)
    clean = re.sub(r'\[JOURNAL:\s*.+?\]', '', clean)
    return clean.strip()

# --- STREAMLIT UI ---
st.set_page_config(page_title="Daily Standup", page_icon="🎯", layout="wide")

# Update streak on load
streak = update_streak()

# Header with streak
col1, col2 = st.columns([3, 1])
with col1:
    st.title("🎯 Daily Standup")
with col2:
    if streak["current"] <= 21:
        st.metric("Building Habit", f"Day {streak['current']}/21", delta=None)
    else:
        st.metric("🔥 Streak", f"{streak['current']} days")

# Initialize chat history from file
if "messages" not in st.session_state:
    st.session_state.messages = load_chat_history()

# --- SIDEBAR ---
with st.sidebar:
    st.header("📋 Open Tasks")
    tasks = read_backlog()
    open_tasks = [t for t in tasks if t["status"] == "todo"]
    
    if open_tasks:
        for t in open_tasks:
            col1, col2 = st.columns([4, 1])
            with col1:
                st.write(f"**{t['id']}**. {t['task']}")
            with col2:
                if st.button("✓", key=f"done_{t['id']}"):
                    complete_task(t["id"])
                    append_journal(f"Completed: {t['task']}")
                    st.rerun()
    else:
        st.write("No open tasks. Nice! 🎉")
    
    st.divider()
    
    # Quick add task
    st.subheader("Quick Add")
    quick_task = st.text_input("New task", label_visibility="collapsed", placeholder="Add a task...")
    if quick_task:
        add_task(quick_task)
        st.rerun()
    
    st.divider()
    
    # Today's journal preview
    st.subheader("📝 Today's Journal")
    journal = read_today_journal()
    if journal:
        st.text_area("Journal", value=journal, height=200, disabled=True, label_visibility="collapsed")
    else:
        st.write("No entries yet.")
    
    st.divider()
    
    # Context editor (collapsed by default)
    with st.expander("⚙️ Edit Context"):
        new_context = st.text_area("Your context", value=read_context(), height=200, label_visibility="collapsed")
        if st.button("Save Context"):
            save_context(new_context)
            st.success("Saved!")

# --- MAIN CHAT ---
# Quick capture buttons
st.write("**Quick capture:**")
col1, col2, col3, col4 = st.columns(4)
with col1:
    if st.button("🔋 Energy check"):
        st.session_state.quick_prompt = "How's my energy right now?"
with col2:
    if st.button("🎯 What's next?"):
        st.session_state.quick_prompt = "What should I focus on next?"
with col3:
    if st.button("💭 Quick thought"):
        st.session_state.quick_prompt = "I want to capture a quick thought"
with col4:
    if st.button("🌙 Wrap up"):
        st.session_state.quick_prompt = "Let's wrap up the day"

st.divider()

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Handle quick prompts
if "quick_prompt" in st.session_state:
    prompt = st.session_state.quick_prompt
    del st.session_state.quick_prompt
else:
    prompt = st.chat_input("What's on your mind?")

if prompt:
    # Show user message
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Get and process AI response
    with st.spinner("Thinking..."):
        raw_response = get_ai_response(prompt)
        display_text = process_ai_actions(raw_response)
    
    # Show AI message
    with st.chat_message("assistant"):
        st.markdown(display_text)
    st.session_state.messages.append({"role": "assistant", "content": display_text})
    
    # Persist chat history
    save_chat_history(st.session_state.messages)
    
    # Rerun to update sidebar if tasks changed
    st.rerun()

# First-time welcome
if not st.session_state.messages:
    time_greeting = {"morning": "Good morning", "afternoon": "Good afternoon", "evening": "Good evening"}
    greeting = time_greeting[get_time_of_day()]
    
    with st.chat_message("assistant"):
        if streak["current"] == 1:
            st.markdown(f"{greeting}! 👋 Welcome to your first standup. What's on your mind today?")
        else:
            st.markdown(f"{greeting}! Day {streak['current']} - what are we working on?")
