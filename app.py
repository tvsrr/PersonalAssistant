import chainlit as cl
from openai import OpenAI
import os
import json
import re
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path

# --- CONFIGURATION ---
load_dotenv(Path(__file__).parent / ".env")
API_KEY = os.getenv("OPENAI_API_KEY", "")
DATA_DIR = Path(__file__).parent / "data"
JOURNAL_DIR = DATA_DIR / "journal"
CONTEXT_FILE = DATA_DIR / "context.md"
TASKS_FILE = DATA_DIR / "tasks.json"
STREAK_FILE = DATA_DIR / "streak.json"
ENERGY_FILE = DATA_DIR / "energy.json"
WEEKLY_GOALS_FILE = DATA_DIR / "weekly_goals.json"

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

def complete_weekly_goal_by_name(goal_name):
    data = read_weekly_goals()
    goal_lower = goal_name.lower()
    for g in data["goals"]:
        if not g["completed"] and goal_lower in g["goal"].lower():
            g["completed"] = True
            g["completed_date"] = get_today()
            save_weekly_goals(data)
            return g["goal"]
    return None

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

def complete_task_by_name(task_name):
    data = read_tasks()
    task_lower = task_name.lower()
    for t in data["tasks"]:
        if t["status"] == "todo" and task_lower in t["task"].lower():
            t["status"] = "done"
            t["completed"] = get_today()
            save_tasks(data)
            return t["task"]
    # Check recurring
    for t in data["recurring"]:
        if task_lower in t["task"].lower():
            if "completions" not in t:
                t["completions"] = []
            if get_today() not in t["completions"]:
                t["completions"].append(get_today())
                save_tasks(data)
                return t["task"]
    return None

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
    return today_energy[-1] if today_energy else None

# --- JOURNAL ---
def get_journal_path(date=None):
    date = date or get_today()
    return JOURNAL_DIR / f"{date}.md"

def read_today_journal():
    path = get_journal_path()
    return path.read_text() if path.exists() else ""

def append_journal(entry):
    path = get_journal_path()
    timestamp = datetime.now().strftime("%H:%M")
    if path.exists():
        content = path.read_text()
    else:
        content = f"# Journal: {get_today()} ({datetime.now().strftime('%A')})\n\n"
    content += f"**{timestamp}** - {entry}\n\n"
    path.write_text(content)

# --- STREAK ---
def get_streak():
    if not STREAK_FILE.exists():
        return {"current": 0, "longest": 0, "last_checkin": None, "total_days": 0}
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
            log_energy(category, content)
            actions_taken.append(f"🔋 Logged energy: {category}")
        
        elif action_type == "COMPLETE":
            completed = complete_task_by_name(content)
            if completed:
                actions_taken.append(f"✅ Completed: {completed}")
            else:
                # Try completing a goal
                completed_goal = complete_weekly_goal_by_name(content)
                if completed_goal:
                    actions_taken.append(f"✅ Completed goal: {completed_goal}")
        
        elif action_type == "JOURNAL":
            append_journal(f"💡 {content}")
            actions_taken.append(f"📝 Journaled")
    
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
    
    system_prompt = f"""You are a personal standup assistant. Help manage the user's day through natural conversation.

CURRENT: {datetime.now().strftime("%A, %B %d, %Y at %H:%M")} ({time_of_day})
STREAK: Day {streak['current']} | Best: {streak.get('longest', 1)} | Total: {streak.get('total_days', 1)}
ENERGY: {energy['level'] if energy else 'Not logged'} {('- ' + energy.get('note', '')) if energy else ''}

WEEKLY GOALS ({weekly_completed}/{weekly_total}):
{json.dumps([g['goal'] + (' ✓' if g['completed'] else '') for g in weekly_goals.get('goals', [])], indent=2) if weekly_goals.get('goals') else 'None'}

TASKS: {json.dumps(tasks_by_cat, indent=2) if tasks_by_cat else 'None'}

HABITS: {', '.join([f"{'✓' if t['done_today'] else '○'} {t['task']}" for t in recurring]) if recurring else 'None'}

CONTEXT: {context}

---

ACTIONS - Include these tags to take actions:
- [ACTION:TASK:category:description] - Add task
- [ACTION:GOAL:category:description] - Add weekly goal
- [ACTION:HABIT:category:description] - Add daily habit
- [ACTION:ENERGY:level:note] - Log energy (high/medium/low)
- [ACTION:COMPLETE:task:name] - Complete task/habit/goal
- [ACTION:JOURNAL:none:note] - Journal an insight

Categories: work, health, personal_brand, daily_chores, learning

RULES:
- Be brief (2-3 sentences)
- Take actions naturally when user mentions tasks/goals/energy
- Don't over-explain actions
- Be warm and encouraging

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
        raw = response.choices[0].message.content
        return process_ai_actions(raw)
    except Exception as e:
        return f"⚠️ Error: {str(e)}", []

# --- CHAINLIT UI ---

@cl.on_chat_start
async def start():
    """Called when a new chat session starts"""
    streak = update_streak()
    greetings = {"morning": "Good morning", "afternoon": "Good afternoon", "evening": "Good evening"}
    greeting = greetings[get_time_of_day()]
    
    # Get current status
    energy = get_latest_energy()
    open_tasks = get_open_tasks()
    weekly_completed, weekly_total = get_weekly_progress()
    recurring = get_recurring_tasks()
    habits_done = len([h for h in recurring if h["done_today"]])
    habits_total = len(recurring)
    
    # Build status message
    status = f"""### 🎯 Daily Standup - Day {streak['current']} 🔥

| Streak | Energy | Tasks | Goals | Habits |
|--------|--------|-------|-------|--------|
| {streak['current']} days | {energy['level'] if energy else '—'} | {len(open_tasks)} open | {weekly_completed}/{weekly_total} | {habits_done}/{habits_total} |

---

{greeting}! How are you feeling today?"""
    
    await cl.Message(content=status).send()

@cl.on_message
async def main(message: cl.Message):
    """Called when user sends a message"""
    user_input = message.content
    
    # Journal the input
    append_journal(f"💬 {user_input[:100]}{'...' if len(user_input) > 100 else ''}")
    
    # Get AI response
    response, actions = get_ai_response(user_input)
    
    # Build response with actions
    if actions:
        actions_text = "\n".join([f"- {a}" for a in actions])
        full_response = f"{response}\n\n---\n**Actions:**\n{actions_text}"
        # Journal actions
        for action in actions:
            append_journal(action)
    else:
        full_response = response
    
    await cl.Message(content=full_response).send()

@cl.action_callback("show_tasks")
async def show_tasks(action):
    """Show current tasks"""
    tasks = get_open_tasks()
    if tasks:
        msg = "**📋 Open Tasks:**\n"
        for cat, name in CATEGORIES.items():
            cat_tasks = [t for t in tasks if t.get("category") == cat]
            if cat_tasks:
                msg += f"\n{name}\n"
                for t in cat_tasks:
                    msg += f"- {t['task']}\n"
    else:
        msg = "No open tasks! 🎉"
    await cl.Message(content=msg).send()

@cl.action_callback("show_goals")
async def show_goals(action):
    """Show weekly goals"""
    data = read_weekly_goals()
    if data["goals"]:
        msg = f"**🎯 Weekly Goals (Week {data['week']}):**\n"
        for g in data["goals"]:
            status = "✅" if g["completed"] else "⬜"
            cat_icon = CATEGORIES.get(g['category'], '📌').split()[0]
            msg += f"- {status} {cat_icon} {g['goal']}\n"
    else:
        msg = "No weekly goals set. Tell me what you want to achieve!"
    await cl.Message(content=msg).send()

@cl.action_callback("show_journal")
async def show_journal(action):
    """Show today's journal"""
    journal = read_today_journal()
    if journal:
        # Truncate if too long
        if len(journal) > 1500:
            journal = journal[:1500] + "\n\n... (truncated)"
        await cl.Message(content=journal).send()
    else:
        await cl.Message(content="No journal entries yet today.").send()