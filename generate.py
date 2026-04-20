import xml.etree.ElementTree as ET
import json, os, re, subprocess
from datetime import datetime

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

def parse_rss(path, source):
    stories = []
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        channel = root.find("channel") or root
        for item in (channel.findall("item") or [])[:10]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            desc = re.sub(r"<[^>]+>", "", item.findtext("description") or "").strip()[:400]
            if title and link:
                stories.append({"title": title, "link": link, "desc": desc, "source": source})
    except Exception as e:
        print(f"Parse error {source}: {e}")
    return stories

stories = []
stories += parse_rss("/tmp/rundown.xml", "The Rundown")
stories += parse_rss("/tmp/sabrina.xml", "Sabrina.dev")
stories += parse_rss("/tmp/carnage.xml", "Daily Carnage")

print(f"Total stories parsed: {len(stories)}")

today = datetime.utcnow().strftime("%A, %B %-d, %Y")

if not stories:
    html_content = "<p>Sources unavailable today. Check back tomorrow.</p>"
    items_html = html_content
else:
    prompt = f"""Today is {today}. You are curating a daily morning briefing for Vikki Baptiste.

Here are up to {len(stories)} raw stories from RSS feeds:
{json.dumps(stories, indent=2)}

Select the 8-10 most interesting stories. Vikki's taste:
- AI tools, Claude, agents, MCP, Anthropic updates (always relevant)
- Creative software (Canva), dev tools, privacy
- Anything immediately actionable for a solo operator
- Weird science, strong ideas

FOR EACH STORY, write:
- Headline in sentence case
- Source name
- URL
- 2-3 sentence summary: snarky-warm, plain language, contractions. Add "FOR YOU:" note if directly relevant to Vikki as AI consultant, enterprise search PO at State Farm, WordPress/Divi web designer, or maker of AI Answer Audit.

Return a JSON array like:
[
  {{
    "headline": "...",
    "source": "...",
    "url": "...",
    "summary": "...",
    "for_you": "..." or null
  }}
]

Rules: no em dashes, sentence case, contractions, never say "but here's the part nobody talks about". Return ONLY the JSON array, no other text."""

    response = subprocess.run([
        "curl", "-s", "-X", "POST",
        "https://api.anthropic.com/v1/messages",
        "-H", "Content-Type: application/json",
        "-H", "anthropic-version: 2023-06-01",
        "-H", f"x-api-key: {ANTHROPIC_API_KEY}",
        "-d", json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}]
        })
    ], capture_output=True, text=True)

    data = json.loads(response.stdout)
    raw = data["content"][0]["text"].strip()
    # Strip markdown code fences if present
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    curated = json.loads(raw)

    items_html = ""
    for i, story in enumerate(curated, 1):
        for_you_html = f'<div class="for-you">FOR YOU: {story["for_you"]}</div>' if story.get("for_you") else ""
        items_html += f"""
    <article>
      <div class="story-number">{i:02d}</div>
      <div class="story-content">
        <h2><a href="{story['url']}" target="_blank">{story['headline']}</a></h2>
        <div class="source">{story['source']}</div>
        <p>{story['summary']}</p>
        {for_you_html}
      </div>
    </article>"""

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Morning Edition -- {today}</title>
<style>
  :root {{
    --ink: #1a1a2e;
    --paper: #faf9f6;
    --accent: #c8a96e;
    --muted: #6b6b7b;
    --rule: #e2ddd5;
    --for-you: #f0ede4;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Georgia', serif;
    background: var(--paper);
    color: var(--ink);
    max-width: 780px;
    margin: 0 auto;
    padding: 2rem 1.5rem 4rem;
    line-height: 1.7;
  }}
  header {{
    border-top: 3px solid var(--ink);
    border-bottom: 1px solid var(--ink);
    padding: 1.2rem 0 1rem;
    margin-bottom: 2.5rem;
    display: flex;
    justify-content: space-between;
    align-items: baseline;
  }}
  header h1 {{
    font-size: 2rem;
    font-weight: 700;
    letter-spacing: -0.02em;
  }}
  header .dateline {{
    font-size: 0.85rem;
    color: var(--muted);
    font-style: italic;
  }}
  article {{
    display: grid;
    grid-template-columns: 2.5rem 1fr;
    gap: 1rem;
    padding: 1.5rem 0;
    border-bottom: 1px solid var(--rule);
  }}
  .story-number {{
    font-size: 0.75rem;
    color: var(--accent);
    font-weight: 700;
    letter-spacing: 0.05em;
    padding-top: 0.3rem;
    font-family: monospace;
  }}
  h2 {{
    font-size: 1.15rem;
    font-weight: 700;
    line-height: 1.3;
    margin-bottom: 0.3rem;
  }}
  h2 a {{
    color: var(--ink);
    text-decoration: none;
  }}
  h2 a:hover {{
    text-decoration: underline;
    text-underline-offset: 3px;
  }}
  .source {{
    font-size: 0.75rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.6rem;
  }}
  p {{
    font-size: 0.95rem;
    color: #2d2d3a;
  }}
  .for-you {{
    margin-top: 0.6rem;
    padding: 0.5rem 0.75rem;
    background: var(--for-you);
    border-left: 3px solid var(--accent);
    font-size: 0.85rem;
    color: var(--muted);
    font-style: italic;
  }}
  footer {{
    margin-top: 3rem;
    padding-top: 1rem;
    border-top: 1px solid var(--rule);
    font-size: 0.8rem;
    color: var(--muted);
    display: flex;
    justify-content: space-between;
  }}
</style>
</head>
<body>
<header>
  <h1>Morning Edition</h1>
  <span class="dateline">{today}</span>
</header>
{items_html}
<footer>
  <span>Sources: The Rundown &middot; Sabrina.dev &middot; Daily Carnage</span>
  <span>Curated by Claude for Vikki</span>
</footer>
</body>
</html>"""

with open("index.html", "w") as f:
    f.write(html)

print(f"Generated index.html with {len(curated) if stories else 0} stories")
