"""
fetch_images.py
Automatically downloads images for all products missing them.
Uses Google Images via SerpAPI to find real product images.
Run: python fetch_images.py
"""
import json, os, re, hashlib, time, requests, subprocess
from pathlib import Path

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
IMAGES_DIR  = "images"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
    "Referer": "https://www.google.com/",
}

def slugify(text):
    text = str(text).lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return text[:50]

def fetch_product_images(product_name, brand, category, count=4):
    """Search Google Images via SerpAPI and return image URLs."""
    if not SERPAPI_KEY:
        print("  No SERPAPI_KEY found in environment")
        return []
    
    query = f"{brand} {product_name} product"
    try:
        resp = requests.get("https://serpapi.com/search", params={
            "engine":  "google_images",
            "q":       query,
            "api_key": SERPAPI_KEY,
            "num":     count,
            "safe":    "active",
        }, timeout=15)
        resp.raise_for_status()
        results = resp.json().get("images_results", [])
        return [r.get("original", "") for r in results[:count] if r.get("original")]
    except Exception as e:
        print(f"  SerpAPI error: {e}")
        return []

def download_one(url, filepath):
    """Download a single image to filepath."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, stream=True)
        resp.raise_for_status()
        if 'image' not in resp.headers.get('content-type', ''):
            return False
        with open(filepath, 'wb') as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
        size = os.path.getsize(filepath)
        if size < 1000:
            os.remove(filepath)
            return False
        return True
    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        return False

def process_product(product, idx):
    """Download images for one product, update its image_url."""
    name     = product.get('name', f'product-{idx}')
    brand    = product.get('brand', '')
    category = product.get('category', 'beauty').replace(' ', '_')
    
    save_dir = Path(IMAGES_DIR) / category
    save_dir.mkdir(parents=True, exist_ok=True)
    
    slug      = slugify(name)
    url_hash  = hashlib.md5(name.encode()).hexdigest()[:6]
    primary   = save_dir / f"{slug}-{url_hash}.jpg"
    rel_path  = f"images/{category}/{slug}-{url_hash}.jpg"
    
    # Already has local image
    if product.get('image_url', '').startswith('images/') and primary.exists():
        print(f"  ✅ Already has image: {name[:40]}")
        return product
    
    print(f"  Fetching images for: {name[:40]}")
    
    # Search for images
    image_urls = fetch_product_images(name, brand, category)
    if not image_urls:
        print(f"  ❌ No images found")
        return product
    
    # Try each URL until one downloads successfully
    downloaded = False
    for i, url in enumerate(image_urls):
        save_path = save_dir / f"{slug}-{url_hash}-{i}.jpg" if i > 0 else primary
        if download_one(url, save_path):
            if i == 0:
                product['image_url'] = rel_path
                product['image_url_orig'] = url
            print(f"  ✅ Image {i+1} saved")
            downloaded = True
            time.sleep(0.5)
        else:
            print(f"  ⚠️  Image {i+1} failed, trying next...")
    
    if not downloaded:
        print(f"  ❌ All images failed for {name[:40]}")
    
    return product

def main():
    # Load products
    with open('products.json') as f:
        products = json.load(f)
    
    missing = [p for p in products if not p.get('image_url')]
    print(f"Found {len(missing)} products missing images\n")
    
    updated = 0
    for i, product in enumerate(products):
        if product.get('image_url'):
            continue  # skip already has image
        products[i] = process_product(product, i)
        if products[i].get('image_url'):
            updated += 1
        time.sleep(1)  # polite delay
    
    # Save updated products.json
    with open('products.json', 'w') as f:
        json.dump(products, f, indent=2)
    
    print(f"\n✅ Done. {updated} products now have images.")
    
    # Push to GitHub
    print("\nPushing to GitHub...")
    cmds = [
        ["git", "add", "-A"],
        ["git", "commit", "-m", f"add product images: {updated} updated"],
        ["git", "push", "origin", "main"],
    ]
    for cmd in cmds:
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.stdout.strip():
            print(f"  {r.stdout.strip()[:80]}")
        if r.returncode != 0 and "nothing to commit" not in r.stderr:
            print(f"  Warning: {r.stderr.strip()[:80]}")

if __name__ == "__main__":
    main()
