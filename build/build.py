#!/usr/bin/env python3
"""Build the static site from data/ into site/. Standard library only.

  python3 build/build.py && npx -y pagefind@1.3.0 --site site
"""
import hashlib, html, json, os, re, shutil
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA, SITE, STATIC = (os.path.join(ROOT, d) for d in ("data", "site", "build/static"))
SITE_NAME = "Irvington Schools Public Records Archive"

SOURCE_LABEL = {"boarddocs": "BoardDocs", "website": "District website", "wayback": "Internet Archive",
                "pac": "PTSA PAC minutes", "video": "Board meeting video"}
TYPE_LABEL = {"agenda item": "Agenda item", "attachment": "Attachment", "minutes attachment": "Attachment",
              "minutes": "Minutes", "meeting": "Meeting agenda", "policy": "Policy",
              "meeting video": "Meeting transcript"}
TS = re.compile(r"^\[(\d\d):(\d\d):(\d\d)\]\s?(.*)$", re.S)
e = html.escape


def slug(i):
    s = re.sub(r"[^A-Za-z0-9._/-]+", "_", i)
    if s != i:
        s += "-" + hashlib.sha1(i.encode()).hexdigest()[:6]
    return s.lower()  # case-insensitive filesystems & case-insensitive Pages URLs


def page(title, body, depth, extra_head=""):
    up = "../" * depth
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)} · {SITE_NAME}</title>
<link rel="stylesheet" href="{up}static/site.css">{extra_head}</head><body>
<header class="top"><a class="brand" href="{up}index.html">{SITE_NAME}</a>
<nav><a href="{up}index.html">Search</a><a href="{up}meetings.html">Meetings</a><a href="{up}about.html">About</a></nav></header>
<main>{body}</main>
<footer>Unofficial, volunteer-run archive of public records. Not affiliated with the Irvington UFSD. <a href="{up}about.html">About &amp; corrections</a></footer>
</body></html>"""


def write(rel, text):
    p = os.path.join(SITE, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write(text)


def read_text(rel):
    with open(os.path.join(DATA, "text", rel), encoding="utf-8", errors="replace") as f:
        lines = f.read().split("\n")
    head = lines[0] if lines else ""
    body = lines[1:] if (head.startswith("# SOURCE") or " | http" in head) else lines
    return body


def paras(lines):
    out, buf = [], []
    for l in lines + [""]:
        if l.strip():
            buf.append(l.strip())
        elif buf:
            out.append(" ".join(buf) if len(buf) > 1 and all(len(b) > 60 for b in buf[:-1]) else "\n".join(buf))
            buf = []
    return out


def meta_block(r):
    year = r["date"][:4]
    src, typ = SOURCE_LABEL[r["coll"]], TYPE_LABEL.get(r["kind"], "Web page" if r["coll"] in ("website", "wayback") else "Document")
    if r["coll"] in ("website", "wayback") and re.search(r"\.(pdf|docx?|pptx?|xlsx?)(\.txt)?$", r["text"], re.I):
        typ = "Document"
    links = [f'<a href="{e(r["url"])}" rel="noopener">View original</a>']
    if r["archive_url"]:
        links.append(f'<a href="{e(r["archive_url"])}" rel="noopener">{"Archived copy" if r["coll"] == "wayback" else "Internet Archive copy"}</a>')
    filt = (f'<span hidden data-pagefind-filter="source">{e(src)}</span><span hidden data-pagefind-filter="type">{e(typ)}</span>'
            + (f'<span hidden data-pagefind-filter="year">{year}</span>' if year else ""))
    sort = f' data-pagefind-sort="date:{r["date"]}"' if r["date"] else ""
    return (f'<p class="meta"{sort}><span data-pagefind-meta="date">{e(r["date"] or "undated")}</span> · {e(src)} · {e(typ)}</p>'
            f'<p class="links">{" · ".join(links)}</p>{filt}')


def doc_page(r):
    depth = slug(r["id"]).count("/") + 1
    body = "".join(f"<p>{e(p)}</p>" for p in paras(read_text(r["text"])))
    title = r["title"] or os.path.basename(r["id"])
    return page(title, f'<article><h1 data-pagefind-meta="title">{e(title)}</h1>{meta_block(r)}'
                       f'<div data-pagefind-body class="doc">{body}</div></article>', depth)


def secs(h, m, s):
    return int(h) * 3600 + int(m) * 60 + int(s)


def video_page(r):
    depth = slug(r["id"]).count("/") + 1
    up = "../" * depth
    base = os.path.basename(r["text"])[:-4]
    yt = r["url"]
    items = []  # (seconds, order, html)
    lines = read_text(r["text"])
    note = lines[0] if lines and lines[0].startswith("(") else ""
    spf = os.path.join(DATA, "speakers", base + ".json")
    officials = set()
    if os.path.exists(spf):
        anon = {}
        for st, name, role, sure, spk, text in json.load(open(spf))["turns"]:
            t = int(st)
            hh = f"{t // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d}"
            if name:
                who = e(name) + ("" if sure else '<span class="q" title="uncertain identification">?</span>')
                if role and role != "Introduced themselves":
                    who += f' <span class="role">{e(role)}</span>'
                    if sure:
                        officials.add(name)
            else:
                anon.setdefault(spk, len(anon) + 1)
                who = f'<span class="anon">Speaker {anon[spk]}</span>'
            items.append((t, 1, f'<div class="turn"><h4 class="who" id="t{t}"><a href="{e(yt)}&amp;t={t}s" rel="noopener">▶ {hh}</a> '
                                f'<b>{who}</b></h4><p>{e(text)}</p></div>'))
    else:
        for p in paras(lines[1:] if note else lines):
            m = TS.match(p)
            if not m:
                continue
            t = secs(*m.groups()[:3])
            hhmmss = ":".join(m.groups()[:3])
            items.append((t, 1, f'<h4 id="t{t}"><a href="{e(yt)}&amp;t={t}s" rel="noopener">▶ {hhmmss}</a></h4><p>{e(m.group(4))}</p>'))
    sp = os.path.join(DATA, "text", "video", base + ".slides.txt")
    nslides = 0
    if os.path.exists(sp):
        blocks = re.split(r"\n\n(?=\[\d\d:\d\d:\d\d\])", open(sp, encoding="utf-8").read())
        for b in blocks:
            m = re.match(r"\[(\d\d):(\d\d):(\d\d)\](?: \(frame at [^)]*\))? (\S+)\.png\n?(.*)", b.strip(), re.S)
            if not m:
                continue
            t = secs(*m.groups()[:3])
            img = f"{up}slides/{base}/{m.group(4)}.webp"
            if not os.path.exists(os.path.join(DATA, "slides", base, m.group(4) + ".webp")):
                continue
            nslides += 1
            ocr = e(m.group(5).strip())
            items.append((t, 0, f'<figure class="slide"><a href="{img}"><img loading="lazy" src="{img}" alt="Slide at {":".join(m.groups()[:3])}"></a>'
                                f'<figcaption><a href="{e(yt)}&amp;t={t}s" rel="noopener">Slide · {":".join(m.groups()[:3])}</a>'
                                f'<details><summary>Slide text (OCR)</summary><pre>{ocr}</pre></details></figcaption></figure>'))
    items.sort()
    gallery = ""
    if nslides:
        gallery = f'<p class="note">{nslides} slides extracted from the video appear inline at the moment they were shown.</p>'
    warn = ('<p class="warn">Machine transcript (Whisper). It contains errors, especially in names. '
            + ('Speakers were identified automatically from voice, nameplates and on-the-record cues; a ? marks an uncertain '
               'identification, and members of the public are named only when they gave their name. ' if officials or os.path.exists(spf) else '')
            + 'Click any timestamp to hear the original.</p>')
    filt = "".join(f'<span hidden data-pagefind-filter="speaker">{e(n)}</span>' for n in sorted(officials))
    if officials:
        gallery = f'<p class="note">Speakers: {e(", ".join(sorted(officials)))}.</p>' + gallery
    title = r["title"]
    return page(title, f'<article><h1 data-pagefind-meta="title">{e(title)}</h1>{meta_block(r)}{filt}{warn}{gallery}'
                       f'<div data-pagefind-body class="transcript">{"".join(h for _, _, h in items)}</div></article>', depth)


def main():
    rows = [json.loads(l) for l in open(os.path.join(DATA, "catalog.jsonl"))]
    if os.path.exists(SITE):
        shutil.rmtree(SITE)
    shutil.copytree(STATIC, os.path.join(SITE, "static"))
    shutil.copytree(os.path.join(DATA, "slides"), os.path.join(SITE, "slides"))
    meetings = defaultdict(lambda: {"bd": [], "video": []})
    for r in rows:
        rel = "d/" + slug(r["id"]) + ".html"
        r["href"] = rel
        write(rel, video_page(r) if r["coll"] == "video" else doc_page(r))
        if r["coll"] == "video":
            meetings[r["date"]]["video"].append(r)
        elif r["coll"] == "boarddocs" and r["kind"] == "meeting":
            meetings[r["date"]]["bd"].append(r)
    # meetings index
    by_year = defaultdict(list)
    for d in sorted(meetings, reverse=True):
        if d:
            by_year[d[:4]].append(d)
    out = ['<h1>Board meetings</h1><p>Every Board of Education meeting on BoardDocs (agendas, minutes, attachments) '
           'and every recorded meeting video (transcript and slides), by date.</p>']
    for y in sorted(by_year, reverse=True):
        out.append(f'<h2 id="y{y}">{y}</h2><table class="meetings"><tbody>')
        for d in by_year[y]:
            m = meetings[d]
            cells = []
            for r in m["bd"]:
                cells.append(f'<a href="{r["href"]}">{e(r["title"].split(" | ")[0])}</a> (<a href="{e(r["url"])}" rel="noopener">BoardDocs</a>)')
            for r in m["video"]:
                cells.append(f'<a href="{r["href"]}">▶ {e(r["title"])}</a>')
            out.append(f'<tr><td class="d">{d}</td><td>{"<br>".join(cells)}</td></tr>')
        out.append("</tbody></table>")
    years = " ".join(f'<a href="#y{y}">{y}</a>' for y in sorted(by_year, reverse=True))
    write("meetings.html", page("Board meetings", f'<p class="years">{years}</p>' + "".join(out), 0))
    # home + about
    counts = defaultdict(int)
    for r in rows:
        counts[r["coll"]] += 1
    nslides = sum(len(fs) for _, _, fs in os.walk(os.path.join(DATA, "slides")))
    span = f'{min(r["date"] for r in rows if r["date"])[:4]}–{max(r["date"] for r in rows)[:4]}'
    tpl = open(os.path.join(STATIC, "..", "index.tpl.html")).read()
    stats = (f'{counts["boarddocs"]:,} BoardDocs records · {counts["video"]} meeting transcripts with {nslides:,} slides · '
             f'{counts["website"]:,} district website pages &amp; documents · {counts["wayback"]:,} archived pages &amp; documents · '
             f'{counts["pac"]} PAC minutes · {span}')
    write("index.html", page("Search", tpl.replace("{{STATS}}", stats),
                             0, '<link rel="stylesheet" href="pagefind/pagefind-ui.css"><script src="pagefind/pagefind-ui.js"></script>'))
    cfg = json.load(open(os.path.join(ROOT, "build", "site.json")))
    about = open(os.path.join(STATIC, "..", "about.tpl.html")).read().replace("{{ORG}}", cfg["org"]).replace("{{REPO}}", cfg["repo"])
    write("about.html", page("About", about, 0))
    print(f"built {len(rows)} pages, {len(meetings)} meeting dates, {nslides} slides -> {SITE}")


if __name__ == "__main__":
    main()
