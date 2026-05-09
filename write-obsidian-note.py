#!/usr/bin/env python3
"""
write-obsidian-note.py
Called by GitHub Actions after daily-briefing.py runs.
Reads the briefing text from /tmp/briefing.txt and writes a daily note
to daily/YYYY-MM-DD.md in the repo (which is then committed and pushed).
The local LaunchAgent syncs this file to VikkiVault/daily/ at 7:15am.
"""

import os, sys
from datetime import datetime, timezone, timedelta

CDT = timezone(timedelta(hours=-5))

def main():
    briefing_file = "/tmp/briefing.txt"
    if not os.path.exists(briefing_file):
        print("No briefing file found at /tmp/briefing.txt — skipping Obsidian note")
        sys.exit(0)

    with open(briefing_file, "r") as f:
        briefing_text = f.read().strip()

    if not briefing_text:
        print("Briefing file is empty — skipping")
        sys.exit(0)

    now   = datetime.now(CDT)
    today = now.strftime("%Y-%m-%d")
    day   = now.strftime("%A, %B %-d, %Y")

    note = f"""---
date: {today}
source: morning-edition
generated: {now.strftime("%Y-%m-%dT%H:%M:%S%z")}
tags: [daily-note, briefing]
---

# Daily briefing — {day}

{briefing_text}
"""

    os.makedirs("daily", exist_ok=True)
    outpath = f"daily/{today}.md"
    with open(outpath, "w") as f:
        f.write(note)

    print(f"Written: {outpath}")

if __name__ == "__main__":
    main()
