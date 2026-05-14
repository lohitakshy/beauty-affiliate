"""
Beauty Affiliate AI Agent
Runs daily: finds top products → generates pages → queues videos → posts to Instagram
Requirements: pip install anthropic requests python-dotenv schedule
"""

import os, json, time, schedule, requests
from datetime import datetime
from anthropic import Anthropic
from dotenv import load_dotenv
from image_downloader import download_all_images, auto_git_push
from generate_products_json import build_products_json

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# ── CONFIG ──────────────────────────────────────────────────────────────────

AFFILIATE_IDS = {
    "amazon":  os.getenv("AMAZON_AFFILIATE_ID"),   # e.g. "yourtag-20"
    "sephora": os.getenv("SEPHORA_AFFILIATE_ID"),  # via Rakuten
    "ebay":    os.getenv("EBAY_CAMPAIGN_ID"),       # via EPN
    "ulta":    os.getenv("ULTA_AFFILIATE_ID"),      # via Impact
    "glossier":os.getenv("GLOSSIER_AFFILIATE_ID"), # via ShareASale
}

CATEGORIES = [
    "skincare", "makeup", "fragrance", "haircare",
    "body care", "nail care", "beauty tools", "wellness beauty"
]

PRODUCTS_PER_CATEGORY = 10

SERPAPI_KEY  = os.getenv("SERPAPI_KEY")    # serpapi.com — free tier available
BUFFER_TOKEN = os.getenv("BUFFER_TOKEN")   # buffer.com API token
BUFFER_PROFILE_ID = os.getenv("BUFFER_PROFILE_ID")

# ── STEP 1: PRODUCT DISCOVERY ────────────────────────────────────────────────

def find_trending_products(category):
    """
    Uses SerpAPI to pull trending/bestselling products from Google Shopping.
    Returns a list of product dicts with name, brand, price, image_url.
    """
    url = "https://serpapi.com/search"
    params = {
        "engine":   "google_shopping",
        "q":        f"best {category} products 2025 beauty",
        "api_key":  SERPAPI_KEY,
        "num":      PRODUCTS_PER_CATEGORY,
        "tbs":      "p_ord:rv",   # sort by review score
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    products = []
    for item in data.get("shopping_results", [])[:PRODUCTS_PER_CATEGORY]:
            # Get direct Amazon URL if available
            product_link = item.get("product_link", "") or item.get("link", "")
            asin = ""
            amazon_url = ""
            
            # Extract ASIN from Amazon URL
            import re as _re
            asin_match = _re.search(r"/dp/([A-Z0-9]{10})", product_link)
            if asin_match:
                asin = asin_match.group(1)
                amazon_url = f"https://www.amazon.com/dp/{asin}?tag=nacre0c-20"
            
            # Get highest quality image available
            image_url = (
                item.get("original", "") or
                item.get("thumbnail", "") or ""
            )
            # Use SerpAPI image search for better quality if thumbnail is low-res
            
            products.append({
                "name":        item.get("title", ""),
                "brand":       item.get("source", ""),
                "price":       item.get("price", ""),
                "rating":      item.get("rating", 0),
                "reviews":     item.get("reviews", 0),
                "image_url":   image_url,
                "amazon_url":  amazon_url,
                "asin":        asin,
                "product_link": product_link,
                "category":    category,
            })
    return products

# ── STEP 2: AI REVIEW SUMMARY ────────────────────────────────────────────────

def generate_review_summary(product):
    """
    Asks Claude to write a compelling review summary and video script for the product.
    """
    prompt = f"""You are a beauty content expert. For the product below, produce a JSON object with these exact keys:

Product: {product['name']} by {product['brand']} — Category: {product['category']}

Keys to produce:
- "hook": one punchy sentence (under 12 words) that would stop someone mid-scroll
- "review_summary": 2 sentences covering what makes this product stand out
- "pros": list of 3 short bullet points (max 6 words each)
- "cons": list of 1-2 short cons
- "how_to_use": 2-sentence simple usage guide
- "instagram_caption": full Instagram caption with hook, benefits, CTA to link in bio, 12 hashtags
- "video_script": 30-second spoken script for a Reel: [0-3s intro] [3-18s how-to-use] [18-25s results] [25-30s CTA]
- "kling_prompt": image-to-video prompt for Kling AI showing a person applying/using this product naturally

Return ONLY valid JSON, no markdown, no extra text."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = message.content[0].text.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: extract between first { and last }
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        return json.loads(raw[start:end])

# ── STEP 3: AFFILIATE LINK BUILDER ──────────────────────────────────────────

def build_affiliate_links(product_name, brand):
    """
    Constructs affiliate URLs for each retailer.
    In production, replace with each retailer's deep-link API.
    """
    encoded = requests.utils.quote(f"{brand} {product_name}")

    links = {}

    # Amazon Associates - use direct product URL if ASIN available
    if AFFILIATE_IDS["amazon"]:
        asin = product_name  # will be overridden below
        links["amazon"] = (
            f"https://www.amazon.com/s?k={encoded}"
            f"&tag={AFFILIATE_IDS['amazon']}"
        )

    # Sephora via Rakuten (deep link format)
    if AFFILIATE_IDS["sephora"]:
        links["sephora"] = (
            f"https://click.linksynergy.com/deeplink?"
            f"id={AFFILIATE_IDS['sephora']}&mid=2530"
            f"&murl=https%3A%2F%2Fwww.sephora.com%2Fsearch%3Fkeyword%3D{encoded}"
        )

    # eBay Partner Network
    if AFFILIATE_IDS["ebay"]:
        links["ebay"] = (
            f"https://www.ebay.com/sch/i.html?_nkw={encoded}"
            f"&mkcid=1&mkrid=711-53200-19255-0"
            f"&siteid=0&campid={AFFILIATE_IDS['ebay']}&customid=&toolid=10001&mkevt=1"
        )

    # Ulta via Impact (simplified — replace with Impact deep-link API)
    if AFFILIATE_IDS["ulta"]:
        links["ulta"] = (
            f"https://www.ulta.com/search?search={encoded}"
            f"&utm_source=impact&utm_medium=affiliate"
            f"&utm_campaign={AFFILIATE_IDS['ulta']}"
        )

    # Glossier direct affiliate
    if AFFILIATE_IDS["glossier"]:
        links["glossier"] = (
            f"https://www.glossier.com/products?ref={AFFILIATE_IDS['glossier']}"
        )

    return links

# ── STEP 4: GENERATE PRODUCT PAGE HTML ──────────────────────────────────────

def generate_product_page(product, ai_content, affiliate_links):
    """
    Generates a standalone HTML product page — your Linktree replacement.
    Save to /docs/{category}/{slug}.html and host on GitHub Pages or Netlify for free.
    """
    pros_html  = "".join(f"<li>{p}</li>" for p in ai_content.get("pros", []))
    cons_html  = "".join(f"<li>{p}</li>" for p in ai_content.get("cons", []))

    buy_buttons = ""
    retailer_names = {
        "amazon":   ("Amazon",   "#FF9900"),
        "sephora":  ("Sephora",  "#000000"),
        "ebay":     ("eBay",     "#0064D2"),
        "ulta":     ("Ulta",     "#E0007A"),
        "glossier": ("Glossier", "#D4D2C9"),
    }
    for key, url in affiliate_links.items():
        name, color = retailer_names.get(key, (key.title(), "#333"))
        buy_buttons += f"""
        <a href="{url}" target="_blank" rel="noopener" class="buy-btn"
           style="background:{color};color:{'#000' if key=='glossier' else '#fff'}">
          Buy on {name}
        </a>"""

    slug     = product['name'].lower().replace(" ", "-")[:40]
    category = product['category'].title()

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{product['name']} — {category} Review</title>
<meta name="description" content="{ai_content.get('review_summary', '')}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;600&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
  :root {{
    --cream: #FAF8F5;
    --ink:   #1A1612;
    --muted: #7A7167;
    --accent:#C8956B;
    --border:#E8E2D9;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0 }}
  body {{
    font-family: 'DM Sans', sans-serif;
    background: var(--cream);
    color: var(--ink);
    min-height: 100vh;
  }}
  .hero {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    min-height: 60vh;
    gap: 0;
  }}
  .hero-img {{
    background: #EDE8E0;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
  }}
  .hero-img img {{
    width: 100%;
    height: 100%;
    object-fit: cover;
  }}
  .hero-content {{
    padding: 4rem 3rem;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 1.25rem;
  }}
  .category-tag {{
    font-size: 11px;
    letter-spacing: .12em;
    text-transform: uppercase;
    color: var(--accent);
    font-weight: 500;
  }}
  h1 {{
    font-family: 'Cormorant Garamond', serif;
    font-size: 2.4rem;
    font-weight: 600;
    line-height: 1.15;
  }}
  .brand {{
    font-size: 13px;
    color: var(--muted);
    letter-spacing: .04em;
  }}
  .rating-row {{
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    color: var(--muted);
  }}
  .stars {{ color: var(--accent); font-size: 15px; }}
  .hook {{
    font-family: 'Cormorant Garamond', serif;
    font-size: 1.2rem;
    font-style: italic;
    color: var(--muted);
    border-left: 2px solid var(--accent);
    padding-left: 1rem;
  }}
  .buy-stack {{
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin-top: .5rem;
  }}
  .buy-btn {{
    display: block;
    text-align: center;
    padding: 12px 20px;
    border-radius: 4px;
    font-size: 13px;
    font-weight: 500;
    text-decoration: none;
    letter-spacing: .03em;
    transition: opacity .15s;
  }}
  .buy-btn:hover {{ opacity: .85 }}
  .body-section {{
    max-width: 820px;
    margin: 4rem auto;
    padding: 0 2rem;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 3rem;
  }}
  .section-title {{
    font-family: 'Cormorant Garamond', serif;
    font-size: 1.4rem;
    margin-bottom: 1rem;
  }}
  ul {{ list-style: none; display: flex; flex-direction: column; gap: 8px }}
  li {{ font-size: 14px; color: var(--muted); padding-left: 1.2rem; position: relative }}
  li::before {{ content: '—'; position: absolute; left: 0; color: var(--accent) }}
  .review-block {{
    max-width: 820px;
    margin: 0 auto 4rem;
    padding: 0 2rem;
  }}
  .review-text {{
    font-size: 15px;
    line-height: 1.8;
    color: var(--muted);
  }}
  .how-to {{
    background: #F0EBE3;
    padding: 2rem;
    border-radius: 4px;
    margin-top: 2rem;
  }}
  .how-to p {{ font-size: 14px; line-height: 1.8; color: var(--muted) }}
  footer {{
    border-top: 1px solid var(--border);
    padding: 2rem;
    text-align: center;
    font-size: 11px;
    color: var(--muted);
    letter-spacing: .03em;
  }}
  @media (max-width: 700px) {{
    .hero {{ grid-template-columns: 1fr }}
    .hero-img {{ height: 280px }}
    .hero-content {{ padding: 2rem 1.5rem }}
    .body-section {{ grid-template-columns: 1fr; gap: 2rem; margin: 2rem auto }}
    h1 {{ font-size: 1.8rem }}
  }}
</style>
</head>
<body>

<div class="hero">
  <div class="hero-img">
    <img src="{product.get('image_url', '')}" alt="{product['name']}" loading="lazy">
  </div>
  <div class="hero-content">
    <div class="category-tag">{category}</div>
    <h1>{product['name']}</h1>
    <div class="brand">{product.get('brand', '')}</div>
    <div class="rating-row">
      <span class="stars">{"★" * int(float(product.get("rating", 4)))}</span>
      <span>{product.get('rating', '')} · {product.get('reviews', '')} reviews</span>
    </div>
    <p class="hook">{ai_content.get('hook', '')}</p>
    <div class="buy-stack">
      <p style="font-size:12px;color:var(--muted);letter-spacing:.04em;text-transform:uppercase">Where to buy</p>
      {buy_buttons}
    </div>
  </div>
</div>

<div class="review-block">
  <h2 class="section-title">Our take</h2>
  <p class="review-text">{ai_content.get('review_summary', '')}</p>
  <div class="how-to">
    <h3 style="font-family:'Cormorant Garamond',serif;font-size:1.1rem;margin-bottom:.75rem">How to use</h3>
    <p>{ai_content.get('how_to_use', '')}</p>
  </div>
</div>

<div class="body-section">
  <div>
    <h2 class="section-title">What we love</h2>
    <ul>{pros_html}</ul>
  </div>
  <div>
    <h2 class="section-title">Worth knowing</h2>
    <ul>{cons_html}</ul>
  </div>
</div>

<footer>
  This page contains affiliate links. We may earn a commission at no extra cost to you.
</footer>

</body>
</html>"""

    # Save the file
    out_dir = f"docs/{product['category'].replace(' ', '_')}"
    os.makedirs(out_dir, exist_ok=True)
    filepath = f"{out_dir}/{slug}.html"
    with open(filepath, "w") as f:
        f.write(html)

    print(f"  Page saved: {filepath}")
    return filepath

# ── STEP 5: QUEUE VIDEO CREATION ─────────────────────────────────────────────

def queue_video_creation(product, ai_content):
    """
    Writes a video job to a queue file.
    A separate process (or Make.com webhook) picks this up and:
      1. Sends kling_prompt to Kling AI API to animate your model photo
      2. Stitches clips in CapCut or RunwayML
      3. Burns in the video_script as captions
      4. Sends to Buffer queue for Instagram posting
    """
    job = {
        "product_name":   product["name"],
        "category":       product["category"],
        "image_url":      product.get("image_url", ""),
        "kling_prompt":   ai_content.get("kling_prompt", ""),
        "video_script":   ai_content.get("video_script", ""),
        "caption":        ai_content.get("instagram_caption", ""),
        "created_at":     datetime.utcnow().isoformat(),
        "status":         "queued",
    }

    queue_file = "video_queue.jsonl"
    with open(queue_file, "a") as f:
        f.write(json.dumps(job) + "\n")

    print(f"  Video queued: {product['name']}")
    return job

# ── STEP 6: POST TO INSTAGRAM VIA BUFFER ─────────────────────────────────────

def post_to_buffer(caption: str, video_url: str = None, image_url: str = None):
    """
    Schedules a post to Instagram via Buffer API.
    Replace video_url with your rendered video once Kling/CapCut produces it.
    """
    if not BUFFER_TOKEN:
        print("  Buffer token not set — skipping post")
        return

    payload = {
        "profile_ids": [BUFFER_PROFILE_ID],
        "text":        caption,
        "scheduled_at": "next_best_time",  # Buffer picks optimal time
    }
    if video_url:
        payload["media"] = {"video": video_url}
    elif image_url:
        payload["media"] = {"photo": image_url}

    resp = requests.post(
        "https://api.bufferapp.com/1/updates/create.json",
        headers={"Authorization": f"Bearer {BUFFER_TOKEN}"},
        json=payload,
        timeout=15,
    )
    print(f"  Buffer response: {resp.status_code}")
    return resp.json()

# ── MAIN DAILY RUN ────────────────────────────────────────────────────────────

def run_daily_agent():
    print(f"\n{'='*50}")
    print(f"Beauty Agent running — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}")

    all_results = []

    for category in CATEGORIES:
        print(f"\n[{category.upper()}]")

        # 1. Find top products
        print("  Fetching trending products...")
        try:
            products = find_trending_products(category)
        except Exception as e:
            print(f"  Error fetching products: {e}")
            continue

        # Process top 3 per category per day (rate limit protection)
        for product in products[:3]:
            print(f"  Processing: {product['name'][:50]}")

            # 2. AI review + scripts
            try:
                ai_content = generate_review_summary(product)
            except Exception as e:
                print(f"  AI error: {e}")
                continue

            # 3. Build affiliate links
            affiliate_links = build_affiliate_links(product["name"], product.get("brand", ""))
            # Use direct Amazon URL if we have an ASIN
            if product.get("amazon_url"):
                affiliate_links["amazon"] = product["amazon_url"]

            # 4. Queue video
            queue_video_creation(product, ai_content)

            # 6. Post a teaser image now (video posts after rendering)
            if product.get("image_url"):
                post_to_buffer(
                    caption=ai_content.get("instagram_caption", ""),
                    image_url=product["image_url"]
                )

            all_results.append({
                "product": product["name"],
                "category": category,
                "affiliate_links": affiliate_links,
            })

            time.sleep(2)  # Polite delay between API calls

    # Download all images locally so they never expire
    print("\nDownloading product images...")
    all_results = download_all_images(all_results)

    # Save daily run summary
    summary_file = f"runs/run_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    os.makedirs("runs", exist_ok=True)
    with open(summary_file, "w") as f:
        json.dump(all_results, f, indent=2)

    # Merge new products with existing - NEVER overwrite existing images
    print("\nUpdating products.json for nacre.beauty...")
    import json as _json, os as _os
    existing = []
    if _os.path.exists("products.json"):
        with open("products.json") as _f:
            existing = _json.load(_f)
    # Index existing by name to preserve images
    existing_map = {p["name"]: p for p in existing}
    for result in all_results:
        name = result.get("product", "")
        if name in existing_map:
            # Preserve existing image data
            result["image_url"] = existing_map[name].get("image_url", result.get("image_url",""))
            result["extra_images"] = existing_map[name].get("extra_images", [])
            result["video_url"] = existing_map[name].get("video_url", "")
    build_products_json()

    # Auto commit and push everything live to nacre.beauty
    print("\nPushing to nacre.beauty...")
    auto_git_push()

    print(f"\nDone. {len(all_results)} products live on nacre.beauty")
    print(f"Summary: {summary_file}")

# ── SCHEDULER ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Run once immediately
    run_daily_agent()

    # Then schedule daily at 6 AM
    schedule.every().day.at("06:00").do(run_daily_agent)

    print("\nAgent scheduled. Running daily at 06:00 AM.")
