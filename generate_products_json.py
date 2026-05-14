"""
Generates products.json from the agent's daily runs.
Uses direct Amazon CDN image URLs — no local images/ folder needed.
"""
import os, json, glob
from datetime import datetime

RUNS_DIR = "runs"
OUT_FILE = "products.json"

def build_products_json():
    products = []
    run_files = sorted(glob.glob(f"{RUNS_DIR}/run_*.json"), reverse=True)
    seen = set()

    for run_file in run_files[:7]:
        try:
            with open(run_file) as f:
                run_data = json.load(f)

            for item in run_data:
                name = item.get("product", "")
                if name in seen:
                    continue
                seen.add(name)

                category = item.get("category", "").replace(" ", "_")
                affiliate_links = item.get("affiliate_links", {})

                # Prefer direct Amazon URL with ASIN
                amazon_url = item.get("amazon_url") or affiliate_links.get("amazon", "")
                sephora_url = item.get("sephora_url") or affiliate_links.get("sephora", "")

                # Image: prefer local if downloaded, otherwise use original URL directly
                image_url = item.get("image_url", "")

                products.append({
                    "name":         name,
                    "category":     category,
                    "brand":        item.get("brand", ""),
                    "rating":       item.get("rating", 0),
                    "reviews":      item.get("reviews", 0),
                    "price":        item.get("price", ""),
                    "image_url":    image_url,
                    "amazon_url":   amazon_url,
                    "sephora_url":  sephora_url,
                    "affiliate_url": amazon_url or sephora_url,
                    "asin":         item.get("asin", ""),
                    "date_added":   item.get("date", datetime.now().strftime("%Y-%m-%d")),
                })

        except Exception as e:
            print(f"Error reading {run_file}: {e}")
            continue

    products.sort(key=lambda x: x.get("date_added", ""), reverse=True)

    with open(OUT_FILE, "w") as f:
        json.dump(products, f, indent=2)

    print(f"products.json updated — {len(products)} products")
    return products

if __name__ == "__main__":
    build_products_json()
