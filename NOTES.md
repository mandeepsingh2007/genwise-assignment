# Notes

## How to run

Python 3 is enough. No packages to install.

1. Copy `cloud-flare.sh` to `cloud-flare.local.sh`.
2. Put your Cloudflare account ID and API token in that file. It is gitignored, so it will not be committed.
3. From this folder, run:

```
python classify.py
```

The script reads `comments.json`, calls Cloudflare Clef once per comment, and writes `report.html`. Open that file in a browser. Labels are colored, and the buttons filter by acceptable, toxic, spam, or low confidence.

Results are saved in `classifications.json`. A second run reuses that file and only rebuilds the HTML. Delete it if you want to call the API again.

## Tools and models

I used Cursor to write `classify.py` and `report.html`. Classification is Cloudflare Workers AI, model `clef` (`@cf/cloudflare/clef`). I read the HTML myself for `MISTAKES.md`.

## What this felt like

The script was the quick part. Reading all 100 comments was the actual work. Clef looked right on most of them, including the obvious ads and the insults. Two still felt wrong to me: 42, because the tone is harsh even though it is a suggestion, and 88, because it does not ask anything about the course. Confident scores did not make those two feel settled.
