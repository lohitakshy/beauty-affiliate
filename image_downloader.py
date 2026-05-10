"""
image_downloader.py
Downloads product images from URLs and saves them locally.
Images are stored in /images/ folder and pushed to GitHub Pages.
Run: pip install requests Pillow
"""

import os, re, hashlib, time
import requests
from pathlib import Path

IMAGES_DIR = "images"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def slugify(text: str) -> str:
    """Convert text to a safe filename."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return text[:50]

def download_image(url: str, product_name: str, category: str) -> str | None:
    """
    Downloads image from URL and saves locally.
    Returns the local relative path like 'images/skincare/dermalogica.jpg'
    or None if download fails.
    """
    if not url or not url.startswith('http'):
        return None

    # Create category subfolder
    cat_slug = slugify(category)
    save_dir = Path(IMAGES_DIR) / cat_slug
    save_dir.mkdir(parents=True, exist_ok=True)

    # Create filename from product name + URL hash (to avoid duplicates)
    name_slug = slugify(product_name)
    url_hash  = hashlib.md5(url.encode()).hexdigest()[:6]
    filename  = f"{name_slug}-{url_hash}.jpg"
    filepath  = save_dir / filename
    rel_path  = f"images/{cat_slug}/{filename}"

    # Skip if already downloaded
    if filepath.exists() and filepath.stat().st_size > 1000:
        print(f"    Image cached: {rel_path}")
        return rel_path

    # Download
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, stream=True)
        resp.raise_for_status()

        content_type = resp.headers.get('content-type', '')
        if 'image' not in content_type and 'octet-stream' not in content_type:
            print(f"    Not an image: {content_type}")
            return None

        with open(filepath, 'wb') as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)

        size = filepath.stat().st_size
        if size < 500:
            filepath.unlink()
            return None

        print(f"    Image saved: {rel_path} ({size//1024}KB)")
        return rel_path

    except Exception as e:
        print(f"    Image download failed: {e}")
        if filepath.exists():
            filepath.unlink()
        return None


def download_all_images(products: list[dict]) -> list[dict]:
    """
    Takes a list of products, downloads all images,
    and updates each product's image_url to the local path.
    Returns updated products list.
    """
    print(f"\n  Downloading images for {len(products)} products...")
    updated = []

    for i, product in enumerate(products):
        original_url = product.get('image_url', '')
        name         = product.get('name', f'product-{i}')
        category     = product.get('category', 'beauty')

        if original_url:
            local_path = download_image(original_url, name, category)
            if local_path:
                product = {**product,
                    'image_url':      local_path,     # local path for site
                    'image_url_orig': original_url,   # keep original for reference
                }
            # If download failed, keep original URL as fallback
        
        updated.append(product)
        time.sleep(0.3)  # polite delay

    downloaded = sum(1 for p in updated if p.get('image_url','').startswith('images/'))
    print(f"  Images: {downloaded}/{len(products)} saved locally")
    return updated


def auto_git_push():
    """
    Commits and pushes new images to GitHub so they go live on nacre.beauty.
    Called automatically after each agent run.
    """
    import subprocess

    cmds = [
        ["git", "add", "images/", "products.json", "docs/"],
        ["git", "commit", "-m", f"auto: update products and images"],
        ["git", "push", "origin", "main"],
    ]

    for cmd in cmds:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            # "nothing to commit" is fine
            if "nothing to commit" in result.stdout or "nothing to commit" in result.stderr:
                print(f"  Git: nothing new to push")
                break
            print(f"  Git warning: {result.stderr.strip()[:100]}")
        else:
            print(f"  Git: {result.stdout.strip()[:80]}")


if __name__ == "__main__":
    # Test with a sample image
    test_url = "https://via.placeholder.com/400x400.jpg"
    result = download_image(test_url, "Test Product", "skincare")
    print(f"Test result: {result}")
