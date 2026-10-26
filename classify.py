"""Classify forum comments with Cloudflare Clef and write a scan-friendly HTML page.

Reads credentials from cloud-flare.local.sh (gitignored). Resume-safe: each
successful call is appended to classifications.json so a retry does not repeat it.
"""

import html
import json
import re
import sys
import time
import urllib.error
import urllib.request

MODEL = "clef"
LOW_CONFIDENCE = 0.5  # most calls are ~0.9; below this is worth a human look
SOURCE = "comments.json"
CREDS = "cloud-flare.local.sh"
CACHE = "classifications.json"
OUT = "report.html"

INSTRUCTIONS = (
    "Classify `comment`, one post on a college course forum (CS307 Applied AI Lab). "
    "`author` and `thread` are context only. "
    "If the post is mainly an unsolicited promotion or a pitch to contact/pay someone, "
    "choose spam even if the tone is pushy. "
    "If it mainly attacks a person or group and is not a sales pitch, choose toxic. "
    "Ordinary coursework talk, including blunt opinions about the assignment or grading, "
    "is acceptable."
)

CRITERIA = {
    "acceptable": (
        "A real student or staff post: a question, answer, tip, thanks, bug report, "
        "peer feedback on the work, or an opinion about the course. "
        "Mild slang, emoji, and complaints about deadlines, marks, or wifi are fine "
        "when nobody is insulted. Disagreeing is fine. An apology is acceptable."
    ),
    "toxic": (
        "Harassment aimed at a person or group: insults, slurs, humiliation, threats, "
        "telling someone they do not belong, or putting down people for gender, "
        "region, hostel, branch, or caste. "
        "Saying a feature is wrong is acceptable; attacking the person who made it is toxic."
    ),
    "spam": (
        "Unsolicited selling or promotion that is not the student's own coursework: "
        "paid assignment help, leaked papers, notes for sale, crypto, followers, "
        "giveaways that collect personal data, referral cash, unrelated products, "
        "or 'DM / WhatsApp / visit this site' commercial offers."
    ),
}


def load_creds(path):
    creds = dict(re.findall(r'export (\w+)="([^"]*)"', open(path, encoding="utf-8").read()))
    account = creds.get("CLOUDFLARE_ACCOUNT_ID", "")
    token = creds.get("CLOUDFLARE_API_TOKEN", "")
    if not account or not token or "your-cloudflare" in token:
        raise SystemExit(f"{path} needs CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN")
    return account, token


def classify(account, token, comment, attempts=6):
    payload = {
        "state": {
            "comment": comment["comment"],
            "author": comment["author"],
            "thread": comment["thread"],
        },
        "questions": {
            "moderation": {
                "type": "choice",
                "instructions": INSTRUCTIONS,
                "criteria": CRITERIA,
            }
        },
    }
    url = (
        f"https://api.cloudflare.com/client/v4/accounts/{account}"
        f"/ai/run/@cf/cloudflare/{MODEL}"
    )
    body = json.dumps(payload).encode("utf-8")
    wait = 2
    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.load(response)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            if exc.code in (429, 500, 502, 503, 504) and attempt < attempts:
                print(f"  id {comment['id']}: HTTP {exc.code}, retry in {wait}s", flush=True)
                time.sleep(wait)
                wait = min(wait * 2, 30)
                continue
            raise SystemExit(f"id {comment['id']}: HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            if attempt < attempts:
                print(f"  id {comment['id']}: {exc.reason}, retry in {wait}s", flush=True)
                time.sleep(wait)
                wait = min(wait * 2, 30)
                continue
            raise SystemExit(f"id {comment['id']}: {exc.reason}") from exc
        if not data.get("success"):
            raise SystemExit(f"id {comment['id']}: {data.get('errors')}")
        answer = data["result"]["answers"]["moderation"]
        choice = answer["choice"]
        if choice not in CRITERIA:
            raise SystemExit(f"id {comment['id']}: unexpected label {choice!r}")
        return {
            "id": comment["id"],
            "choice": choice,
            "confidence": answer.get("confidence"),
            "probabilities": answer.get("probabilities") or {},
        }
    raise SystemExit(f"id {comment['id']}: gave up after {attempts} tries")


def render(course, comments, by_id):
    counts = {label: 0 for label in CRITERIA}
    rows = []
    low = 0
    for comment in comments:
        result = by_id[comment["id"]]
        label = result["choice"]
        counts[label] += 1
        confidence = result["confidence"]
        if confidence is not None and confidence < LOW_CONFIDENCE:
            low += 1
        probs = result["probabilities"]
        prob_bits = " · ".join(
            f"{name} {probs.get(name, 0):.0%}" for name in CRITERIA
        )
        conf = "" if confidence is None else f"{confidence:.0%}"
        flag = " low" if confidence is not None and confidence < LOW_CONFIDENCE else ""
        rows.append(
            f'<tr data-label="{label}" class="{label}{flag}">'
            f"<td>{comment['id']}</td>"
            f"<td><span class=\"tag\">{label}</span></td>"
            f"<td>{conf}</td>"
            f"<td>{html.escape(comment['author'])}<br><span class=\"meta\">{html.escape(comment['thread'])} · {html.escape(comment['posted_at'])}</span></td>"
            f"<td>{html.escape(comment['comment'])}<br><span class=\"meta\">{prob_bits}</span></td>"
            "</tr>"
        )
    summary = " · ".join(f"{counts[name]} {name}" for name in CRITERIA)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Comment moderation</title>
<style>
  body {{ font: 15px/1.4 system-ui, sans-serif; margin: 24px; color: #1a1a1a; }}
  h1 {{ font-size: 1.25rem; margin-bottom: 0; }}
  p.meta {{ color: #555; }}
  .filters button {{ margin-right: 6px; padding: 4px 10px; cursor: pointer; }}
  .filters button.on {{ background: #1a1a1a; color: #fff; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 12px; }}
  th, td {{ text-align: left; vertical-align: top; padding: 8px; border-bottom: 1px solid #e4e4e4; }}
  th {{ position: sticky; top: 0; background: #fff; }}
  tr.acceptable {{ box-shadow: inset 4px 0 #1b7f3a; }}
  tr.toxic {{ box-shadow: inset 4px 0 #b42318; background: #fff6f5; }}
  tr.spam {{ box-shadow: inset 4px 0 #b54708; background: #fff8f0; }}
  tr.low td:nth-child(3) {{ font-weight: 700; }}
  .tag {{ font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .03em; }}
  .acceptable .tag {{ color: #1b7f3a; }}
  .toxic .tag {{ color: #b42318; }}
  .spam .tag {{ color: #b54708; }}
  .meta {{ color: #666; font-size: 12px; }}
  td:nth-child(1) {{ width: 3rem; color: #666; }}
  td:nth-child(2) {{ width: 7rem; }}
  td:nth-child(3) {{ width: 4rem; }}
  td:nth-child(4) {{ width: 14rem; }}
</style>
</head>
<body>
<h1>{html.escape(course.get("forum", "Comments"))}</h1>
<p class="meta">{html.escape(course.get("course", ""))}<br>
{summary} · {low} low confidence (&lt;50%) · model {MODEL}</p>
<div class="filters">
  <button class="on" data-filter="all">All</button>
  <button data-filter="acceptable">Acceptable</button>
  <button data-filter="toxic">Toxic</button>
  <button data-filter="spam">Spam</button>
  <button data-filter="low">Low confidence</button>
</div>
<table>
<thead><tr><th>Id</th><th>Label</th><th>Conf</th><th>Who</th><th>Comment</th></tr></thead>
<tbody>
{"".join(rows)}
</tbody>
</table>
<script>
document.querySelectorAll(".filters button").forEach((btn) => {{
  btn.onclick = () => {{
    document.querySelectorAll(".filters button").forEach((b) => b.classList.remove("on"));
    btn.classList.add("on");
    const want = btn.dataset.filter;
    document.querySelectorAll("tbody tr").forEach((row) => {{
      const show = want === "all"
        || (want === "low" ? row.classList.contains("low") : row.dataset.label === want);
      row.style.display = show ? "" : "none";
    }});
  }};
}});
</script>
</body>
</html>
"""


def self_check():
    sample = '<script>alert("x")</script>'
    assert html.escape(sample) == "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;"
    assert set(CRITERIA) == {"acceptable", "toxic", "spam"}
    page = render(
        {"course": "C", "forum": "F"},
        [{"id": 1, "author": "A<b>", "thread": "T", "posted_at": "t", "comment": sample}],
        {1: {"id": 1, "choice": "spam", "confidence": 0.1, "probabilities": {"spam": 0.8, "toxic": 0.1, "acceptable": 0.1}}},
    )
    assert "&lt;script&gt;" in page and "<script>alert" not in page
    assert "A&lt;b&gt;" in page
    print("self-check ok")


def main():
    if "--self-check" in sys.argv:
        self_check()
        return
    account, token = load_creds(CREDS)
    course = json.load(open(SOURCE, encoding="utf-8"))
    comments = course["comments"]
    try:
        done = json.load(open(CACHE, encoding="utf-8"))
    except FileNotFoundError:
        done = []
    by_id = {row["id"]: row for row in done}
    for comment in comments:
        if comment["id"] in by_id:
            continue
        result = classify(account, token, comment)
        by_id[comment["id"]] = result
        done.append(result)
        json.dump(done, open(CACHE, "w", encoding="utf-8"), indent=2)
        print(f"{result['id']:>3}  {result['choice']:<12} {result['confidence']}", flush=True)
    missing = [c["id"] for c in comments if c["id"] not in by_id]
    if missing:
        raise SystemExit(f"missing classifications: {missing}")
    open(OUT, "w", encoding="utf-8").write(render(course, comments, by_id))
    print(f"wrote {OUT} ({len(comments)} comments)")


if __name__ == "__main__":
    main()
