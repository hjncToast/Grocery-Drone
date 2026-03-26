import requests
import time
import os
from statistics import mode, median, mean 
from datetime import datetime, timedelta


# item input area
# Format: "ProductID, Store, Name" (One per line)
RAW_DATA = """
(nut milk)
1260754, coles, so good almond milk

(chocolate)
9524521, coles, lindt 85%
201687, wool, lindt 85%
935634, wool, Woolworths 85% Belgian Dark Chocolate 100g

(supplements)
4805443, coles, Swisse Fish Oil 2000mg 200 pills
5325476, coles, Ultralife Vitamin D | 400 pack
4941770, coles, Blackmores Fish Oil 1000mg Omega-3 Capsules | 400 pack


(vegetables)
3627805, coles, Coles I'm Perfect Avocados | 1kg
3479297, coles, Coles Avocados Prepacked | 5 Pack

(super veggie stuff)
5833557, coles, La Espanola Extra Virgin Olive Oil | 1L

(legumes)
353521, coles, McKenzie's Split Green Peas | 500g
130017, coles, McKenzie's Split Yellow Peas | 500g
8192787, coles, Gaganis Premium Yellow Split Peas | 1kg
753948, wool, Katoomba Ingredients Yellow Split Peas 1kg
6288116, coles, McKenzie's French Style Black Lentils | 375g

(fruits)
8133391, coles, Coles White Seedless Grapes | approx. 1kg

(poisons [You'll never read this, right Harrison?])

"""

def build_watchlist(raw_text):
    watchlist = []
    current_genre = "General"
    for line in raw_text.strip().split('\n'):
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
                "id": parts[0],
                "store": parts[1].lower(),
                "name": parts[2],
                "genre": current_genre # attach genre to the item
            })
    return watchlist

WATCHLIST = build_watchlist(RAW_DATA)

# webhook 
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")



def get_verdict(curr, mo, we, mn, month_avg, all_time_min):
    """Statistical Verdict Engine"""
    if curr <= (mo * 0.51): return "🚨🤪🚨🤪 **M A S S I V E     D E A L : 50% OFF**"
    if curr <= (all_time_min * 1.03): return "💎 ALL-TIME LOW (Crusade the stores)"
    if curr > month_avg and curr < mo: return "⚠️ SEASONAL TRAP (Recent avg was lower)"
    if curr < mo and curr <= we:      return "🛒 BUY NOW (Solid Sale)"
    if curr < mn:                     return "🔑🔑 **...regular price keys...**"
    if curr > mo:                     return "❌ WAIT (Price Spike)"
    return "😴 NO RUSH (Regular Price)"



def run_drone():
    print("🚀 Drone engaged. ahlelele ahlelas...")
    
    today_dt = datetime.now()
    header_payload = {
        "username": "Grocery Drone",
        "content": f"━━━ 📦 **WEEKLY SCAN: {today_dt.strftime('%d/%m/%y')}** ━━━\n*Drone engaged. ahlelele ahlelas...*"
    }
    requests.post(WEBHOOK_URL, json=header_payload)

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
        else:
            api_url = f"https://data-holdings-fastapi-lp22d.ondigitalocean.app/woolworths/product_search/{item['id']}"
            store_url = f"https://www.woolworths.com.au/shop/productdetails/{item['id']}"

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
                
                # Weighted Average (Recent Bias)
                weights = list(range(1, len(prices) + 1))
                stat_weighted = sum(p * w for p, w in zip(prices, weights)) / sum(weights) if prices else current
                
                # Previous Price
                previous = history[-2]['price'] if len(history) >= 2 else current


                # last_update_date = history[-1]['date'] if history else "Unknown"

                if history:
                    raw_date = history[-1]['date']
                    try:

                        dt_obj = datetime.fromisoformat(raw_date)
                        last_update_date = dt_obj.strftime("%d/%m/%Y")
                        last_update_time = dt_obj.strftime("%H:%M:%S")
                    except ValueError:
                        # fallback if the API uses the old DD/MM/YYYY format
                        last_update_date = raw_date
                        last_update_time = "00:00:00"
                else:
                    last_update_date = "Unknown"
                    last_update_time = "Unknown"



                all_time_min = min(prices)
                

                thirty_days_ago = today_dt - timedelta(days=30)
                recent_prices = []
                for h in history:
                    try:
                        h_date = datetime.strptime(h['date'], "%d/%m/%Y")
                        if h_date >= thirty_days_ago:
                            recent_prices.append(h['price'])
                    except: continue
                
                month_avg = mean(recent_prices) if recent_prices else stat_mean


                verdict = get_verdict(current, stat_mode, stat_weighted, stat_mean, month_avg, all_time_min)

                # terminal output
                print(f"[{item['store'].upper()}] {item['name']}: ${current:.2f}")

                # discord output
                send_to_discord(item['name'], item['store'], current, previous, stat_mode, stat_median, stat_mean, stat_weighted, month_avg, all_time_min, verdict, store_url, last_update_date, last_update_time)

        except Exception as e:
            print(f"⚠️ Error scanning {item['name']}: {e}")
        
        time.sleep(1.5)


def calculate_weighted_average(prices):
    if not prices:
        return 0

    weights = list(range(1, len(prices) + 1))
    weighted_sum = sum(p * w for p, w in zip(prices, weights))
    return weighted_sum / sum(weights)


def send_to_discord(name, store, current, previous, mode, med, mean, weight, m_avg, a_min, verdict, store_url, last_update_date, last_update_time):
    today = datetime.now().strftime("%d/%m/%y")
    header = f"━━━ 📦 **WEEKLY SCAN** ({today}) ━━━"

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
    run_drone()