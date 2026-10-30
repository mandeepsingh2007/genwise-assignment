# Notes (version 2)

## How to run

Same setup as the first batch. Python 3, no packages. Credentials stay in `cloud-flare.local.sh` (gitignored).

From this folder:

```
python classify.py comments-v2.json classifications-v2.json report-v2.html
```

That reads `comments-v2.json`, calls Clef, and writes `report-v2.html`. Open that file in a browser. The first batch is still `report.html`; this command does not overwrite it.

`classifications-v2.json` is only a cache so a second run does not call the API again. The HTML already contains every label, so the cache does not need to be pushed. Delete it if you want a fresh API run.

With no arguments, `python classify.py` still runs the original `comments.json` into `report.html`.

## Tools and models

Cursor wrote the small change that lets `classify.py` take an input file, a cache file, and an output HTML path. Classification is still Cloudflare Workers AI, model `clef` (`@cf/cloudflare/clef`), with the same three labels: acceptable, toxic, spam.

## What this felt like

The script was the same job on a new forum thread (assignment 4). Clef returned 73 acceptable, 15 spam, and 12 toxic. A few scores were low, under 50%: comments 7, 10, 23, 40, 61, 62, 83, and 96. Those are the ones I would read twice. I have not written `MISTAKES-v2.md`; that check is still mine to do by hand.
