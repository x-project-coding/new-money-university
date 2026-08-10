#!/usr/bin/env python3
"""Generate branded 16:9 course infographics with GPT Image 2 via OpenRouter's
dedicated images endpoint (which honors aspect_ratio, unlike chat completions).

    OPENROUTER_API_KEY=... python3 gen_course_images.py prompts.json outdir/

prompts.json: [{"slug": "funnel", "prompt": "..."}, ...]
Each prompt describes a full-frame 16:9 infographic and the exact Russian text.
Existing outdir/<slug>.png files are skipped, so reruns only fill gaps.
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
    "Premium 16:9 landscape infographic that fills the entire frame edge to edge "
    "with no large empty areas. Dark background #0b0b0e with subtle darker texture, "
    "bold red #e62e39 accents, white and light-gray text. Sleek modern flat design, "
    "rounded card panels with thin borders, thin-line outline icons, clean bold "
    "sans-serif typography, clear visual hierarchy, generous internal padding, "
    "professional dashboard aesthetic, high quality, crisp. No watermark, no extra "
    "logos. Render every Russian label exactly as written, correctly spelled. "
    "Composition: "
)


def generate(slug: str, prompt: str, outdir: str, retries: int = 2) -> str:
    path = os.path.join(outdir, f"{slug}.png")
    if os.path.exists(path):
        return f"skip {slug}"
    body = json.dumps({
        "model": MODEL,
        "prompt": STYLE + prompt,
        "aspect_ratio": "16:9",
        "resolution": "1K",
    }).encode()
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/images",
                data=body,
                headers={
                    "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
                    "Content-Type": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=300) as r:
                d = json.load(r)
            png = base64.b64decode(d["data"][0]["b64_json"])
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
