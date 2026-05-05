#!/usr/bin/env python3
"""Daily briefing: Google Calendar + Notion tasks -> Slack."""

import json, os, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta

ANTHROPIC_KEY  = os.environ["ANTHROPIC_API_KEY"]
NOTION_TOKEN   = os.environ.get("NOTION_TOKEN")
NOTION_DB_ID   = "2c5dfa24532581e7922be64559fa22a6"
GOOGLE_ID      = os.environ["GOOGLE_CLIENT_ID"]
GOOGLE_SECRET  = os.environ["GOOGLE_CLIENT_SECRET"]
GOOGLE_REFRESH = os.environ["GOOGLE_REFRESH_TOKEN"]
SLACK_WEBHOOK  = os.environ["SLACK_WEBHOOK"]

CDT = timezone(timedelta(hours=-5))

def now_cdt():
    return datetime.now(CDT)

def http_json(url, method="GET", data=None, headers=None):
    if isinstance(data, dict):
        data = json.dumps(data).encode()
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"HTTP error {method} {url}: {e}")
        return {}

def google_token():
    data = urllib.parse.urlencode({
        "client_id":     GOOGLE_ID,
        "client_secret": GOOGLE_SECRET,
        "refresh_token": GOOGLE_REFRESH,
        "grant_type":    "refresh_token"
    }).encode()
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token", data=data, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read()).get("access_token")
    except Exception as e:
        print(f"Google token error: {e}")
        return None

def get_calendar_events(token):
    now      = now_cdt()
    day_start = now.replace(hour=0,  minute=0,  second=0,  microsecond=0)
    day_end   = now.replace(hour=23, minute=59, second=59, microsecond=0)

    cal_resp = http_json(
        "https://www.googleapis.com/calendar/v3/calendarList",
        headers={"Authorization": f"Bearer {token}"}
    )

    events = []
    for cal in cal_resp.get("items", []):
        if cal.get("accessRole") not in ("owner", "writer", "reader"):
            continue
        cal_id = urllib.parse.quote(cal["id"], safe="")
        params = urllib.parse.urlencode({
            "timeMin":      day_start.isoformat(),
            "timeMax":      day_end.isoformat(),
            "singleEvents": "true",
            "orderBy":      "startTime"
        })
        ev_resp = http_json(
            f"https://www.googleapis.com/calendar/v3/calendars/{cal_id}/events?{params}",
            headers={"Authorization": f"Bearer {token}"}
        )
        for ev in ev_resp.get("items", []):
            start     = ev.get("start", {})
            start_str = start.get("dateTime", start.get("date", ""))
            # Format time for display
            try:
                dt = datetime.fromisoformat(start_str)
                if dt.tzinfo:
                    dt = dt.astimezone(CDT)
                time_label = dt.strftime("%-I:%M %p")
            except Exception:
                time_label = start_str
            events.append({
                "title":    ev.get("summary", "(no title)"),
                "time":     time_label,
                "raw":      start_str,
                "calendar": cal.get("summary", "")
            })

    events.sort(key=lambda e: e["raw"])
    return events

def get_notion_tasks():
    today_str = now_cdt().strftime("%Y-%m-%d")
    payload = {
        "filter": {
            "and": [
                {"property": "Due Date", "date": {"equals": today_str}},
                {"property": "Status",   "status": {"does_not_equal": "Done"}},
                {"property": "Status",   "status": {"does_not_equal": "Not done"}}
            ]
        },
        "page_size": 30
    }
    resp = http_json(
        f"https://api.notion.com/v1/databases/{NOTION_DB_ID}/query",
        method="POST",
        data=payload,
        headers={
            "Authorization":  f"Bearer {NOTION_TOKEN}",
            "Notion-Version": "2022-06-28",
            "Content-Type":   "application/json"
        }
    )
    tasks = []
    for page in resp.get("results", []):
        props    = page.get("properties", {})
        name_raw = props.get("Name", props.get("Task", props.get("title", {})))
        titles   = name_raw.get("title", []) if isinstance(name_raw, dict) else []
        title    = "".join(t.get("plain_text", "") for t in titles).strip()
        status   = props.get("Status", {}).get("status", {}).get("name", "")
        priority = props.get("Priority", {}).get("select", {}).get("name", "")
        if title:
            tasks.append({"title": title, "status": status, "priority": priority})
    return tasks

def call_claude(events, tasks):
    now   = now_cdt()
    today = now.strftime("%A, %B %-d, %Y")

    events_text = "\n".join(
        f"  {e['time']} - {e['title']}" for e in events
    ) or "  No events today"

    tasks_text = "\n".join(
        f"  [{t.get('priority', '')}] {t['title']}" for t in tasks[:15]
    ) or "  No tasks due today"

    prompt = f"""Today is {today}. Write Vikki Baptiste's daily briefing for Slack.

Calendar today (CDT):
{events_text}

Notion tasks due today:
{tasks_text}

Write a concise Slack message with:
1. One-line greeting (direct, not flowery)
2. *Today's calendar* — list events with times, note anything that needs prep or creates time pressure
3. *Top 5 tasks* — numbered, pick the most important from the list, one-line note on why each matters today
4. *Look at the day* — 2-3 sentences on what's realistic given the calendar load

Rules: plain language, contractions, Slack bold (*word*) and italic (_word_), no em dashes, under 400 words, direct not cheerful."""

    resp = http_json(
        "https://api.anthropic.com/v1/messages",
        method="POST",
        data={
            "model":      "claude-haiku-4-5-20251001",
            "max_tokens": 1000,
            "messages":   [{"role": "user", "content": prompt}]
        },
        headers={
            "x-api-key":          ANTHROPIC_KEY,
            "anthropic-version":  "2023-06-01",
            "Content-Type":       "application/json"
        }
    )
    content = resp.get("content", [{}])
    return content[0].get("text", "").strip() if content else ""

def post_slack(text):
    data = json.dumps({"text": text}).encode()
    req  = urllib.request.Request(
        SLACK_WEBHOOK, data=data, method="POST",
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            print(f"Slack: {r.status}")
    except Exception as e:
        print(f"Slack error: {e}")

# ── main ───────────────────────────────────────────────────────────────────
token  = google_token()
events = get_calendar_events(token) if token else []
print(f"Calendar: {len(events)} events")

tasks = get_notion_tasks() if NOTION_TOKEN else []
print(f"Notion: {len(tasks)} tasks (token {'present' if NOTION_TOKEN else 'missing — skipped'})")

briefing = call_claude(events, tasks)
print("Briefing:\n", briefing)

if briefing:
    post_slack(briefing)
    print("Posted to Slack.")
else:
    print("No briefing generated.")
