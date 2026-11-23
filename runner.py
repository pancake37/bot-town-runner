import json
import time
import urllib.request
import urllib.error
import os
import sys
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

BASE_URL = "https://www.botvillage.town/api/v0"
MAX_RUN_SECONDS = 330 * 60  # ~5.5 hours
TASK_DURATION_SECONDS = 185  # Server rule: >= 3 minutes

def log(msg):
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{ts}] {msg}", flush=True)

def load_team():
    team_raw = os.environ.get("BOTTOWN_TEAM")
    if team_raw:
        try:
            return json.loads(team_raw)
        except Exception as e:
            log(f"Failed to parse BOTTOWN_TEAM: {e}")
    
    # Fallback to single token
    token = os.environ.get("BOTTOWN_TOKEN")
    if token:
        return [{"name": "Antigravity", "handle": "antigravity", "token": token, "category": "code"}]
    
    log("FATAL: No BOTTOWN_TEAM or BOTTOWN_TOKEN provided!")
    sys.exit(1)

def api_request(endpoint, token, method="GET", body=None):
    url = f"{BASE_URL}{endpoint}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
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

def bot_start(bot):
    category = bot.get("category", "code")
    res = api_request("/signals", bot["token"], method="POST", body={"status": "start", "category": category})
    return bot["name"], res

def bot_end(bot):
    res = api_request("/signals", bot["token"], method="POST", body={"status": "end"})
    return bot["name"], res

def main():
    team = load_team()
    log(f"=== Bot Town 5-in-1 Cloud Syndicate started ({len(team)} agents) ===")
    for b in team:
        log(f" - {b['name']} ({b['handle']}) | Category: {b.get('category')}")
        
    start_time = time.time()
    
    while True:
        elapsed = time.time() - start_time
        if elapsed > MAX_RUN_SECONDS:
            log(f"Max run time of {MAX_RUN_SECONDS}s reached. Exiting cleanly for next chained run.")
            break
            
        try:
            # 1. Start all bots in parallel
            with ThreadPoolExecutor(max_workers=5) as executor:
                start_results = list(executor.map(bot_start, team))
                
            for name, res in start_results:
                log(f"[{name}] Signal START -> Status: {res.get('status', res)}")
                
            # 2. Wait 185 seconds together
            time.sleep(TASK_DURATION_SECONDS)
            
            # 3. End all bots in parallel
            with ThreadPoolExecutor(max_workers=5) as executor:
                end_results = list(executor.map(bot_end, team))
                
            for name, res in end_results:
                counted = res.get("counted", False)
                earned = res.get("earned", 0)
                coins = res.get("coins", 0)
                tasks = res.get("tasks", 0)
                rank = res.get("rank", "Unknown")
                reason = res.get("reason", "")
                log(f"[{name}] Signal END -> Counted: {counted} ({reason}) | Earned: +{earned} | Coins: {coins} | Tasks: {tasks} | Rank: {rank}")
                
            # 4. Small breather before next cycle
            time.sleep(5)
            
        except Exception as e:
            log(f"Unexpected loop exception: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
