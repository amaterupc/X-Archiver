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

from src.agent_interface import AgentBrowserInterface
import lxml.html

def get_thread(url: str, headless: bool = True, backend: str = "playwright"):
    """
    Fetches an X thread from the given URL.
    Returns a list of dictionaries containing tweet data.
    
    Args:
        url (str): The URL of the thread.
        headless (bool): Whether to run in headless mode (Playwright only).
        backend (str): 'playwright' or 'agent-browser'.
    """
    if backend == "agent-browser":
        return _get_thread_agent_browser(url)
    else:
        return _get_thread_playwright(url, headless)

def _get_thread_agent_browser(url: str):
    """
    Implementation using agent-browser CLI.
    """
    print(f"[Agent-Browser] Starting session for {url}")
    agent = AgentBrowserInterface()
    
    collected_tweets = []
    seen_ids = set()
    
    try:
        # Load available cookies
        storage_path = os.path.join("data", "cookies.json")
        storage_state = load_storage_state(storage_path)
        
        if storage_state and "cookies" in storage_state:
            print("[Agent-Browser] Pre-loading x.com to set cookies...")
            # We need to establish a domain context to set cookies usually
            agent.open("https://x.com")
            # Wait a bit for page init (even if it redirects to login)
            agent.wait(3000)
            
            count = 0
            for c in storage_state["cookies"]:
                # Simple domain check to avoid setting irrelevant cookies if any
                domain = c.get("domain", "")
                if ".x.com" in domain or ".twitter.com" in domain or "x.com" == domain:
                    agent.set_cookie(c)
                    count += 1
            print(f"[Agent-Browser] Set {count} cookies.")
        
        # Navigate
        print(f"[Agent-Browser] Navigating to target: {url}")
        agent.open(url)
        agent.wait(5000) # Wait for initial load
        
        # Determine OP handle from URL
        # URL format: https://x.com/username/status/123...
        op_handle = ""
        match = re.search(r'x\.com/([^/]+)/status', url)
        if match:
            op_handle = match.group(1)
        
        # Scroll loop similar to Playwright
        max_attempts = 5
        attempts = 0
        last_html_len = 0
        
        for i in range(max_attempts):
            print(f"[Agent-Browser] Scroll iteration {i+1}/{max_attempts}")
            
            # Click "Show more" buttons using JS injection
            # This is more robust than finding selectors one by one via CLI
            js_click_all = """
            (() => {
                const buttons = document.querySelectorAll('[data-testid="tweet-text-show-more-link"]');
                let count = 0;
                buttons.forEach(b => {
                    // Check visibility (offsetParent is null if hidden)
                    if (b.offsetParent !== null) {
                        b.click();
                        count++;
                    }
                });
                return count;
            })()
            """
            try:
                res = agent.evaluate(js_click_all)
                # The result might be "2" or similar string, or empty.
                if res and res.isdigit() and int(res) > 0:
                    print(f"[Agent-Browser] Expanded {res} tweets.")
                    agent.wait(500) # Wait for expansion
            except Exception as e:
                print(f"[Agent-Browser] Warning: JS eval failed: {e}")
            
            # Get content
            html_content = agent.get_html()
            if not html_content:
                print("[Agent-Browser] Failed to get HTML content.")
                break
                
            current_len = len(html_content)
            if current_len == last_html_len:
                attempts += 1
                if attempts >= 2:
                    print("[Agent-Browser] No more content loading.")
                    break
            else:
                attempts = 0
                last_html_len = current_len
            
            # Parse HTML with lxml
            # Since we can't use Playwright's element handles, we parse the static HTML dump.
            # This is less robust for dynamic events but sufficient for scraping text.
            tweets = _parse_html_tweets(html_content, op_handle)
            
            new_tweets = 0
            for t in tweets:
                if t['id'] not in seen_ids:
                    collected_tweets.append(t)
                    seen_ids.add(t['id'])
                    new_tweets += 1
            
            print(f"[Agent-Browser] Found {new_tweets} new tweets (Total: {len(collected_tweets)})")
            
            # Scroll down
            agent.scroll("down", 1000)
            agent.wait(2000)
            
    except Exception as e:
        print(f"[Agent-Browser] Error: {e}")
    finally:
        agent.close()
        
    return collected_tweets

def _parse_html_tweets(html_content, op_handle):
    """
    Parses tweet data from raw HTML content using lxml.
    """
    tweets_data = []
    if not html_content:
        return tweets_data
        
    try:
        doc = lxml.html.fromstring(html_content)
        articles = doc.xpath('//article[@data-testid="tweet"]')
        
        for article in articles:
            try:
                # Text
                text_div = article.xpath('.//div[@data-testid="tweetText"]')
                text = text_div[0].text_content() if text_div else ""
                
                # Timestamp
                time_el = article.xpath('.//time')
                timestamp = time_el[0].get('datetime') if time_el else ""
                
                # Links for ID
                links = article.xpath('.//a[contains(@href, "/status/")]')
                tweet_url = ""
                tweet_id = None
                
                for link in links:
                    href = link.get('href')
                    # Check if inside quote
                    # accurate XPath check for ancestor quote is tricky on static generic HTML parse 
                    # without precise class logic, but let's try strict hierarchy check if possible.
                    # Simplified: just take first one that looks like a main status.
                    if "/status/" in href:
                        tweet_url = href
                        match = re.search(r'/status/(\d+)', href)
                        if match:
                            tweet_id = match.group(1)
                            # Prefer OP's status
                            if op_handle and f"/{op_handle}/" in href:
                                break
                
                if not tweet_id:
                     tweet_id = f"{timestamp}-{text[:10]}"
                
                # Images
                imgs = article.xpath('.//img[contains(@src, "pbs.twimg.com/media")]')
                images = [img.get('src') for img in imgs]
                
                # Video (simple check)
                video = article.xpath('.//div[@data-testid="videoPlayer"]')
                has_video = bool(video)
                
                # Check handle to filter non-OP replies (approximate without detailed user info)
                # We try to find the user link at the start of the tweet
                user_links = article.xpath('.//div[@data-testid="User-Name"]//a[starts-with(@href, "/")]')
                tweet_handle = ""
                if user_links:
                    tweet_handle = user_links[0].get('href').strip("/")
                
                if op_handle and tweet_handle != op_handle:
                    continue

                tweets_data.append({
                    "id": tweet_id,
                    "text": text,
                    "timestamp": timestamp,
                    "images": images,
                    "url": tweet_url,
                    "has_video": has_video
                })
                
            except Exception as ex:
                continue
                
    except Exception as e:
        print(f"Parse error: {e}")
        
    # Try parsing as Twitter Article (Note)
    try:
        doc = lxml.html.fromstring(html_content)
        article_view = doc.xpath('//div[@data-testid="twitterArticleReadView"]')
        
        if article_view:
            print("[Agent-Browser] Detected Twitter Article/Note.")
            view = article_view[0]
            
            # Title
            title_el = view.xpath('.//div[@data-testid="twitter-article-title"]')
            title = title_el[0].text_content() if title_el else "No Title"
            
            # Body content
            # Strategy: Get all text from div components that are likely paragraphs
            # We look for divs that have specific text classes or generic containers excluding buttons
            
            # Remove noise elements (buttons, stats) from a copy to extract text cleanly
            # However, lxml copies are tricky. We can try to select specific content divs.
            # Observation: Content usually resides in 'div.css-1jxf684' spans or 'div.longform-*'
            
            # Simple approach: Extract all text, but filter out button text which usually are stats.
            # However, stats like "92 replies" are in buttons.
            
            content_text = []
            
            # Extract title explicitly
            content_text.append(f"# {title}\n")
            
            # Find the main container? 
            # We iterate over all text-bearing elements and try to exclude buttons/ui
            
            # Get all elements with text
            all_elements = view.xpath('.//*[text()]')
            # Filter:
            # - Ignore inside button
            # - Ignore inside script/style
            
            # Better: use CSS classes if possible. 
            # "css-1jxf684" seems to be the text span class.
            text_spans = view.xpath('.//span[contains(@class, "css-1jxf684")] | .//div[contains(@class, "css-1jxf684")] | .//span')
            
            seen_text = set()
            body_text = []
            
            for span in text_spans:
                txt = span.text_content().strip()
                if not txt:
                    continue
                    
                # Check if inside button
                is_button = span.xpath('ancestor::button')
                if is_button:
                    continue

                # Check if it's the title (already added)
                is_title = span.xpath('ancestor::div[@data-testid="twitter-article-title"]')
                if is_title:
                    continue

                if txt and txt not in seen_text:
                    body_text.append(txt)
                    seen_text.add(txt)

            full_text = "\n\n".join(body_text)
            text = f"{title}\n\n{full_text}"

            # ID and Timestamp
            # URL is passed in args or found in links
            tweet_id = None
            if op_handle:
                # Try to find link to this article
                pass

            # Attempt to find timestamp
            time_el = view.xpath('.//time')
            timestamp = time_el[0].get('datetime') if time_el else ""

            # ID from URL or timestamp
            parent_link = time_el[0].getparent().get('href') if time_el else ""
            match = re.search(r'/status/(\d+)', str(parent_link))
            if not match:
                match = re.search(r'/article/(\d+)', str(parent_link))

            if match:
                tweet_id = match.group(1)
            else:
                tweet_id = f"article-{timestamp}"

            # Images in Article
            imgs = view.xpath('.//img[contains(@src, "pbs.twimg.com/media")]')
            images = [img.get('src') for img in imgs]

            # Add to tweets_data if not duplicate
            tweets_data.append({
                "id": tweet_id,
                "text": text,
                "timestamp": timestamp,
                "images": images,
                "url": f"https://x.com/{op_handle}/status/{tweet_id}" if tweet_id and op_handle else "",
                "has_video": False,
                "is_article": True
            })

    except Exception as e:
        print(f"Article Parse error: {e}")

    return tweets_data

def _get_thread_playwright(url: str, headless: bool = True):
    """
    Fetches an X thread from the given URL using Playwright.
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
            # 1. Expand "Show more" / "Read more" buttons
            # Try to click "Show more" buttons to expand truncated text
            try:
                # We will try a few selectors but catch errors aggressively
                # [data-testid="tweet-text-show-more-link"] is the most specific one.
                buttons = page.query_selector_all('[data-testid="tweet-text-show-more-link"]')
                # if not buttons:
                #    # Fallback to text search if testid is missing - DISABLED for safety/speed
                #    buttons = page.query_selector_all('text="Show more"')
                # if not buttons:
                #    buttons = page.query_selector_all('text="さらに表示"')
                
                if buttons:
                    # print(f"Debug: Found {len(buttons)} 'Show more' buttons.")
                    pass

                for btn in buttons:
                    if btn.is_visible():
                        try:
                            # print("Debug: Clicking 'Show more'...")
                            btn.click(timeout=1000)
                            # Small sleep to allow simple expansion
                            time.sleep(0.5) 
                        except Exception:
                            pass 
            except Exception as e:
                pass

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

        # Check for Twitter Article (Note) if not yet found
        has_article = any(t.get('is_article') for t in collected_tweets)
        if not has_article:
            article_view = page.query_selector('div[data-testid="twitterArticleReadView"]')
            if article_view:
                print("Detected Twitter Article/Note.")
                
                try:
                    # Title
                    title_el = article_view.query_selector('div[data-testid="twitter-article-title"]')
                    title = title_el.inner_text() if title_el else "No Title"
                    
                    # Body content: Use evaluate to robustly extract text excluding buttons
                    body_text = article_view.evaluate("""(el) => {
                        const title = el.querySelector('div[data-testid="twitter-article-title"]');
                        const textNodes = [];
                        const seen = new Set();
                        
                        // Select all text-containing elements
                        const candidates = el.querySelectorAll('span, div');
                        
                        candidates.forEach(node => {
                            // Filter out buttons
                            if (node.closest('button')) return;
                            // Filter out title
                            if (title && (title === node || title.contains(node))) return;
                            
                            const text = node.innerText.trim();
                            if (text && !seen.has(text)) {
                                textNodes.push(text);
                                seen.add(text);
                            }
                        });
                        return textNodes.join('\\n\\n');
                    }""")
                    
                    full_text = f"# {title}\n\n{body_text}"
                    
                    # Metadata
                    time_el = article_view.query_selector('time')
                    timestamp = time_el.get_attribute("datetime") if time_el else ""
                    
                    # ID extraction
                    tweet_id = None
                    if time_el:
                        parent = time_el.evaluate_handle(
                            "el => el.parentElement"
                        )
                        href = parent.get_attribute("href")
                        if href:
                            match = re.search(
                                r'/(?:status|article)/(\d+)', href
                            )
                            if match:
                                tweet_id = match.group(1)
                    
                    if not tweet_id:
                        tweet_id = f"article-{timestamp}"
                        
                    # Images
                    images = []
                    img_elements = article_view.query_selector_all(
                        'img[src*="pbs.twimg.com/media"]'
                    )
                    for img in img_elements:
                        src = img.get_attribute("src")
                        if src:
                            images.append(src)
                             
                    # Add to collected tweets
                    collected_tweets.append({
                        "id": tweet_id,
                        "text": full_text,
                        "timestamp": timestamp,
                        "images": images,
                        "url": url,
                        "has_video": False,
                        "is_article": True
                    })
                    
                except Exception as e:
                    print(f"Error parsing Article in Playwright: {e}")

        if not any(t.get('is_article') for t in collected_tweets):
            os.makedirs("debug", exist_ok=True)
            debug_path = os.path.join("debug", "debug_page_pw.png")
            print(
                f"[Playwright] Debug: No article found. Screen: {debug_path}"
            )
            page.screenshot(path=debug_path, full_page=True)

            # Additional debug info
            if "Sign in to X" in page.content():
                print("[Playwright] Login wall detected.")

        browser.close()
        return collected_tweets


class AgentBrowserInterface:

if __name__ == "__main__":
    # Test with a dummy URL or user input
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else "https://x.com/jack/status/20"
    data = get_thread(url, headless=True)
    print(f"Found {len(data)} tweets.")
    for t in data:
        print(f"- [{t['timestamp']}] {t['text'][:50]}...")
