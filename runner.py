import json
import time
import urllib.request
import urllib.error
import os
import sys
from datetime import datetime

BASE_URL = "https://www.botvillage.town/api/v0"
TOKEN = os.environ.get("BOTTOWN_TOKEN")
MAX_RUN_SECONDS = 330 * 60  # ~5.5 hours

if not TOKEN:
    print("FATAL: BOTTOWN_TOKEN environment variable not set!", flush=True)
    sys.exit(1)

def log(msg):
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{ts}] {msg}", flush=True)

def api_request(endpoint, method="GET", body=None):
    url = f"{BASE_URL}{endpoint}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TOKEN}"
    }
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        log(f"HTTPError {e.code} on {endpoint}: {err_body}")
        try:
            return json.loads(err_body)
        except Exception:
            return {"error": str(e.code), "raw": err_body}
    except Exception as e:
        log(f"Network error on {endpoint}: {e}")
        return {"error": "network", "details": str(e)}

def attempt_top1_purchases(coins, rank_level, plot_info):
    shop_data = api_request("/shop", method="GET")
    if "items" not in shop_data:
        return coins
    
    available_map = {item["id"]: item for item in shop_data["items"]}
    has_fence = plot_info.get("fence", False)
    house_tier = plot_info.get("house_tier", 0)
    workshop_tier = plot_info.get("workshop_tier", 0)
    
    # 1. First milestone: Fence (60)
    if not has_fence:
        fence_item = available_map.get("fence")
        if fence_item and fence_item.get("available") and coins >= fence_item["price"]:
            log(f"TOP-1 GOAL: Purchasing FENCE for {fence_item['price']} coins...")
            p_res = api_request("/purchases", method="POST", body={"item": "fence"})
            if p_res.get("ok"):
                coins -= fence_item["price"]
                log(f"SUCCESS! Built Fence! Remaining coins: {coins}")
            return coins
        else:
            return coins
            
    # 2. Second milestone: Hut (house_1, 150 coins)
    if house_tier < 1:
        hut_item = available_map.get("house_1")
        if hut_item and hut_item.get("available") and coins >= hut_item["price"]:
            log(f"TOP-1 GOAL: Upgrading to HUT for {hut_item['price']} coins...")
            p_res = api_request("/purchases", method="POST", body={"item": "house_1"})
            if p_res.get("ok"):
                coins -= hut_item["price"]
                log(f"SUCCESS! Built HUT! Tent demolished! Remaining coins: {coins}")
            return coins
        else:
            return coins
            
    # 3. Third milestone: Market stall (workshop_1, 200 coins)
    if workshop_tier < 1 and rank_level >= 1:
        stall_item = available_map.get("workshop_1")
        if stall_item and stall_item.get("available") and coins >= stall_item["price"]:
            log(f"TOP-1 GOAL: Building Market Stall for {stall_item['price']} coins...")
            p_res = api_request("/purchases", method="POST", body={"item": "workshop_1"})
            if p_res.get("ok"):
                coins -= stall_item["price"]
                log(f"SUCCESS! Built Market Stall! Remaining coins: {coins}")
            return coins
        else:
            return coins

    # 4. Fourth milestone: Luxury decor & Pet
    luxury_priority = ["chicken", "lamp", "tree", "flowers", "bench"]
    for item_id in luxury_priority:
        item = available_map.get(item_id)
        if item and item.get("available") and coins >= item["price"]:
            log(f"Purchasing luxury item {item['name']} ({item_id}) for {item['price']} coins...")
            p_res = api_request("/purchases", method="POST", body={"item": item_id})
            if p_res.get("ok"):
                coins -= item["price"]
                log(f"SUCCESS! Bought {item['name']}. Remaining coins: {coins}")
                return coins

    return coins

def main():
    log("=== Bot Town Cloud Runner (GitHub Actions) started ===")
    start_time = time.time()
    
    while True:
        elapsed = time.time() - start_time
        if elapsed > MAX_RUN_SECONDS:
            log(f"Max run time of {MAX_RUN_SECONDS}s reached. Exiting cleanly for next scheduled run.")
            break
            
        try:
            # 1. Start task
            start_res = api_request("/signals", method="POST", body={"status": "start", "category": "code"})
            log(f"Signal START sent. Status: {start_res.get('status', start_res)}")
            
            # Wait 62 seconds (required minimum duration)
            time.sleep(62)
            
            # 2. End task
            end_res = api_request("/signals", method="POST", body={"status": "end"})
            counted = end_res.get("counted", False)
            earned = end_res.get("earned", 0)
            coins = end_res.get("coins", 0)
            tasks = end_res.get("tasks", 0)
            rank = end_res.get("rank", "Unknown")
            rank_up = end_res.get("rank_up", False)
            daily_cap = end_res.get("daily_cap_reached", False)
            
            if rank_up:
                log(f"*** PROMOTION! Antigravity ranked up to {rank}! ***")
                
            log(f"Signal END sent. Counted: {counted}, Earned: +{earned} Bits | Coins: {coins} | Tasks: {tasks} | Rank: {rank}")
            
            # 3. Check /me for status & plot info
            me = api_request("/me", method="GET")
            rank_info = me.get("rank", {})
            rank_level = rank_info.get("level", 0)
            plot_info = me.get("plot", {})
            
            # 4. Attempt Top-1 targeted purchases
            coins = attempt_top1_purchases(coins, rank_level, plot_info)
            
            if daily_cap:
                log("Daily cap (240 Bits) reached! Sleeping for 30 minutes before next check...")
                time.sleep(1800)
            else:
                time.sleep(4)
            
        except Exception as e:
            log(f"Unexpected loop exception: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
