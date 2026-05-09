# Beauty Affiliate AI Agent — Setup Guide

Fully automated pipeline: finds top products → generates pages → creates videos → posts to Instagram.

## Files

| File | What it does |
|---|---|
| `beauty_agent.py` | Main agent — runs daily, finds products, generates pages, queues videos |
| `video_processor.py` | Picks up queued videos, sends to Kling/Runway, posts via Buffer |
| `.env.example` | Copy to `.env` and fill in your API keys |

## Quick start (15 minutes)

### 1. Install dependencies
```bash
pip install anthropic requests python-dotenv schedule
```

### 2. Set up your keys
```bash
cp .env.example .env
# Edit .env with your actual keys
```

### 3. Run the agent
```bash
# Terminal 1 — main agent (runs daily at 6 AM)
python beauty_agent.py

# Terminal 2 — video processor (run after agent queues jobs)
python video_processor.py
```

### 4. Host your product pages free
The agent saves HTML pages to `docs/` folder.
Push to GitHub → enable GitHub Pages → your product pages are live at:
`https://yourusername.github.io/beauty/skincare/product-name.html`

Put the GitHub Pages root URL in your Instagram bio.

---

## Affiliate programs to sign up for (do this first)

| Retailer | Program | Commission | Sign up |
|---|---|---|---|
| Amazon | Amazon Associates | 4–10% | affiliate-program.amazon.com |
| Sephora | Rakuten Advertising | up to 10% | rakutenadvertising.com |
| eBay | eBay Partner Network | up to 4% | partnernetwork.ebay.com |
| Ulta | Impact | 2–5% | impact.com → search Ulta |
| Glossier | ShareASale | up to 15% | shareasale.com |
| Tarte | ShareASale | 8–12% | shareasale.com → search Tarte |
| ILIA Beauty | Direct | 10% + 30-day cookie | iliabeauty.com/pages/affiliate |

---

## Video creation tools

The agent queues video jobs. Use one of:

**Kling AI** (best quality, free tier available)
- klingai.com — image-to-video, 5-sec clips
- API access: waitlist at klingai.com/api

**Runway Gen-3** (best fallback, pay per second)
- runwayml.com — ~$0.05/second
- API docs: docs.runwayml.com

**Manual alternative (no API)**
1. Open CapCut
2. Import your AI model photo
3. Add "AI Smart Cutout" + motion effect
4. Layer product footage from brand media kits
5. Add text from the `video_script` in `video_queue.jsonl`
6. Export 9:16, 1080×1920

---

## Product page hosting (free options)

| Option | Setup time | Custom domain |
|---|---|---|
| GitHub Pages | 5 min | Yes (free) |
| Netlify | 5 min | Yes (free) |
| Cloudflare Pages | 10 min | Yes (free) |

All three are free and auto-deploy when you push the `docs/` folder.

---

## Categories tracked

The agent runs across 8 categories daily:
- Skincare (serums, SPF, moisturisers)
- Makeup (foundation, lip, eye)
- Fragrance (eau de parfum, mists)
- Haircare (serums, masks, tools)
- Body care (scrubs, oils, SPF body)
- Nail care (gel, press-on, care)
- Beauty tools (LED, microneedle, brush)
- Wellness beauty (supplements, gua sha)

To add categories: edit `CATEGORIES` list in `beauty_agent.py`.

---

## Revenue tracking

Each affiliate program has its own dashboard:
- Amazon: affiliate-program.amazon.com → Reports
- Sephora/Rakuten: rakutenadvertising.com → Reports
- eBay: partnernetwork.ebay.com → Reports
- Impact (Ulta): app.impact.com → Reports

For a unified view, use **Affilimate** or **Post Affiliate Pro** to aggregate all dashboards into one.

---

## Scaling up

Once generating consistently:
1. Increase `products[:3]` to `products[:10]` to process all 10 per category
2. Add `schedule.every().day.at("18:00").do(run_daily_agent)` for a second daily run
3. Connect a Telegram/Slack webhook for daily earnings reports
4. Feed top-converting products back into the agent's priority list
