import xml.etree.ElementTree as ET
import json, os, re, subprocess, urllib.request
from datetime import datetime, date

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

def parse_rss(path, source):
    stories = []
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        channel = root.find("channel") or root
        for item in (channel.findall("item") or [])[:5]:
            title = (item.findtext("title") or "").strip()
            link  = (item.findtext("link")  or "").strip()
            desc  = re.sub(r"<[^>]+>", "", item.findtext("description") or "").strip()[:400]
            if title and link:
                stories.append({"title": title, "link": link, "desc": desc, "source": source})
    except Exception as e:
        print(f"Parse error {source}: {e}")
    return stories

def parse_beehiiv_page(index_path, source):
    """Fetch story titles+descriptions from a Beehiiv publication (no public RSS)."""
    stories = []
    try:
        with open(index_path) as f:
            html = f.read()
        slugs = []
        for slug in re.findall(r'"slug":"([^"]+)"', html):
            if slug not in slugs:
                slugs.append(slug)
            if len(slugs) >= 5:
                break
        for slug in slugs:
            url = f"https://www.superhuman.ai/p/{slug}"
            try:
                req = urllib.request.Request(
                    url, headers={"User-Agent": "Mozilla/5.0 (compatible; MorningEdition/1.0)"}
                )
                with urllib.request.urlopen(req, timeout=10) as r:
                    page = r.read().decode("utf-8", errors="ignore")
                og_title = re.search(r'property="og:title"\s+content="([^"]+)"', page) or \
                           re.search(r'content="([^"]+)"\s+property="og:title"', page)
                og_desc  = re.search(r'property="og:description"\s+content="([^"]{10,}?)"', page) or \
                           re.search(r'content="([^"]{10,300})"\s+property="og:description"', page)
                title = og_title.group(1).strip() if og_title else slug.replace("-", " ").title()
                desc  = og_desc.group(1).strip()[:400] if og_desc else ""
                if title:
                    stories.append({"title": title, "link": url, "desc": desc, "source": source})
            except Exception as e:
                print(f"Superhuman post fetch error {slug}: {e}")
    except Exception as e:
        print(f"Superhuman parse error: {e}")
    return stories

stories = []
stories += parse_rss("/tmp/techcrunch.xml",           "TechCrunch AI")
stories += parse_rss("/tmp/sabrina.xml",               "Sabrina.dev")
stories += parse_rss("/tmp/venturebeat.xml",           "VentureBeat")
stories += parse_rss("/tmp/tldr.xml",                  "TLDR Tech")
stories += parse_beehiiv_page("/tmp/superhuman_index.html", "Superhuman AI")
print(f"Total parsed: {len(stories)}")

now       = datetime.utcnow()
today     = now.strftime("%A, %B %-d, %Y")
delta     = (date(now.year, now.month, now.day) - date(2026, 4, 19)).days + 1
issue_no  = max(1, delta)

if not stories:
    curated = None
else:
    prompt = f"""Today is {today}. Curate a daily morning briefing for Vikki Baptiste.

Vikki: AI consultant for small businesses, Product Owner enterprise search at State Farm (Fortune 50), WordPress/Divi web designer, solo operator, creator of AI Answer Audit, LinkedIn primary marketing channel.

Raw RSS stories:
{json.dumps(stories, indent=2)}

Return ONLY a JSON object with exactly this structure. Use ONLY real stories from the feed. Preserve each story's exact URL.

{{
  "stories": [
    {{
      "headline": "sentence case",
      "url": "exact url from feed",
      "source": "source name",
      "for_you": true or false,
      "body1": "2-3 sentences, snarky-warm, contractions, no em dashes",
      "body2": "2-3 more sentences — why it matters to Vikki specifically"
    }}
  ],
  "stat": {{
    "number": "a striking number or % from any story (just the number itself)",
    "headline": "sentence case headline about what this number means",
    "source": "source name",
    "url": "exact url",
    "body": "2-3 sentences on why this stat matters"
  }}
}}

Include EXACTLY 10 stories. Maximize variety across all available sources — aim for at least 1 story from each source present in the feed. FOR YOU = directly relevant to Vikki's roles above. Sentence case only. No em dashes. Contractions throughout.
Return ONLY the JSON, no other text."""

    resp = subprocess.run([
        "curl", "-s", "-X", "POST",
        "https://api.anthropic.com/v1/messages",
        "-H", "Content-Type: application/json",
        "-H", "anthropic-version: 2023-06-01",
        "-H", f"x-api-key: {ANTHROPIC_API_KEY}",
        "-d", json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 6000,
            "messages": [{"role": "user", "content": prompt}]
        })
    ], capture_output=True, text=True)

    data   = json.loads(resp.stdout)
    raw    = data["content"][0]["text"].strip()
    raw    = re.sub(r"^```json\s*", "", raw)
    raw    = re.sub(r"\s*```$",     "", raw)
    curated = json.loads(raw)
    print(f"Curated {len(curated['stories'])} stories")

# ── helpers ──────────────────────────────────────────────────────────────────

def badge(for_you):
    return '<span class="for-you-badge">For you</span>' if for_you else ""

def stamp(for_you):
    return '<div class="for-you-stamp">For you</div>' if for_you else ""

def meta(source):
    return f'<p class="story-meta">{source}, {today}</p>'

def read_link(url, color="#0066cc", border="#0066cc"):
    style = f"color:{color}; border-bottom-color:{border};"
    return f'<a href="{url}" class="story-link" style="{style}" target="_blank" rel="noopener">Read more</a>'

# ── build spreads ─────────────────────────────────────────────────────────────

if curated:
    ss = curated["stories"]
    st = curated["stat"]
    while len(ss) < 10:
        ss.append(ss[-1])  # pad if fewer than 10

    # TOC
    toc_items = ""
    for i, s in enumerate(ss[:10], 1):
        toc_items += f"""
            <div class="toc-item">
                <span class="toc-number">{i:02d}</span>
                <span class="toc-title-text">{s['headline']}</span>
                {badge(s.get('for_you'))}
            </div>"""

    # SPREAD 1: hero
    s = ss[0]
    spread1 = f"""
    <div class="spread spread-hero">
        <div style="position:absolute;top:40px;right:60px;font-family:'Fraunces',serif;font-size:420px;font-weight:700;color:rgba(0,0,0,0.04);line-height:1;z-index:0;">01</div>
        {stamp(s.get('for_you'))}
        <div class="hero-content">
            <h2 class="hero-headline">{s['headline']}</h2>
            {meta(s['source'])}
            <p class="story-body">{s['body1']}</p>
            <p class="story-body">{s['body2']}</p>
            {read_link(s['url'])}
        </div>
    </div>"""

    # SPREAD 2: terminal
    s = ss[1]
    spread2 = f"""
    <div class="spread spread-terminal">
        <div class="terminal-content">
            <div class="terminal-prompt">>_ 02</div>
            <h2 class="terminal-headline">{s['headline']}</h2>
            <p class="terminal-body">{s['body1']}</p>
            <p class="terminal-body">{s['body2']}</p>
            <p class="terminal-body">{read_link(s['url'], '#00ff41', '#00ff41')}</p>
        </div>
    </div>"""

    # SPREAD 3: rose
    s = ss[2]
    spread3 = f"""
    <div class="spread spread-rose">
        <div class="rose-stamp"><div class="rose-stamp-text">Heads up</div></div>
        <div class="rose-content">
            <h2 class="rose-headline">{s['headline']}</h2>
            {meta(s['source'])}
            <p class="rose-body">{s['body1']}</p>
            <p class="rose-body">{s['body2']}</p>
            {read_link(s['url'])}
        </div>
    </div>"""

    # SPREAD 4: academic drop-cap
    s = ss[3]
    first_word = s['body1'].split()[0] if s['body1'] else "T"
    rest       = s['body1'][len(first_word):]
    spread4 = f"""
    <div class="spread spread-academic">
        <div class="academic-content">
            <h2 class="academic-headline">{s['headline']}</h2>
            {meta(s['source'])}
            <p class="academic-body"><span class="drop-cap">{first_word[0]}</span>{first_word[1:]}{rest}</p>
            <p class="academic-body" style="margin-top:30px;">{s['body2']}</p>
            <p class="academic-body" style="margin-top:30px;">{read_link(s['url'])}</p>
        </div>
    </div>"""

    # SPREAD 5: midnight
    s = ss[4]
    spread5 = f"""
    <div class="spread spread-midnight">
        <div class="midnight-numeral">05</div>
        <div class="midnight-content">
            <h2 class="midnight-headline">{s['headline']}</h2>
            {meta(s['source'])}
            <p class="midnight-body">{s['body1']}</p>
            <p class="midnight-body">{s['body2']}</p>
            <p class="midnight-body">{read_link(s['url'], '#00d4ff', '#00d4ff')}</p>
        </div>
    </div>"""

    # SPREAD 6: split (two stories)
    s1, s2 = ss[5], ss[6]
    spread6 = f"""
    <div class="spread spread-split">
        <div class="split-left">
            <h2 class="split-headline">{s1['headline']}</h2>
            <p class="story-meta" style="color:#999;">{s1['source']}, {today}</p>
            <p class="split-body">{s1['body1']}</p>
            <p class="split-body" style="margin-top:20px;">{read_link(s1['url'], '#00d4ff', '#00d4ff')}</p>
        </div>
        <div class="split-right">
            <div style="position:relative;z-index:1;">
                <h2 class="split-headline">{s2['headline']}</h2>
                <p class="split-body">{s2['body1']}</p>
                {"<p class='split-body' style='margin-top:20px;font-weight:700;font-size:24px;'>For you.</p>" if s2.get('for_you') else ""}
                <p class="split-body" style="margin-top:20px;">{read_link(s2['url'], 'white', 'white')}</p>
            </div>
        </div>
    </div>"""

    # SPREAD 7: poster
    s = ss[7]
    spread7 = f"""
    <div class="spread spread-poster">
        {stamp(s.get('for_you'))}
        <div class="poster-numeral">07</div>
        <div class="poster-content">
            <h2 class="poster-headline">{s['headline']}</h2>
            {meta(s['source'])}
            <p class="poster-body">{s['body1']}</p>
            <p class="poster-body">{s['body2']}</p>
            {read_link(s['url'])}
        </div>
    </div>"""

    # SPREAD 8: kraft
    s = ss[8]
    spread8 = f"""
    <div class="spread spread-kraft">
        <div class="kraft-stamp-circle"><div class="kraft-stamp-text">Pay attention</div></div>
        <div class="kraft-content">
            <h2 class="kraft-headline">{s['headline']}</h2>
            <p class="story-meta" style="color:#8b7355;">{s['source']}, {today}</p>
            <p class="kraft-body">{s['body1']}</p>
            <p class="kraft-body">{s['body2']}</p>
            {read_link(s['url'])}
        </div>
    </div>"""

    # SPREAD 9: editorial two-column
    s = ss[9]
    spread9 = f"""
    <div class="spread spread-editorial">
        <div class="editorial-content">
            <h2 class="editorial-headline">{s['headline']}</h2>
            <p class="story-meta">{s['source']}, {today}</p>
            <div class="editorial-column editorial-first-paragraph">{s['body1']}</div>
            <div class="editorial-column">{s['body2']}</div>
            <p class="story-meta" style="grid-column:1/-1;margin-top:30px;">{read_link(s['url'])}</p>
        </div>
    </div>"""

    # SPREAD 10: bigstat
    spread10 = f"""
    <div class="spread spread-bigstat">
        <div class="bigstat-content">
            <div class="bigstat-numeral">{st['number']}</div>
            <h2 class="bigstat-headline">{st['headline']}</h2>
            <p class="story-meta" style="color:#a7f3d0;margin-bottom:30px;">{st['source']}, {today}</p>
            <p class="bigstat-body">{st['body']}</p>
            <p class="bigstat-body" style="margin-top:30px;">{read_link(st['url'], '#a7f3d0', '#a7f3d0')}</p>
        </div>
    </div>"""

    colophon_sources = """
            <div class="colophon-source"><strong>TechCrunch AI</strong><br><a href="https://techcrunch.com/category/artificial-intelligence/">techcrunch.com/ai</a></div>
            <div class="colophon-source"><strong>Sabrina Ramonov</strong><br><a href="https://www.sabrina.dev/archive">sabrina.dev/archive</a></div>
            <div class="colophon-source"><strong>VentureBeat</strong><br><a href="https://venturebeat.com/category/ai/">venturebeat.com/ai</a></div>
            <div class="colophon-source"><strong>TLDR Tech</strong><br><a href="https://tldr.tech">tldr.tech</a></div>
            <div class="colophon-source"><strong>Superhuman AI</strong><br><a href="https://www.superhuman.ai">superhuman.ai</a></div>"""

else:
    toc_items = '<div class="toc-item">Sources unavailable today.</div>'
    spread1=spread2=spread3=spread4=spread5=spread6=spread7=spread8=spread9=spread10=""
    colophon_sources=""

# ── assemble ──────────────────────────────────────────────────────────────────

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Morning Edition - Vol. 1 / Issue {issue_no} / {today}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@72,400;72,600;72,700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        html, body {{ width: 100%; height: 100%; overflow-x: hidden; }}
        body {{ font-family: 'Inter', sans-serif; background: #faf8f3; scroll-snap-type: y mandatory; scroll-behavior: smooth; }}
        .spread {{ width: 100%; min-height: 100vh; scroll-snap-align: start; scroll-snap-stop: always; display: flex; flex-direction: column; justify-content: center; align-items: center; padding: 60px 40px; position: relative; overflow: hidden; }}
        .cover {{ background: #faf8f3; text-align: center; }}
        .cover-title {{ font-family: 'Fraunces', serif; font-size: 180px; font-weight: 700; color: #1a1a1a; line-height: 0.9; margin-bottom: 20px; letter-spacing: -2px; }}
        .cover-subtitle {{ font-family: 'Inter', sans-serif; font-size: 28px; color: #666; margin-bottom: 80px; font-weight: 500; }}
        .toc {{ width: 100%; max-width: 700px; text-align: left; }}
        .toc-title {{ font-family: 'Fraunces', serif; font-size: 36px; font-weight: 600; color: #1a1a1a; margin-bottom: 40px; }}
        .toc-items {{ display: grid; gap: 20px; }}
        .toc-item {{ font-size: 22px; color: #333; line-height: 1.5; }}
        .toc-number {{ display: inline-block; font-weight: 600; color: #1a1a1a; margin-right: 12px; }}
        .for-you-badge {{ display: inline-block; background: #ff6b35; color: white; font-size: 12px; font-weight: 700; padding: 4px 10px; border-radius: 3px; margin-left: 12px; text-transform: uppercase; letter-spacing: 1px; }}
        .spread-hero {{ background: #faf8f3; position: relative; }}
        .hero-content {{ position: relative; z-index: 1; max-width: 900px; text-align: left; }}
        .hero-headline {{ font-family: 'Fraunces', serif; font-size: 80px; font-weight: 700; color: #1a1a1a; line-height: 1.1; margin-bottom: 30px; }}
        .story-meta {{ font-size: 18px; color: #999; margin-bottom: 30px; font-weight: 500; }}
        .story-body {{ font-size: 22px; line-height: 1.7; color: #333; margin-bottom: 30px; }}
        .story-link {{ display: inline-block; font-size: 20px; color: #0066cc; text-decoration: none; font-weight: 600; border-bottom: 2px solid #0066cc; padding-bottom: 4px; transition: opacity 0.3s; }}
        .story-link:hover {{ opacity: 0.7; }}
        .for-you-stamp {{ position: absolute; top: 100px; left: 40px; background: #ff6b35; color: white; font-size: 14px; font-weight: 700; padding: 12px 20px; border-radius: 4px; transform: rotate(-15deg); z-index: 10; text-transform: uppercase; letter-spacing: 1.5px; box-shadow: 0 4px 12px rgba(255,107,53,0.3); }}
        .spread-terminal {{ background: #0a0a0a; color: #00ff41; font-family: 'JetBrains Mono', monospace; }}
        .terminal-content {{ width: 100%; max-width: 1000px; text-align: left; }}
        .terminal-prompt {{ font-size: 28px; margin-bottom: 30px; letter-spacing: 2px; }}
        .terminal-headline {{ font-family: 'Fraunces', serif; font-size: 70px; font-weight: 700; color: #00ff41; line-height: 1.2; margin-bottom: 40px; text-transform: uppercase; }}
        .terminal-body {{ font-size: 22px; line-height: 1.8; margin-bottom: 30px; color: #00ff41; }}
        .spread-rose {{ background: #ffe4e8; }}
        .rose-stamp {{ position: absolute; top: 80px; left: 60px; width: 200px; height: 200px; border: 4px solid #ff4466; border-radius: 50%; display: flex; align-items: center; justify-content: center; transform: rotate(-25deg); z-index: 5; }}
        .rose-stamp-text {{ font-family: 'Fraunces', serif; font-size: 32px; font-weight: 700; color: #ff4466; text-align: center; text-transform: uppercase; line-height: 1.2; }}
        .rose-content {{ position: relative; z-index: 1; max-width: 900px; margin-left: 200px; }}
        .rose-headline {{ font-family: 'Fraunces', serif; font-size: 70px; font-weight: 700; color: #1a1a1a; line-height: 1.1; margin-bottom: 30px; font-style: italic; }}
        .rose-body {{ font-size: 22px; color: #333; line-height: 1.7; margin-bottom: 30px; }}
        .spread-academic {{ background: #f5f0e8; }}
        .academic-content {{ max-width: 900px; text-align: left; }}
        .academic-headline {{ font-family: 'Fraunces', serif; font-size: 68px; font-weight: 600; color: #1a1a1a; line-height: 1.2; margin-bottom: 40px; font-style: italic; }}
        .academic-body {{ font-size: 22px; line-height: 1.8; color: #333; text-align: justify; }}
        .drop-cap {{ float: left; font-family: 'Fraunces', serif; font-size: 160px; font-weight: 700; line-height: 1; padding-right: 15px; margin-top: -10px; color: #1a1a1a; }}
        .spread-midnight {{ background: radial-gradient(circle at 40% 50%, #1a3a52 0%, #0a1628 100%); position: relative; }}
        .midnight-numeral {{ position: absolute; top: 50%; left: 50%; transform: translate(-50%,-50%); font-family: 'Fraunces', serif; font-size: 500px; font-weight: 700; color: transparent; -webkit-text-stroke: 3px rgba(255,255,255,0.1); line-height: 1; z-index: 0; }}
        .midnight-content {{ position: relative; z-index: 1; max-width: 900px; text-align: left; }}
        .midnight-headline {{ font-family: 'Fraunces', serif; font-size: 70px; font-weight: 700; color: white; line-height: 1.2; margin-bottom: 30px; }}
        .midnight-body {{ font-size: 22px; color: #e0e0e0; line-height: 1.7; margin-bottom: 30px; }}
        .spread-split {{ flex-direction: row; background: #1a1a1a; padding: 0; position: relative; align-items: stretch; }}
        .split-left {{ flex: 1; background: #1a1a1a; padding: 60px; display: flex; flex-direction: column; justify-content: center; }}
        .split-right {{ flex: 1; background: #ff6b35; padding: 60px; display: flex; flex-direction: column; justify-content: center; position: relative; }}
        .split-right::before {{ content: '06'; position: absolute; top: 50%; left: 50%; transform: translate(-50%,-50%); font-family: 'Fraunces', serif; font-size: 450px; font-weight: 700; color: rgba(255,255,255,0.08); line-height: 1; z-index: 0; }}
        .split-headline {{ font-family: 'Fraunces', serif; font-size: 65px; font-weight: 700; line-height: 1.2; margin-bottom: 30px; }}
        .split-left .split-headline {{ color: white; }}
        .split-right .split-headline {{ color: white; position: relative; z-index: 1; }}
        .split-body {{ font-size: 22px; line-height: 1.7; position: relative; z-index: 1; }}
        .split-left .split-body {{ color: #e0e0e0; }}
        .split-right .split-body {{ color: white; }}
        .spread-poster {{ background: #ffd60a; position: relative; }}
        .poster-numeral {{ position: absolute; top: 50%; left: 50%; transform: translate(-50%,-50%); font-family: 'Fraunces', serif; font-size: 480px; font-weight: 700; color: rgba(26,26,26,0.05); line-height: 1; z-index: 0; }}
        .poster-content {{ position: relative; z-index: 1; max-width: 900px; text-align: left; }}
        .poster-headline {{ font-family: 'Fraunces', serif; font-size: 75px; font-weight: 700; color: #1a1a1a; line-height: 1.1; margin-bottom: 30px; }}
        .poster-body {{ font-size: 22px; color: #1a1a1a; line-height: 1.7; margin-bottom: 30px; }}
        .spread-kraft {{ background: linear-gradient(135deg, #c8a87c 0%, #b8985c 100%); }}
        .kraft-stamp-circle {{ position: absolute; top: 100px; right: 80px; width: 220px; height: 220px; border: 5px solid #8b7355; border-radius: 50%; display: flex; align-items: center; justify-content: center; z-index: 5; transform: rotate(20deg); }}
        .kraft-stamp-text {{ font-family: 'Fraunces', serif; font-size: 28px; font-weight: 700; color: #8b7355; text-align: center; text-transform: uppercase; line-height: 1.2; }}
        .kraft-content {{ position: relative; z-index: 1; max-width: 900px; text-align: left; }}
        .kraft-headline {{ font-family: 'Fraunces', serif; font-size: 70px; font-weight: 700; color: #3d2f22; line-height: 1.1; margin-bottom: 30px; }}
        .kraft-body {{ font-size: 22px; color: #2a1f16; line-height: 1.7; margin-bottom: 30px; }}
        .spread-editorial {{ background: #faf8f3; }}
        .editorial-content {{ max-width: 1000px; display: grid; grid-template-columns: 1fr 1fr; gap: 60px; text-align: left; }}
        .editorial-headline {{ grid-column: 1/-1; font-family: 'Fraunces', serif; font-size: 70px; font-weight: 700; color: #1a1a1a; line-height: 1.1; margin-bottom: 40px; }}
        .editorial-column {{ font-size: 22px; line-height: 1.8; color: #333; }}
        .editorial-first-paragraph::first-letter {{ float: left; font-family: 'Fraunces', serif; font-size: 140px; font-weight: 700; color: #dc2626; line-height: 1; padding-right: 10px; margin-top: -10px; }}
        .spread-bigstat {{ background: #064e3b; }}
        .bigstat-content {{ max-width: 900px; text-align: center; display: flex; flex-direction: column; align-items: center; }}
        .bigstat-numeral {{ font-family: 'Fraunces', serif; font-size: 300px; font-weight: 700; color: white; line-height: 0.9; margin-bottom: 20px; }}
        .bigstat-headline {{ font-family: 'Fraunces', serif; font-size: 70px; font-weight: 700; color: white; line-height: 1.2; margin-bottom: 30px; }}
        .bigstat-body {{ font-size: 22px; color: #d1fae5; line-height: 1.7; }}
        .colophon {{ background: #1a1a1a; color: white; padding: 80px 40px; scroll-snap-align: start; }}
        .colophon-title {{ font-family: 'Fraunces', serif; font-size: 60px; font-weight: 700; color: white; margin-bottom: 40px; text-align: center; }}
        .colophon-sources {{ max-width: 700px; margin: 0 auto; }}
        .colophon-source {{ font-size: 22px; line-height: 1.8; margin-bottom: 30px; }}
        .colophon-source a {{ color: #00d4ff; text-decoration: none; border-bottom: 2px solid #00d4ff; }}
        .colophon-credit {{ margin-top: 60px; padding-top: 40px; border-top: 1px solid #444; font-size: 20px; color: #999; text-align: center; font-style: italic; }}
        @media (max-width: 768px) {{
            .spread {{ padding: 40px 30px; }}
            .cover-title {{ font-size: 100px; }}
            .hero-headline, .rose-headline, .academic-headline, .midnight-headline, .poster-headline, .kraft-headline, .editorial-headline, .bigstat-headline {{ font-size: 48px; }}
            .poster-numeral, .midnight-numeral {{ font-size: 200px; }}
            .bigstat-numeral {{ font-size: 160px; }}
            .terminal-headline {{ font-size: 42px; }}
            .story-body, .terminal-body, .rose-body, .academic-body, .midnight-body, .split-body, .poster-body, .kraft-body, .editorial-column, .bigstat-body, .colophon-source {{ font-size: 18px; }}
            .spread-split {{ flex-direction: column; }}
            .split-left, .split-right {{ padding: 40px 30px; flex: none; min-height: 50vh; }}
            .editorial-content {{ grid-template-columns: 1fr; gap: 30px; }}
            .rose-content {{ margin-left: 0; }}
            .rose-stamp {{ position: relative; width: 150px; height: 150px; margin-bottom: 30px; }}
            .kraft-stamp-circle {{ position: relative; top: auto; right: auto; margin-bottom: 30px; }}
        }}
    </style>
</head>
<body>

    <div class="spread cover">
        <h1 class="cover-title">Morning Edition</h1>
        <p class="cover-subtitle">Vol. 1 / Issue {issue_no} / {today}</p>
        <div class="toc">
            <h2 class="toc-title">In this issue</h2>
            <div class="toc-items">{toc_items}</div>
        </div>
    </div>

    {spread1}
    {spread2}
    {spread3}
    {spread4}
    {spread5}
    {spread6}
    {spread7}
    {spread8}
    {spread9}
    {spread10}

    <div class="spread colophon">
        <h2 class="colophon-title">Colophon</h2>
        <div class="colophon-sources">
            {colophon_sources}
            <div class="colophon-credit">
                Curated by Claude for Vikki. Stories sourced {today}.<br><br>
                Typefaces: Fraunces (display), Inter (body), JetBrains Mono (terminal)
            </div>
        </div>
    </div>

</body>
</html>"""

with open("index.html", "w") as f:
    f.write(html)
print("Generated index.html")
