"""
Generates products.json from the agent's run history.
This file powers the nacre.beauty homepage product grid.
Run automatically after beauty_agent.py completes.
"""

import os, json, glob
from datetime import datetime

RUNS_DIR  = "runs"
DOCS_DIR  = "docs"
OUT_FILE  = "products.json"

def build_products_json():
    products = []

    # Load all run summaries
    run_files = sorted(glob.glob(f"{RUNS_DIR}/run_*.json"), reverse=True)

    seen = set()

    for run_file in run_files[:7]:  # Last 7 days of runs
        try:
            with open(run_file) as f:
                run_data = json.load(f)

            for item in run_data:
                name = item.get("product", "")
                if name in seen:
                    continue
                seen.add(name)

                category = item.get("category", "").replace(" ", "_")

                # Build review page URL
                slug = name.lower().replace(" ", "-")[:40]
                review_url = f"https://nacre.beauty/docs/{category}/{slug}.html"

                # Build affiliate URLs
                affiliate_links = item.get("affiliate_links", {})
                primary_url = (
                    affiliate_links.get("sephora") or
                    affiliate_links.get("amazon") or
                    affiliate_links.get("glossier") or
                    review_url
                )

                products.append({
                    "name":          name,
                    "category":      category,
                    "brand":         item.get("brand", ""),
                    "rating":        item.get("rating", 4.5),
                    "reviews":       item.get("reviews", ""),
                    "image_url":     item.get("image_url", ""),
                    "affiliate_url": primary_url,
                    "review_url":    review_url,
                    "amazon_url":    affiliate_links.get("amazon", ""),
                    "sephora_url":   affiliate_links.get("sephora", ""),
                    "ebay_url":      affiliate_links.get("ebay", ""),
                    "date_added":    item.get("date", datetime.now().strftime("%Y-%m-%d")),
                })

        except Exception as e:
            print(f"  Error reading {run_file}: {e}")
            continue

    # Sort by date, newest first
    products.sort(key=lambda x: x.get("date_added", ""), reverse=True)

    with open(OUT_FILE, "w") as f:
        json.dump(products, f, indent=2)

    print(f"products.json updated — {len(products)} products")
    return products

if __name__ == "__main__":
    build_products_json()
