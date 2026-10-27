"""Classify forum comments as acceptable / toxic / spam with Cloudflare's Clef model,
and write an HTML page of the results.

Usage:
    python classify.py comments.json clef-flash results.html
    python classify.py comments-v2.json clef results-v2.html

Credentials are read from cloud-flare.local.sh (never committed).
"""
import argparse
import html
import json
import re
import time
import urllib.error
import urllib.request

INSTRUCTIONS = (
    "Classify `comment`, a post by a student (or teacher) on the discussion forum of a "
    "college course on applied AI. `thread` is the forum thread it was posted in. "
    "Judge the comment as a forum moderator would: blunt criticism, frustration, "
    "complaints about the course, casual language and jokes are normal and acceptable. "
    "Only flag a comment if it is clearly harmful to people or clearly promotional."
)

CRITERIA = {
    "acceptable": (
        "A genuine post: questions, answers, sharing work, feedback (even harsh or "
        "negative feedback about work, tools or the course), complaints, mild swearing "
        "not aimed at a person, jokes, or off-hand chat between classmates."
    ),
    "toxic": (
        "Attacks, insults, threatens, harasses, humiliates or demeans a person or group "
        "(including slurs, sexual remarks, or mocking someone's background, gender, "
        "caste, religion or ability), or encourages others to do so. Also toxic: a "
        "comment that is mostly (even 75-80%) genuine feedback on someone's work but "
        "adds a personal jab, insult or put-down aimed at the person themselves."
    ),
    "spam": (
        "Advertising or self-promotion unrelated to helping with the course: selling "
        "assignment-writing or other services, referral links, crypto/betting/job "
        "schemes, contact numbers for paid help, or repeated junk text. Also spam: a "
        "post that is mostly a genuine question or request for feedback but includes "
        "a pitch that benefits only the poster (sign-ups, referral bonuses, followers, "
        "their own product)."
    ),
}

LABEL_COLOURS = {"acceptable": "#1a7f37", "toxic": "#cf222e", "spam": "#9a6700"}
LOW_CONFIDENCE = 0.5


def load_credentials(path="cloud-flare.local.sh"):
    with open(path, encoding="utf-8") as f:
        creds = dict(re.findall(r'export (\w+)="([^"]*)"', f.read()))
    return creds["CLOUDFLARE_ACCOUNT_ID"], creds["CLOUDFLARE_API_TOKEN"]


def classify(comment, account, token, model, retries=5):
    payload = {
        "state": {"comment": comment["comment"], "thread": comment.get("thread", "")},
        "questions": {
            "moderation": {
                "type": "choice",
                "instructions": INSTRUCTIONS,
                "criteria": CRITERIA,
            }
        },
    }
    request = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/@cf/cloudflare/{model}",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.load(response)
            if not data.get("success"):
                raise RuntimeError(f"Clef error: {data.get('errors')}")
            return data["result"]["answers"]["moderation"]
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise SystemExit("Bad account ID or API token (HTTP %d)." % e.code)
            if e.code == 429 or e.code >= 500:
                time.sleep(2 ** attempt)
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Gave up on comment {comment['id']} after {retries} attempts")


def write_html(meta, results, model, path):
    counts = {label: 0 for label in CRITERIA}
    for r in results:
        counts[r["choice"]] += 1
    low = sum(r["confidence"] < LOW_CONFIDENCE for r in results)

    rows = []
    for r in results:
        colour = LABEL_COLOURS[r["choice"]]
        probs = " ".join(
            f"{label[0].upper()} {r['probabilities'].get(label, 0):.2f}" for label in CRITERIA
        )
        flag = " low" if r["confidence"] < LOW_CONFIDENCE else ""
        rows.append(
            f'<tr class="{r["choice"]}{flag}">'
            f'<td class="id">{r["id"]}</td>'
            f'<td><span class="badge" style="background:{colour}">{r["choice"]}</span></td>'
            f'<td class="num">{r["confidence"]:.2f}</td>'
            f'<td class="probs">{probs}</td>'
            f'<td><div class="meta">{html.escape(r["author"])} · {html.escape(r["thread"])}</div>'
            f'{html.escape(r["comment"])}</td></tr>'
        )

    buttons = "".join(
        f'<button data-f="{label}">{label} ({n})</button>' for label, n in counts.items()
    )
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Clef results ({html.escape(model)})</title>
<style>
body {{ font: 15px/1.45 system-ui, sans-serif; margin: 24px; color: #1f2328; background: #fff; }}
h1 {{ font-size: 20px; margin: 0 0 4px; }}
.sub {{ color: #59636e; margin-bottom: 16px; }}
.bar {{ position: sticky; top: 0; background: #fff; padding: 8px 0; z-index: 1; }}
button {{ font: inherit; padding: 4px 10px; margin: 0 6px 6px 0; border: 1px solid #d0d7de;
         border-radius: 6px; background: #f6f8fa; cursor: pointer; }}
button.on {{ background: #0969da; color: #fff; border-color: #0969da; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border-bottom: 1px solid #d8dee4; padding: 8px; vertical-align: top; text-align: left; }}
th {{ background: #f6f8fa; position: sticky; top: 44px; }}
tr.low td {{ background: #fff8c5; }}
tr.toxic td:first-child {{ border-left: 4px solid {LABEL_COLOURS["toxic"]}; }}
tr.spam td:first-child {{ border-left: 4px solid {LABEL_COLOURS["spam"]}; }}
.badge {{ color: #fff; border-radius: 10px; padding: 2px 8px; font-size: 13px; }}
.id, .num {{ font-variant-numeric: tabular-nums; white-space: nowrap; }}
.probs {{ font-size: 12px; color: #59636e; white-space: nowrap; }}
.meta {{ font-size: 12px; color: #59636e; margin-bottom: 2px; }}
</style></head><body>
<h1>{html.escape(meta.get("forum", "Forum comments"))}</h1>
<div class="sub">{html.escape(meta.get("course", ""))} · model <b>{html.escape(model)}</b> ·
{len(results)} comments · yellow rows = confidence below {LOW_CONFIDENCE} ({low})</div>
<div class="bar"><button data-f="all" class="on">all ({len(results)})</button>{buttons}<button data-f="low">low confidence ({low})</button></div>
<table><thead><tr><th>#</th><th>Clef label</th><th>Conf.</th><th>Probabilities (A/T/S)</th><th>Comment</th></tr></thead>
<tbody>
{chr(10).join(rows)}
</tbody></table>
<script>
document.querySelectorAll("button").forEach(b => b.onclick = () => {{
  document.querySelectorAll("button").forEach(x => x.classList.toggle("on", x === b));
  document.querySelectorAll("tbody tr").forEach(tr => {{
    tr.hidden = b.dataset.f !== "all" && !tr.classList.contains(b.dataset.f);
  }});
}});
</script>
</body></html>
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input", help="comments JSON file")
    parser.add_argument("model", choices=["clef-flash", "clef"])
    parser.add_argument("output", help="HTML file to write")
    args = parser.parse_args()

    account, token = load_credentials()
    with open(args.input, encoding="utf-8") as f:
        meta = json.load(f)

    results = []
    for c in meta["comments"]:
        answer = classify(c, account, token, args.model)
        results.append({**c, **{k: answer[k] for k in ("choice", "probabilities", "confidence")}})
        print(f"{c['id']:>3}  {answer['choice']:<10}  {answer['confidence']:.2f}")

    write_html(meta, results, args.model, args.output)
    json_path = args.output.rsplit(".", 1)[0] + ".json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"Wrote {args.output} and {json_path}")


if __name__ == "__main__":
    main()
