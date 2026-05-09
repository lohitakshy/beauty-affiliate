"""
Video Queue Processor
Reads from video_queue.jsonl and sends each job to Kling AI (or Runway).
Run this separately: python video_processor.py

Kling AI API docs: https://klingai.com/api (currently waitlist — use Runway as fallback)
Runway API docs:   https://docs.runwayml.com
"""

import os, json, time, requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

KLING_API_KEY  = os.getenv("KLING_API_KEY")
RUNWAY_API_KEY = os.getenv("RUNWAY_API_KEY")
BUFFER_TOKEN   = os.getenv("BUFFER_TOKEN")
BUFFER_PROFILE = os.getenv("BUFFER_PROFILE_ID")

QUEUE_FILE     = "video_queue.jsonl"
PROCESSED_FILE = "video_queue_done.jsonl"

# Your AI model photo — upload once, reuse for every video
# The model photo gets animated differently for each product via the kling_prompt
MODEL_PHOTO_URL = os.getenv("MODEL_PHOTO_URL")  # host on S3, Cloudinary, or GitHub


def animate_with_kling(image_url: str, prompt: str) -> str | None:
    """
    Sends image + prompt to Kling AI image-to-video API.
    Returns a video URL when rendering completes.
    Kling currently requires API waitlist access — use Runway as fallback.
    """
    if not KLING_API_KEY:
        return None

    # Step 1: Submit job
    resp = requests.post(
        "https://api.klingai.com/v1/videos/image2video",
        headers={
            "Authorization": f"Bearer {KLING_API_KEY}",
            "Content-Type":  "application/json",
        },
        json={
            "model_name":   "kling-v1",
            "image_url":    image_url,   # your AI model photo
            "prompt":       prompt,      # how-to-use motion prompt
            "duration":     5,           # 5 seconds
            "cfg_scale":    0.5,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        print(f"  Kling error: {resp.text}")
        return None

    task_id = resp.json().get("data", {}).get("task_id")
    if not task_id:
        return None

    # Step 2: Poll until done (usually 60-120 seconds)
    print(f"  Kling task {task_id} — waiting for render...")
    for _ in range(30):
        time.sleep(10)
        poll = requests.get(
            f"https://api.klingai.com/v1/videos/image2video/{task_id}",
            headers={"Authorization": f"Bearer {KLING_API_KEY}"},
            timeout=15,
        )
        data = poll.json().get("data", {})
        status = data.get("task_status")

        if status == "succeed":
            video_url = data["task_result"]["videos"][0]["url"]
            print(f"  Video ready: {video_url}")
            return video_url
        elif status == "failed":
            print(f"  Kling render failed")
            return None

    print("  Kling timed out")
    return None


def animate_with_runway(image_url: str, prompt: str) -> str | None:
    """
    Fallback: uses Runway Gen-3 image-to-video API.
    Sign up at runwayml.com — $0.05/second of video generated.
    """
    if not RUNWAY_API_KEY:
        return None

    resp = requests.post(
        "https://api.dev.runwayml.com/v1/image_to_video",
        headers={
            "Authorization": f"Bearer {RUNWAY_API_KEY}",
            "Content-Type":  "application/json",
            "X-Runway-Version": "2024-11-06",
        },
        json={
            "model":        "gen3a_turbo",
            "promptImage":  image_url,
            "promptText":   prompt,
            "duration":     5,
            "ratio":        "768:1344",  # 9:16 vertical for Reels
        },
        timeout=30,
    )
    if resp.status_code not in (200, 201):
        print(f"  Runway error: {resp.text}")
        return None

    task_id = resp.json().get("id")
    if not task_id:
        return None

    print(f"  Runway task {task_id} — waiting...")
    for _ in range(20):
        time.sleep(15)
        poll = requests.get(
            f"https://api.dev.runwayml.com/v1/tasks/{task_id}",
            headers={"Authorization": f"Bearer {RUNWAY_API_KEY}"},
            timeout=15,
        )
        data = poll.json()
        if data.get("status") == "SUCCEEDED":
            video_url = data["output"][0]
            print(f"  Video ready: {video_url}")
            return video_url
        elif data.get("status") == "FAILED":
            print(f"  Runway failed: {data.get('failure')}")
            return None

    return None


def post_video_to_buffer(caption: str, video_url: str):
    """Posts the rendered video to Instagram via Buffer."""
    if not BUFFER_TOKEN:
        print("  No Buffer token — skipping post")
        return

    resp = requests.post(
        "https://api.bufferapp.com/1/updates/create.json",
        headers={"Authorization": f"Bearer {BUFFER_TOKEN}"},
        json={
            "profile_ids":  [BUFFER_PROFILE],
            "text":         caption,
            "scheduled_at": "next_best_time",
            "media":        {"video": video_url},
        },
        timeout=15,
    )
    print(f"  Posted to Buffer: {resp.status_code}")


def process_queue():
    queue_path = Path(QUEUE_FILE)
    if not queue_path.exists():
        print("No queue file found. Run beauty_agent.py first.")
        return

    jobs = queue_path.read_text().strip().splitlines()
    print(f"Found {len(jobs)} queued videos\n")

    done = []
    remaining = []

    for line in jobs:
        job = json.loads(line)
        if job.get("status") == "done":
            done.append(line)
            continue

        print(f"Processing: {job['product_name']}")

        # Use model photo if product image unavailable
        image = job.get("image_url") or MODEL_PHOTO_URL
        prompt = job.get("kling_prompt", f"Person applying {job['product_name']} to their face, smooth natural motion, beauty tutorial style, 9:16 vertical")

        # Try Kling first, fall back to Runway
        video_url = animate_with_kling(image, prompt)
        if not video_url:
            print("  Trying Runway fallback...")
            video_url = animate_with_runway(image, prompt)

        if video_url:
            post_video_to_buffer(job["caption"], video_url)
            job["status"]    = "done"
            job["video_url"] = video_url
            done.append(json.dumps(job))
            print(f"  Done: {job['product_name']}\n")
        else:
            print(f"  Could not render video for {job['product_name']} — leaving in queue\n")
            remaining.append(line)

        time.sleep(5)

    # Rewrite queue with only unprocessed jobs
    queue_path.write_text("\n".join(remaining) + ("\n" if remaining else ""))

    # Append completed to done file
    with open(PROCESSED_FILE, "a") as f:
        for d in done:
            f.write(d + "\n")

    print(f"\nComplete. {len(done)} processed, {len(remaining)} remaining.")


if __name__ == "__main__":
    process_queue()
