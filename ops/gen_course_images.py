#!/usr/bin/env python3
"""Generate branded course infographics with GPT Image 2 via OpenRouter.

Usage:
    OPENROUTER_API_KEY=... python3 gen_course_images.py prompts.json outdir/

prompts.json: [{"slug": "funnel", "prompt": "..."}, ...]
Each prompt should describe the layout AND the exact (Russian) text to render.
Already-existing outdir/<slug>.png files are skipped, so reruns only fill gaps.
"""

import base64
import json
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

MODEL = "openai/gpt-5.4-image-2"
STYLE = (
    "Modern flat vector infographic, dark background #0b0b0e, red #e62e39 accents "
    "with white and light-gray text, minimal geometric shapes, thin outline icons, "
    "clean sans-serif typography, generous spacing, subtle diagonal texture, "
    "no watermark, no logos other than described. All labels must be spelled "
    "exactly as given, in Russian. "
)


def generate(slug: str, prompt: str, outdir: str, retries: int = 2) -> str:
    path = os.path.join(outdir, f"{slug}.png")
    if os.path.exists(path):
        return f"skip {slug}"
    body = json.dumps(
        {
            "model": MODEL,
            "messages": [{"role": "user", "content": STYLE + prompt}],
            "modalities": ["image", "text"],
        }
    ).encode()
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                data=body,
                headers={
                    "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
                    "Content-Type": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=300) as r:
                d = json.load(r)
            url = d["choices"][0]["message"]["images"][0]["image_url"]["url"]
            png = base64.b64decode(url.split(",", 1)[1])
            with open(path, "wb") as f:
                f.write(png)
            return f"ok {slug} ({len(png)} bytes)"
        except Exception as e:
            if attempt == retries:
                return f"FAIL {slug}: {e}"
            time.sleep(10)


def main():
    prompts_file, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    prompts = json.load(open(prompts_file))
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(generate, p["slug"], p["prompt"], outdir) for p in prompts]
        for fut in as_completed(futures):
            print(fut.result(), flush=True)


if __name__ == "__main__":
    main()
