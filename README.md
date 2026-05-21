# Slack Poll App
![Live poll example](docs/screenshot.png)

An interactive poll bot for Slack with click-to-vote buttons, live tallies, multi-select, anonymous voting, and auto-expiry. Built with [Bolt for Python](https://slack.dev/bolt-python/) and Flask. Exposes an HTTP API so AI agents can create polls programmatically.

## ✨ Features

- 📊 **Click-to-vote buttons** — no emoji-reaction counting
- 🔁 **Live tallies** — message updates in place as votes come in
- ☑️ **Multi-select** — `--multi` allows voters to pick multiple options
- 🕶️ **Anonymous mode** — `--anon` hides who voted for what
- ⏰ **Auto-expiry** — `--expires=30m` closes the poll automatically
- 🔒 **Creator-only close** — only the poll creator can close early
- 🤖 **HTTP API** — `POST /api/polls` for programmatic creation (AI agents, automations)

## 🏗️ Architecture

```text
User in Slack ───────/poll command────▶ ┐
User clicks button ──interactivity───▶  ├─▶ Bolt app ─┬─▶ poll_store (SQLite)
AI agent ──POST /api/polls──────────▶  ┘             └─▶ chat.postMessage / chat.update
                                                          (live tally refresh)

Background scheduler ─every 30s─▶ closes expired polls + refreshes their messages
```

## 📂 Project layout

```
slack-poll-app/
├── app.py              # Bolt app + Flask wiring + HTTP API
├── poll_store.py       # SQLAlchemy models + vote logic
├── blocks.py           # Block Kit renderer
├── expiry.py           # Background scheduler for auto-closing
├── requirements.txt
├── .env.example
├── Dockerfile
├── Procfile
├── fly.toml            # Fly.io deploy config
├── manifest.yaml       # Slack app manifest
├── composio_tool.yaml  # Composio custom tool definition
└── tests/              # pytest suite (no Slack needed)
```

## 🚀 Quick start

### 1. Clone and install

```bash
git clone <your-repo> slack-poll-app
cd slack-poll-app

python -m venv venv
source venv/bin/activate           # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Run the tests (no Slack required)

```bash
pytest -v
```

You should see ~15 passing tests. If any fail, fix before continuing.

### 3. Create the Slack app

1. Go to https://api.slack.com/apps → **Create New App** → **From a manifest**
2. Pick a workspace (a personal dev workspace is recommended for testing)
3. Paste the contents of `manifest.yaml`
4. **Install to Workspace** → copy the **Bot User OAuth Token** (`xoxb-...`) and **Signing Secret**

### 4. Configure environment

```bash
cp .env.example .env
# Edit .env with your real tokens
```

Required values:
- `SLACK_BOT_TOKEN` — from step 3
- `SLACK_SIGNING_SECRET` — from step 3
- `POLL_API_TOKEN` — any long random string (`openssl rand -hex 32`)

### 5. Run locally + expose via ngrok

```bash
# Terminal 1
python app.py

# Terminal 2
ngrok http 3000
```

Copy the `https://abc123.ngrok-free.app` URL from ngrok and **update both** in your Slack app config:
- **Slash Commands** → `/poll` → Request URL = `https://abc123.ngrok-free.app/slack/events`
- **Interactivity & Shortcuts** → Request URL = `https://abc123.ngrok-free.app/slack/events`

### 6. Test in Slack

In your test workspace:

```text
/invite @PollBot
/poll "Lunch?" "🍜 Ramen" "🥢 Pho"
```

Click a Vote button — the tally should update live.

## 🎛️ Slash command usage

```text
/poll "Question?" "Option 1" "Option 2" [Option 3 …] [flags]
```

| Flag | Effect |
|---|---|
| `--multi` | Allow voters to pick multiple options |
| `--anon` | Hide who voted; disables "View voters" button |
| `--expires=30m` | Auto-close after duration (`m`/`h`/`d`) |

### Examples

```text
/poll "Lunch?" "🍜 Ramen" "🥢 Pho"
/poll "Sprint themes?" "Speed" "Quality" "Scope" --multi
/poll "Friday off?" "Yes" "No" --anon
/poll "Roadmap" "AI" "Perf" "DX" "Security" --multi --anon --expires=3d
```

## 🤖 HTTP API

### `POST /api/polls`

**Headers**
```
Authorization: Bearer <POLL_API_TOKEN>
Content-Type: application/json
```

**Body**
```json
{
  "channel": "C0B1JC9DFN2",
  "question": "Which noodle?",
  "options": ["🍜 Ramen", "🥢 Pho"],
  "anonymous": false,
  "multi_choice": false,
  "expires_in": "1h",
  "creator_user_id": "U09QPJSSXED"
}
```

**Response**
```json
{
  "poll_id": "a1b2c3d4",
  "channel": "C0B1JC9DFN2",
  "message_ts": "1779218554.755159",
  "expires_at": "2026-05-20T15:35:00+00:00"
}
```

**curl example**
```bash
curl -X POST https://your-domain.fly.dev/api/polls \
  -H "Authorization: Bearer $POLL_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "general",
    "question": "Which noodle?",
    "options": ["🍜 Ramen", "🥢 Pho"],
    "expires_in": "1h"
  }'
```

## 🚢 Deploy to Fly.io

```bash
# One-time setup
brew install flyctl              # macOS; see fly.io/docs for other OS
fly auth login
fly launch --no-deploy --copy-config
fly volumes create polls_data --region dfw --size 1

# Set secrets
fly secrets set \
  SLACK_BOT_TOKEN=xoxb-... \
  SLACK_SIGNING_SECRET=... \
  POLL_API_TOKEN=$(openssl rand -hex 32)

# Deploy
fly deploy

# Get the URL
fly status
```

Update Slack app URLs to point at `https://your-app.fly.dev/slack/events`.

**Watch logs:**
```bash
fly logs
```

## 🧠 Plug into an AI agent (Composio)

1. In Composio dashboard → **Custom Tools** → **Import YAML**
2. Upload `composio_tool.yaml`
3. Set connection env vars:
   - `SLACK_POLL_BASE_URL=https://your-app.fly.dev`
   - `SLACK_POLL_API_TOKEN=<same token as fly secret>`
4. The tool `slack_create_poll` is now callable by any agent in your Composio account

## 🧪 Testing reference

| Level | Command | Slack needed? |
|---|---|---|
| Unit + API | `pytest -v` | No |
| Local API smoke | `curl http://localhost:3000/healthz` | No |
| Slash command | `/poll "Q?" "A" "B"` in Slack | Yes (ngrok or deployed) |
| HTTP API live | `curl POST /api/polls` against deployed URL | Yes |
| Agent integration | Ask your AI to "start a poll" | Yes |

## 🛠️ Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| `dispatch_failed` in Slack | Local app crashed or ngrok URL changed | Check Flask logs; update Slack URLs |
| Buttons don't respond | Interactivity URL not set | Slack app → Interactivity & Shortcuts |
| `invalid_auth` from Slack | Wrong bot token | Re-copy `xoxb-...` from OAuth page |
| `401 unauthorized` from API | Wrong `POLL_API_TOKEN` | Match the `Authorization: Bearer` header |
| Bot can't post in channel | Bot not invited | `/invite @PollBot` in that channel |
| Poll doesn't auto-close | Scheduler disabled | Confirm `RUN_SCHEDULER=1` in env |

## 📈 Extending

Easy adds:
- 📊 **Results SVG chart** when a poll closes
- 🔔 **DM the creator** when poll closes
- 📥 **CSV export** of votes
- 👥 **Slack workflow trigger** when a poll closes with X+ votes
- 🌐 **Postgres** instead of SQLite (change `DATABASE_URL`)

## 📜 License

MIT — do whatever you want.