# Grocery Drone
 
A Python bot that tracks supermarket prices across Coles and Woolworths and delivers a weekly statistical analysis report to Discord — automatically, every Thursday via GitHub Actions. (Coles and Woolworths update every Wednesday, so a one day buffer... )
 
## What it does
 
It watches a configurable list of products and, for each one, pulls historical pricing data and runs a statistical breakdown to determine whether the current price is actually worth acting on. Results are posted to a Discord channel with a plain-English verdict (with a bit of silliness) for each item.
 
The verdict compares the current price against the mode (typical shelf price), a recency-weighted trend average, the 30-day average, and the all-time recorded low — so you can tell the difference between a genuine sale and a cosmetic discount off an inflated baseline.
 
## Tech
 
- **Python** — data fetching, statistical analysis (`statistics` module), and Discord webhook delivery
- **GitHub Actions** — scheduled weekly execution via cron, no server required
- **REST APIs** — live product and price history data from Coles and Woolworths
- **Discord Webhooks** — formatted report delivery
 
## Setup
 
1. Clone the repo and add your products to `RAW_DATA` in `drone.py` using the format:
   ```
   ProductID, store, Product Name
   ```
2. Add your Discord webhook URL as a GitHub Actions secret named `DISCORD_WEBHOOK_URL`
3. The workflow runs every Thursday at 8am AEDT — or trigger it manually from the Actions tab
