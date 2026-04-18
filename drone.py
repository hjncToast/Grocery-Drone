import requests
import time
import os
from statistics import mode, median, mean 
from datetime import datetime, timedelta
import json
import sys

from dotenv import load_dotenv
load_dotenv()

TEST_MODE = os.environ.get("TEST_MODE", "false").lower() == "true"
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_TEST_URL" if TEST_MODE else "DISCORD_WEBHOOK_URL")
if not WEBHOOK_URL:
    raise ValueError("No DISCORD_WEBHOOK_URL set in .env")

# do this for testing
# TEST_MODE=true python3 drone.py summary

CACHE_FILE = "price_cache.json"
NAME_LEN = 30
SUMMARY_HEADER = f" ⚫`{'Item':<{NAME_LEN}} | {'Curr':>6} | {'Prev':>6} | {'Wght':>6}`"


def save_to_cache(item, current, previous, stat_weighted):
    cache = {}
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f:
            cache = json.load(f)
    cache[item['id']] = {
        "name": item['name'],
        "store": item['store'],
        "genre": item['genre'],
        "current": current,
        "previous": previous,
        "weighted": stat_weighted,
        "scanned_at": datetime.now().isoformat()
    }
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=2)

def load_watchlist(filepath="list.txt"):
    watchlist = []
    current_genre = "GENERAL"
    
    if not os.path.exists(filepath):
        print(f"⚠️ {filepath} not found. Creating a blank one.")
        with open(filepath, 'w') as f: f.write("(GENERAL)\n000, coles, example item")
        return []

    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line: continue
            # if line is like (chocolate), update the current genre
            if line.startswith('(') and line.endswith(')'):
                current_genre = line.strip('()').upper()
                continue
            # split by comma and clean up whitespace
            parts = [p.strip() for p in line.split(',')]
            if len(parts) == 3:
                watchlist.append({
                    "id": parts[0], "store": parts[1].lower(), 
                    "name": parts[2], "genre": current_genre
                })
    return watchlist

# initialise list from file
WATCHLIST = load_watchlist("list.txt")


def get_verdict(curr, mo, we, mn, month_avg, all_time_min):
    """Statistical Verdict Engine"""
    if curr <= (mo * 0.51): return "🚨🤪🚨🤪 **M A S S I V E     D E A L : 50% OFF**"
    if curr <= (all_time_min * 1.03): return "💎 ALL-TIME LOW (Crusade the stores)"
    if curr > month_avg and curr < mo: return "⚠️ SEASONAL TRAP (Recent avg was lower)"
    if curr < mo and curr <= we:      return "🛒 BUY NOW (Solid Sale)"
    if curr < mn:                     return "🔑🔑 **...regular price keys...**"
    if curr > mo:                     return "❌ WAIT (Price Spike)"
    return "😴 NO RUSH (Regular Price)"


def calculate_weighted_average(prices):
    if not prices: return 0
    weights = list(range(1, len(prices) + 1))
    weighted_sum = sum(p * w for p, w in zip(prices, weights))
    return weighted_sum / sum(weights)


def post_summary(summary_list, scanned_at=None):
    header = "**Price Summary**"
    if scanned_at:
        header += f" *(last scan: {scanned_at[:10]})*"
    final_summary = header + "\n" + "\n".join(summary_list)
    
    chunks = []
    current_chunk = ""
    for line in final_summary.split("\n"):
        if len(current_chunk) + len(line) + 1 > 1900:
            chunks.append(current_chunk)
            current_chunk = line
        else:
            current_chunk += ("\n" if current_chunk else "") + line
    if current_chunk:
        chunks.append(current_chunk)

    for chunk in chunks:
        requests.post(WEBHOOK_URL, json={"username": "Summary Drone", "content": chunk})


def parse_last_update(history):
    if not history:
        return "Unknown", "Unknown"
    try:
        dt_obj = datetime.fromisoformat(history[-1]['date'])
        return dt_obj.strftime("%d/%m/%Y"), dt_obj.strftime("%H:%M:%S")
    except ValueError:
        return history[-1]['date'], "00:00:00"

def get_month_avg(history, today_dt, fallback):
    thirty_days_ago = today_dt - timedelta(days=30)
    recent = []
    for h in history:
        try:
            if datetime.strptime(h['date'], "%d/%m/%Y") >= thirty_days_ago:
                recent.append(h['price'])
        except:
            continue
    return mean(recent) if recent else fallback


def run_drone():
    print("🚀 Drone engaged. ahlelele ahlelas...")
    
    today_dt = datetime.now()
    header_payload = {
        "username": "Grocery Drone",
        "content": f"━━━ 📦 **WEEKLY SCAN: {today_dt.strftime('%d/%m/%y')}** ━━━\n*Drone engaged. ahlelele ahlelas...*"
    }
    requests.post(WEBHOOK_URL, json=header_payload)

    summary_list = [
                    SUMMARY_HEADER
        ]
    last_genre = None # keep track of the genre we just processed



    for item in WATCHLIST:

        # genre break logic
        if item['genre'] != last_genre:
            genre_msg = f"## 🟦🟦🟦🟦🟦 {item['genre']} "
            requests.post(WEBHOOK_URL, json={"username": "Grocery Drone", "content": genre_msg})
            last_genre = item['genre']

        # build the correct API link for scanning
        if item['store'] == "coles":
            api_url = f"https://data-holdings-fastapi-lp22d.ondigitalocean.app/coles/product_search/{item['id']}"
            store_url = f"https://www.coles.com.au/product/{item['id']}"
            store_emoji = "🔴"
        else:
            api_url = f"https://data-holdings-fastapi-lp22d.ondigitalocean.app/woolworths/product_search/{item['id']}"
            store_url = f"https://www.woolworths.com.au/shop/productdetails/{item['id']}"
            store_emoji = "🟢"

        try:
            response = requests.get(api_url, headers={"User-Agent": "Mozilla/5.0"})
            if response.status_code == 200:
                data = response.json()
                current = data.get('current_price', 0)
                history = data.get('priceHistory', [])
                prices = [h['price'] for h in history if 'price' in h]

                # basic Stats
                stat_mode = mode(prices) if prices else current
                stat_median = median(prices) if prices else current
                stat_mean = mean(prices) if prices else current
                
                stat_weighted = calculate_weighted_average(prices)
                all_time_min = min(prices)
                
                # Previous Price
                previous = history[-2]['price'] if len(history) >= 2 else current
                      # last_update_date = history[-1]['date'] if history else "Unknown"

                # Date formatting
                last_update_date, last_update_time = parse_last_update(history)

                #30=day average
                month_avg = get_month_avg(history, today_dt, stat_mean)

                save_to_cache(item, current, previous, stat_weighted)

                # add to summary list
                # <30 = Left align, 30 spaces | >6.2f = Right align, 6 spaces total
                clean_name = item['name'][:NAME_LEN]
                table_text = f"{clean_name:<{NAME_LEN}} | ${current:>5.2f} | ${previous:>5.2f} | ${stat_weighted:>5.2f}"
                full_pill_line = f"{store_emoji} `{table_text}`"
                
                summary_list.append(full_pill_line)

                verdict = get_verdict(current, stat_mode, stat_weighted, stat_mean, month_avg, all_time_min)

                # terminal output
                print(f"[{item['store'].upper()}] {item['name']}: ${current:.2f}")

                # discord output
                send_to_discord(item['name'], item['store'], current, previous, stat_mode, stat_median, stat_mean, stat_weighted, month_avg, all_time_min, verdict, store_url, last_update_date, last_update_time)

        except Exception as e:
            print(f"⚠️ Error scanning {item['name']}: {e}")
        
        time.sleep(1)


    if summary_list:
        post_summary(summary_list)

def run_summary():
    if not os.path.exists(CACHE_FILE):
        print("No cache found. Run the full drone first.")
        return

    with open(CACHE_FILE, 'r') as f:
        cache = json.load(f)

    summary_list = [SUMMARY_HEADER]

    for item in WATCHLIST:
        entry = cache.get(item['id'])
        if not entry:
            continue

        store_emoji = "🔴" if entry['store'] == "coles" else "🟢"
        clean_name = entry['name'][:NAME_LEN]
        row = f"{clean_name:<{NAME_LEN}} | ${entry['current']:>5.2f} | ${entry['previous']:>5.2f} | ${entry['weighted']:>5.2f}"
        summary_list.append(f"{store_emoji} `{row}`")

    scanned_at = list(cache.values())[-1].get('scanned_at', 'Unknown')
    post_summary(summary_list, scanned_at)


def send_to_discord(name, store, current, previous, mode, med, mean, weight, m_avg, a_min, verdict, store_url, last_update_date, last_update_time):

    def get_p(ref, curr):
        return ((ref - curr) / ref * 100) if ref > 0 else 0
    
    trend = "⬆️" if current > previous else "⬇️" if current < previous else "➡️"
    store_emoji = "🔴" if store == "coles" else "🟢"

    msg = (
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        f"### - {name}\n"
        f"now: **💰 ${current:.2f}** {trend} was: ${previous:.2f})\n"
        f"{verdict}\n"
        f"*Data updated: {last_update_date}* - - - - - - {last_update_time}\n"
        f"```\n"
        f"Analysis (vs Now):\n"
        f"• Previous Price: ${previous:.2f} -> {get_p(previous, current):>3.0f}% OFF\n"
        f"• Shelf (Mode):   ${mode:.2f} -> {get_p(mode, current):>3.0f}% OFF\n"
        f"• Mid (Median):   ${med:.2f} -> {get_p(med, current):>3.0f}% OFF\n"
        f"• Avg (Global):   ${mean:.2f} -> {get_p(mean, current):>3.0f}% OFF\n"
        f"• Avg (30 day):   ${m_avg:>.2f} -> {get_p(m_avg, current):>3.0f}% OFF\n"
        f"• Trend (Weight): ${weight:.2f} -> {get_p(weight, current):>3.0f}% OFF\n"
        f"• All-Time Low:   ${a_min:>.2f} -> {get_p(a_min, current):>3.0f}% OFF\n"
        f"```"
        f"{store_emoji} `{store}` [Store Link]({store_url})\n"
        f"\n"
        
    )
    payload = {"username": "Grocery Drone", "content": msg}
    requests.post(WEBHOOK_URL, json=payload)

if __name__ == "__main__":
    if "summary" in sys.argv:
        run_summary()
    else:
        run_drone()