# 🎯 Daily Standup Assistant

A simple, habit-forming personal standup tool that runs locally on your Mac.

## Quick Setup (5 minutes)

### 1. Get your Gemini API key
- Go to https://aistudio.google.com/app/apikey
- Create a new API key (free tier is plenty)

### 2. Setup the project

```bash
# Navigate to where you downloaded this
cd ~/standup

# Create your .env file
cp .env.example .env

# Edit .env and add your API key
nano .env   # or open with any editor

# Install dependencies
pip3 install -r requirements.txt
```

### 3. Run it

```bash
streamlit run app.py
```

Opens in your browser at http://localhost:8501

## Daily Use

### Make it easy to launch

Add this to your `~/.zshrc`:

```bash
alias standup="cd ~/standup && streamlit run app.py"
```

Then just type `standup` in Terminal.

### The 21-Day Habit

The app tracks your streak. Aim for 21 days to build the habit.
- Morning: Set intentions, review tasks
- During day: Quick captures via buttons
- Evening: Wrap up, reflect

## What gets saved

```
data/
├── context.md          # Your stable info (edit via sidebar)
├── backlog.json        # Your tasks
├── journal/
│   └── 2025-01-29.md   # Daily entries (one file per day)
├── chat_history.json   # Conversation history
└── streak.json         # Your streak data
```

Journal files are **append-only** - nothing ever gets deleted or overwritten.

## Next Steps (Later)

Once you're using this daily, we can add:
- [ ] Slack integration for office access
- [ ] Weekly/monthly reviews
- [ ] Data visualization
- [ ] Cloud sync

But first: **just use it for a week**.
