# Notes

## How to run

Needs Python 3 (standard library only) and a Cloudflare account ID and Workers AI token in
`cloud-flare.local.sh` (copy `cloud-flare.sh` and fill in the values).

```
python classify.py comments.json clef-flash results.html
python classify.py comments-v2.json clef results-v2.html
```

Each run prints one line per comment, writes the HTML page, and also saves the raw Clef
answers (label, probabilities, confidence) to a `.json` file with the same name. In the
HTML page you can filter by label, and rows where Clef's confidence is below 0.5 are
highlighted in yellow.

## Criteria changes for v2

After reviewing the first set, I added two rules to the toxic and spam criteria before
running `comments-v2.json`:

- **Toxic:** a comment that is mostly (75-80%) genuine feedback on someone's work, but adds
  a personal jab or put-down aimed at the person, counts as toxic.
- **Spam:** a post that is mostly a genuine question or feedback request, but includes a
  pitch that benefits only the poster (sign-ups, referral bonuses, their own product),
  counts as spam.

Re-running v2 with these rules changed 3 of the 100 labels. `results-v2.html` is from the
updated criteria; `results.html` is from the original criteria.

## Tools and models used

- **Cloudflare Workers AI:** `clef-flash` for `comments.json`, `clef` for `comments-v2.json`.
- **Claude Code (Claude Opus 5.5):** to read the task, write `classify.py` and the HTML
  output, set up the repo, and format my notes into Markdown.
- **My own judgement:** I reviewed every comment and Clef's label myself for
  `MISTAKES.md` and `MISTAKES-v2.md`. The AI did not decide any labels; it only checked that
  the comment ids and Clef labels I wrote matched the results, and tidied the wording.

## What I felt about doing this

Most of the comments were easy to label. Clef's confidence scores were not always a good
guide: many of the low-confidence (yellow) rows still had the right label.

**Sarcasm.** Clef mostly fails to detect sarcasm. Sarcastic put-downs like "Truly
groundbreaking research, Nobel prize loading 👏👏" were marked acceptable instead of toxic.

**Keywords over context.** When a comment has links or words like promo, referral, free,
workshop, internship or jobs, Clef tends to mark it as spam. The professor's post about a
free AI workshop was marked spam, even though it only benefits the students. Clef does not
consider who is posting or the full context of the text, which is why it put a professor's
helpful post in spam and sarcastic messages in acceptable. (Note: my program only sent the
comment and thread to Clef, not the author, so it had no way to know who was posting.
Adding the author's role would be a good next step.)

**The hardest cases** were comments where 75-80% of the post genuinely helps the community,
but the last few lines push a promo code or referral link. These sit between acceptable and
spam, so I marked them borderline, acknowledging the helpful part while noting the
promotion. If I were fixing this on a real forum, I would remove or hide the referral part
by default and keep only the helpful part of the post.
