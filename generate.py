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
stories += parse_rss("/tmp/rundown.xml", "The Rundown AI")
stories += parse_rss("/tmp/sabrina.xml", "Sabrina.dev")
stories += parse_rss("/tmp/carnage.xml", "Daily Carnage")
print(f"Total stories parsed: {len(stories)}")

now = datetime.utcnow()
today_long = now.strftime("%A, %B %-d, %Y")
today_short = now.strftime("%Y-%m-%d")

# Build issue number from days since launch (Apr 19 2026 = Issue 1)
from datetime import date
delta = (date(now.year, now.month, now.day) - date(2026, 4, 19)).days + 1
issue_no = max(1, delta)

if not stories:
    curated = None
else:
    prompt = f"""Today is {today_long}. You're curating a daily newspaper-style morning briefing for Vikki Baptiste.

Raw RSS stories:
{json.dumps(stories, indent=2)}

Vikki is: AI consultant for tech-resistant small businesses, Product Owner for enterprise search at State Farm (Fortune 50), WordPress/Divi web designer, solo operator who builds automations and vibecoded apps, creator of AI Answer Audit, uses Claude daily, LinkedIn as primary marketing channel.

Structure the best stories into this EXACT JSON format. Select real stories from the feed only — do NOT fabricate.

{{
  "lead": {{
    "source": "source name",
    "for_you": true or false,
    "headline": "sentence case headline",
    "pull_quote": "a punchy 1-sentence pull quote from the summary",
    "body1": "first paragraph, 2-3 sentences, snarky-warm, plain language, contractions",
    "body2": "second paragraph, 2-3 sentences continuing the thought"
  }},
  "secondary": {{
    "source": "source name",
    "for_you": true or false,
    "headline": "sentence case headline",
    "body": "2-3 sentences, snarky-warm, plain language, contractions"
  }},
  "stat": {{
    "source": "source name",
    "number": "a striking number or percentage from one of the stories (just the number/% itself)",
    "label": "what the number means, 1-2 short lines",
    "context": "1-2 sentences of why it matters"
  }},
  "col1": [
    {{"source": "...", "for_you": true/false, "headline": "...", "body": "2-3 sentences"}},
    {{"source": "...", "for_you": true/false, "headline": "...", "body": "2-3 sentences"}},
    {{"source": "...", "for_you": true/false, "headline": "...", "body": "2-3 sentences"}}
  ],
  "col2": [
    {{"source": "...", "for_you": true/false, "headline": "...", "body": "2-3 sentences"}},
    {{"source": "...", "for_you": true/false, "headline": "...", "body": "2-3 sentences"}},
    {{"source": "...", "for_you": true/false, "headline": "...", "body": "2-3 sentences"}}
  ],
  "col3": [
    {{"source": "...", "for_you": true/false, "headline": "...", "body": "2-3 sentences"}},
    {{"source": "...", "for_you": true/false, "headline": "...", "body": "2-3 sentences"}}
  ]
}}

Rules: sentence case only, no em dashes (use commas or semicolons), contractions throughout, never say "but here's the part nobody talks about". FOR YOU = directly relevant to Vikki's specific roles above. Return ONLY the JSON object, no other text."""

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
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    curated = json.loads(raw)
    print("Curation complete")

def for_you_badge(flag):
    return '<span class="for-you">For you</span>' if flag else ""

def source_tag(source, for_you=False):
    return f'<div class="source-tag">{source} {for_you_badge(for_you)}</div>'

if curated:
    lead = curated["lead"]
    sec  = curated["secondary"]
    stat = curated["stat"]

    lead_html = f"""
      <article class="lead-story">
        {source_tag(lead['source'], lead.get('for_you'))}
        <h2 class="hed-xl">{lead['headline']}</h2>
        <p class="pull-quote">&ldquo;{lead['pull_quote']}&rdquo;</p>
        <p class="body">{lead['body1']}</p>
        <p class="body">{lead['body2']}</p>
      </article>"""

    sec_html = f"""
        <article class="secondary-story">
          {source_tag(sec['source'], sec.get('for_you'))}
          <h2 class="hed-l">{sec['headline']}</h2>
          <p class="body">{sec['body']}</p>
        </article>"""

    stat_html = f"""
        <div class="stat-block">
          {source_tag(stat['source'])}
          <div class="stat-number">{stat['number']}</div>
          <div class="stat-label">{stat['label']}</div>
          <p class="stat-context">{stat['context']}</p>
        </div>"""

    def col_html(stories):
        out = ""
        for s in stories:
            out += f"""
        <article class="story-item">
          {source_tag(s['source'], s.get('for_you'))}
          <h3 class="hed-m">{s['headline']}</h3>
          <p class="body">{s['body']}</p>
        </article>"""
        return out

    col1_html = col_html(curated.get("col1", []))
    col2_html = col_html(curated.get("col2", []))
    col3_html = col_html(curated.get("col3", []))
else:
    lead_html = '<article class="lead-story"><p class="body">Sources unavailable today. Check back tomorrow.</p></article>'
    sec_html = stat_html = col1_html = col2_html = col3_html = ""

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Morning Edition &mdash; {today_long}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Abril+Fatface&family=Playfair+Display:ital,wght@0,400;0,700;0,900;1,400;1,700&family=Lora:ital,wght@0,400;0,500;1,400&family=Courier+Prime:ital,wght@0,400;0,700;1,400&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    :root {{
      --bg: #0c0b09; --bg-lift: #131210; --text: #ede7d5; --text-muted: #7a7064;
      --text-dim: #3a352e; --gold: #c8963e; --gold-bright: #e0ad55;
      --gold-dim: rgba(200,150,62,0.12); --rule: #221f1a; --rule-gold: rgba(200,150,62,0.28);
    }}
    html {{ scroll-behavior: smooth; }}
    body {{ background: var(--bg); color: var(--text); font-family: 'Lora', Georgia, serif; min-height: 100vh; position: relative; overflow-x: hidden; }}
    body::after {{ content: ''; position: fixed; inset: 0; background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E"); opacity: 0.04; pointer-events: none; z-index: 9999; mix-blend-mode: overlay; }}
    .wrap {{ max-width: 1180px; margin: 0 auto; padding: 0 36px; }}
    @keyframes fadeUp {{ from {{ opacity: 0; transform: translateY(14px); }} to {{ opacity: 1; transform: translateY(0); }} }}
    @keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
    @keyframes ruleGrow {{ from {{ transform: scaleX(0); transform-origin: left; }} to {{ transform: scaleX(1); transform-origin: left; }} }}
    .rule-thin {{ border: none; border-top: 1px solid var(--rule); margin: 14px 0; }}
    .rule-gold {{ border: none; border-top: 1px solid var(--rule-gold); margin: 16px 0; }}
    .rule-double {{ border: none; height: 6px; position: relative; margin: 18px 0; }}
    .rule-double::before, .rule-double::after {{ content: ''; position: absolute; left: 0; right: 0; height: 1px; background: var(--rule-gold); animation: ruleGrow 1.4s cubic-bezier(0.22,1,0.36,1) 0.3s both; }}
    .rule-double::before {{ top: 0; }} .rule-double::after {{ bottom: 0; }}
    .masthead {{ padding-top: 36px; text-align: center; animation: fadeUp 0.9s cubic-bezier(0.22,1,0.36,1) both; }}
    .sources-line {{ font-family: 'Courier Prime', monospace; font-size: 0.62rem; letter-spacing: 0.28em; text-transform: uppercase; color: var(--text-muted); margin-bottom: 14px; }}
    .masthead-title {{ font-family: 'Abril Fatface', serif; font-size: clamp(58px,9.5vw,122px); line-height: 0.93; color: var(--text); letter-spacing: -0.015em; animation: fadeUp 1.1s cubic-bezier(0.22,1,0.36,1) 0.1s both; }}
    .masthead-meta {{ display: flex; justify-content: space-between; align-items: center; margin: 18px 0 14px; }}
    .masthead-meta span {{ font-family: 'Courier Prime', monospace; font-size: 0.68rem; letter-spacing: 0.14em; text-transform: uppercase; color: var(--text-muted); }}
    .masthead-tagline {{ font-family: 'Lora', serif; font-style: italic; font-size: 0.95rem; color: var(--text-muted); margin: 14px 0 28px; letter-spacing: 0.01em; }}
    .source-tag {{ font-family: 'Courier Prime', monospace; font-size: 0.6rem; letter-spacing: 0.22em; text-transform: uppercase; color: var(--gold); margin-bottom: 11px; display: flex; align-items: center; gap: 9px; }}
    .source-tag::before {{ content: ''; display: block; width: 22px; height: 1px; background: var(--gold); flex-shrink: 0; }}
    .for-you {{ display: inline-block; font-family: 'Courier Prime', monospace; font-size: 0.52rem; letter-spacing: 0.14em; text-transform: uppercase; color: var(--bg); background: var(--gold); padding: 2px 6px 1px; border-radius: 2px; box-shadow: 0 0 10px rgba(200,150,62,0.35); }}
    .hed-xl {{ font-family: 'Playfair Display', serif; font-size: clamp(26px,3.2vw,42px); font-weight: 700; line-height: 1.14; color: var(--text); margin-bottom: 16px; transition: color 0.2s ease; }}
    .hed-l {{ font-family: 'Playfair Display', serif; font-size: clamp(19px,2.2vw,26px); font-weight: 700; line-height: 1.2; color: var(--text); margin-bottom: 12px; transition: color 0.2s ease; }}
    .hed-m {{ font-family: 'Playfair Display', serif; font-size: clamp(16px,1.5vw,19px); font-weight: 700; line-height: 1.28; color: var(--text); margin-bottom: 10px; transition: color 0.2s ease; }}
    article:hover .hed-xl, article:hover .hed-l, article:hover .hed-m {{ color: var(--gold-bright); }}
    .body {{ font-family: 'Lora', serif; font-size: 0.875rem; line-height: 1.78; color: rgba(237,231,213,0.7); }}
    .body + .body {{ margin-top: 10px; }}
    .pull-quote {{ font-family: 'Playfair Display', serif; font-style: italic; font-size: 1.05rem; line-height: 1.55; color: var(--gold-bright); border-left: 2px solid var(--gold); padding-left: 18px; margin: 18px 0; }}
    .lead-section {{ display: grid; grid-template-columns: 1.45fr 1fr; gap: 0; animation: fadeUp 1.3s cubic-bezier(0.22,1,0.36,1) 0.15s both; }}
    .lead-story {{ padding: 30px 36px 30px 0; border-right: 1px solid var(--rule); cursor: default; }}
    .lead-right {{ display: flex; flex-direction: column; }}
    .secondary-story {{ padding: 30px 0 30px 36px; border-bottom: 1px solid var(--rule); flex: 1; cursor: default; }}
    .stat-block {{ padding: 26px 0 26px 36px; }}
    .stat-number {{ font-family: 'Abril Fatface', serif; font-size: clamp(64px,7vw,92px); line-height: 1; color: var(--gold); margin: 6px 0 8px; }}
    .stat-label {{ font-family: 'Courier Prime', monospace; font-size: 0.66rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--text-muted); line-height: 1.7; }}
    .stat-context {{ font-family: 'Lora', serif; font-style: italic; font-size: 0.8rem; color: var(--text-muted); margin-top: 14px; line-height: 1.7; }}
    .stories-section {{ display: grid; grid-template-columns: 1fr 1fr 1fr; border-top: 1px solid var(--rule); }}
    .col {{ padding: 28px 32px 28px 0; border-right: 1px solid var(--rule); }}
    .col:nth-child(2) {{ padding: 28px 32px 28px 32px; }}
    .col:last-child {{ padding: 28px 0 28px 32px; border-right: none; }}
    .story-item {{ padding-bottom: 22px; margin-bottom: 22px; border-bottom: 1px solid var(--rule); cursor: default; }}
    .story-item:last-child {{ border-bottom: none; margin-bottom: 0; padding-bottom: 0; }}
    .col:nth-child(1) .story-item:nth-child(1) {{ animation: fadeUp 0.7s ease 0.25s both; }}
    .col:nth-child(1) .story-item:nth-child(2) {{ animation: fadeUp 0.7s ease 0.38s both; }}
    .col:nth-child(1) .story-item:nth-child(3) {{ animation: fadeUp 0.7s ease 0.51s both; }}
    .col:nth-child(2) .story-item:nth-child(1) {{ animation: fadeUp 0.7s ease 0.32s both; }}
    .col:nth-child(2) .story-item:nth-child(2) {{ animation: fadeUp 0.7s ease 0.45s both; }}
    .col:nth-child(2) .story-item:nth-child(3) {{ animation: fadeUp 0.7s ease 0.58s both; }}
    .col:nth-child(3) .story-item:nth-child(1) {{ animation: fadeUp 0.7s ease 0.39s both; }}
    .col:nth-child(3) .story-item:nth-child(2) {{ animation: fadeUp 0.7s ease 0.52s both; }}
    .colophon {{ border-top: 1px solid var(--rule-gold); padding: 30px 0 52px; display: grid; grid-template-columns: 1fr auto 1fr; gap: 36px; align-items: start; animation: fadeIn 2s ease 0.5s both; }}
    .colophon-text {{ font-family: 'Courier Prime', monospace; font-size: 0.63rem; letter-spacing: 0.1em; color: var(--text-muted); line-height: 1.9; }}
    .colophon-center {{ text-align: center; }}
    .colophon-name {{ font-family: 'Abril Fatface', serif; font-size: 22px; color: var(--text); display: block; margin-bottom: 5px; }}
    .colophon-byline {{ font-family: 'Courier Prime', monospace; font-size: 0.6rem; letter-spacing: 0.2em; text-transform: uppercase; color: var(--gold); }}
    .colophon-right {{ text-align: right; }}
    @media (max-width: 920px) {{
      .lead-section {{ grid-template-columns: 1fr; }}
      .lead-story {{ border-right: none; border-bottom: 1px solid var(--rule); padding: 24px 0; }}
      .secondary-story {{ padding: 24px 0; }} .stat-block {{ padding: 24px 0; }}
      .stories-section {{ grid-template-columns: 1fr; }}
      .col, .col:nth-child(2), .col:last-child {{ padding: 24px 0; border-right: none; border-bottom: 1px solid var(--rule); }}
      .col:last-child {{ border-bottom: none; }}
      .colophon {{ grid-template-columns: 1fr; }} .colophon-right {{ text-align: left; }}
    }}
    @media (max-width: 580px) {{ .wrap {{ padding: 0 20px; }} .masthead-title {{ font-size: 50px; }} .colophon {{ padding-bottom: 36px; }} }}
  </style>
</head>
<body>
  <div class="wrap">
    <header class="masthead">
      <p class="sources-line">The Rundown AI &nbsp;&middot;&nbsp; Sabrina.dev &nbsp;&middot;&nbsp; Daily Carnage</p>
      <hr class="rule-thin">
      <h1 class="masthead-title">Morning Edition</h1>
      <div class="masthead-meta">
        <span>Vol. I &nbsp;&middot;&nbsp; {today_long}</span>
        <span>Issue No. {issue_no}</span>
      </div>
      <div class="rule-double"></div>
      <p class="masthead-tagline">Your daily AI briefing, curated for the business owner who doesn't have time for noise.</p>
      <hr class="rule-gold">
    </header>

    <section class="lead-section">
      {lead_html}
      <div class="lead-right">
        {sec_html}
        {stat_html}
      </div>
    </section>

    <section class="stories-section">
      <div class="col">{col1_html}</div>
      <div class="col">{col2_html}</div>
      <div class="col">{col3_html}</div>
    </section>

    <footer>
      <div class="rule-double" style="margin-top: 0;"></div>
      <div class="colophon">
        <div class="colophon-text">
          Morning Edition is curated daily<br>
          from The Rundown AI, Sabrina.dev,<br>
          and Daily Carnage.<br><br>
          Stories selected for business owners<br>
          who use AI to do real work.
        </div>
        <div class="colophon-center">
          <span class="colophon-name">Morning Edition</span>
          <span class="colophon-byline">Curated by AI Auntie &nbsp;&middot;&nbsp; vikki@vikkibaptiste.com</span>
        </div>
        <div class="colophon-text colophon-right">
          Published {today_long}<br>
          Bloomington-Normal, Illinois<br><br>
          3 Bees Digital<br>
          3bees.digital
        </div>
      </div>
    </footer>
  </div>
</body>
</html>"""

with open("index.html", "w") as f:
    f.write(html)
print(f"Generated index.html")
