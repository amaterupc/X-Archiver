import json
import time
import os
import re
from playwright.sync_api import sync_playwright

def load_storage_state(path):
    if not os.path.exists(path):
        return None
    
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # If the file is a list (standard extension export), convert to storageState format
    if isinstance(data, list):
        print(f"Detected raw cookie list in {path}. Converting for Playwright...")
        new_cookies = []
        for c in data:
            new_c = {
                "name": c.get("name"),
                "value": c.get("value"),
                "domain": c.get("domain"),
                "path": c.get("path"),
                "httpOnly": c.get("httpOnly", False),
                "secure": c.get("secure", False),
                "sameSite": "None" if c.get("sameSite") == "no_restriction" else (c.get("sameSite", "Lax").capitalize() if c.get("sameSite") else "Lax")
            }
            if "expirationDate" in c:
                new_c["expires"] = c["expirationDate"]
            
            if new_c["sameSite"] not in ["Lax", "Strict", "None"]:
                new_c["sameSite"] = "Lax"
            new_cookies.append(new_c)
        
        return {"cookies": new_cookies, "origins": []}
    
    # Otherwise assume it's already in the correct dict format
    return data

def get_thread(url: str, headless: bool = True):
    """
    Fetches an X thread from the given URL.
    Returns a list of dictionaries containing tweet data.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        
        storage_path = os.path.join("data", "cookies.json")
        storage_state = load_storage_state(storage_path)
        
        if storage_state:
            print(f"Using storage state from {storage_path}")

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            viewport={"width": 1280, "height": 720},
            storage_state=storage_state
        )
        page = context.new_page()

        print(f"Navigating to {url}...")
        try:
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
        except Exception as e:
            print(f"Navigation error: {e}")
            # Try to proceed anyway, maybe some content loaded

        
        # Wait for the first tweet to appear
        try:
            page.wait_for_selector('article[data-testid="tweet"]', timeout=15000)
        except Exception as e:
            print(f"Error loading page or tweet not found: {e}")
            browser.close()
            return []

        # Identify the OP (Original Poster)
        # The first tweet is the root of the thread.
        first_tweet = page.query_selector('article[data-testid="tweet"]')
        if not first_tweet:
            print("No tweets found.")
            browser.close()
            return []
            
        # Extract OP handle
        user_link = first_tweet.query_selector('div[data-testid="User-Name"] a[href^="/"]')
        if user_link:
            op_handle = user_link.get_attribute("href").strip("/")
            print(f"OP Handle: {op_handle}")
        else:
            print("Could not determine OP handle.")
            browser.close()
            return []

        collected_tweets = []
        seen_ids = set()
        
        # Initial scrape
        # We need to scroll down to load more tweets in the thread
        last_height = page.evaluate("document.body.scrollHeight")
        attempts = 0
        max_attempts = 5 # Limit scrolling to avoid infinite loops or getting too much unrelated stuff

        while True:
            # Get all visible tweets
            all_visible_tweets = page.query_selector_all('article[data-testid="tweet"]')
            
            # Filter matches to avoid nested articles (quotes) being treated as separate thread items
            tweets = []
            for t in all_visible_tweets:
                is_nested = t.evaluate("el => el.parentElement.closest('article[data-testid=\"tweet\"]') !== null")
                if not is_nested:
                    tweets.append(t)
            
            for tweet in tweets:
                 # Helper to get text efficiently
                try:
                    text_div = tweet.query_selector('div[data-testid="tweetText"]')
                    text = text_div.inner_text() if text_div else ""
                    
                    # Get Time/ID
                    time_el = tweet.query_selector('div[data-testid="User-Name"] time')
                    if not time_el:
                        time_el = tweet.query_selector('time')
                    timestamp = time_el.get_attribute("datetime") if time_el else ""
                    
                    # Find all links to statuses
                    links = tweet.query_selector_all('a[href*="/status/"]')
                    tweet_url = ""
                    for link in links:
                        href = link.get_attribute("href") or ""
                        is_inside_quote = link.evaluate("el => el.closest('[data-testid=\"quoteTweet\"]') !== null")
                        if not is_inside_quote:
                             tweet_url = href
                             if f"/{op_handle}/status/" in href:
                                 break
                    
                    # Better ID extraction to handle /photo/N or /video/N
                    tweet_id = None
                    if tweet_url:
                        match = re.search(r'/status/(\d+)', tweet_url)
                        if match:
                            tweet_id = match.group(1)
                    
                    # Critical Fix: For the first tweet on the page, the ID in the URL is the correct one 
                    # even if we accidentally picked up a quoted tweet's ID or if there's no permalink.
                    if not collected_tweets:
                        match_url = re.search(r'/status/(\d+)', page.url)
                        if match_url:
                            tweet_id = match_url.group(1)
                            tweet_url = f"/{op_handle}/status/{tweet_id}"
                    
                    if not tweet_id:
                        time_el = tweet.query_selector('time')
                        timestamp = time_el.get_attribute("datetime") if time_el else ""
                        tweet_id = f"{timestamp}-{text[:10]}"
                    else:
                        time_el = tweet.query_selector('time')
                        timestamp = time_el.get_attribute("datetime") if time_el else ""
                    
                    if tweet_id in seen_ids:
                        continue
                        
                    # Check if this tweet belongs to OP
                    tweet_user_link = tweet.query_selector('div[data-testid="User-Name"] a[href^="/"]')
                    tweet_handle = tweet_user_link.get_attribute("href").strip("/") if tweet_user_link else ""
                    
                    if tweet_handle == op_handle:
                        # Get images
                        images = []
                        img_elements = tweet.query_selector_all('img[src*="pbs.twimg.com/media"]')
                        for img in img_elements:
                            src = img.get_attribute("src")
                            if src:
                                images.append(src)
                        
                        # Check for video
                        video_player = tweet.query_selector('div[data-testid="videoPlayer"]')
                        has_video = video_player is not None
                        
                        collected_tweets.append({
                            "id": tweet_id,
                            "text": text,
                            "timestamp": timestamp,
                            "images": images,
                            "url": tweet_url,
                            "has_video": has_video
                        })
                        seen_ids.add(tweet_id)
                        
                except Exception as e:
                    print(f"Error parsing a tweet: {e}")
                    continue

            # Scroll down
            page.evaluate("window.scrollBy(0, 1000)")
            time.sleep(2) # Wait for network requests
            
            new_height = page.evaluate("document.body.scrollHeight")
            if new_height == last_height:
                attempts += 1
                if attempts >= 3:
                    break
            else:
                attempts = 0
                last_height = new_height
            
            # Heuristic break: if we have a lot of tweets, maybe stop? 
            # Or reliance on "Show more replies" button?
            # For now, simple scrolling is usually enough for medium threads.

        if len(collected_tweets) <= 1:
            os.makedirs("debug", exist_ok=True)
            debug_path = os.path.join("debug", "debug_page.png")
            print(f"Debug: Saving screenshot to {debug_path}")
            page.screenshot(path=debug_path, full_page=True)
            
            # thorough debug of page content
            content = page.content()
            if "Sign in to X" in content or "Log in" in content:
                print("DEBUG_INFO: Login detected on page.")
            if "Unlock more on X" in content:
                print("DEBUG_INFO: 'Unlock more' wall detected.")
            if "Show more replies" in content:
                print("DEBUG_INFO: 'Show more replies' button detected (but maybe not clicked).")

        browser.close()
        return collected_tweets

if __name__ == "__main__":
    # Test with a dummy URL or user input
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else "https://x.com/jack/status/20"
    data = get_thread(url, headless=True)
    print(f"Found {len(data)} tweets.")
    for t in data:
        print(f"- [{t['timestamp']}] {t['text'][:50]}...")
