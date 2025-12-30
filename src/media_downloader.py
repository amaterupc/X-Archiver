import os
import subprocess
import json
import re

def convert_playwright_cookies_to_netscape(json_path: str, txt_path: str) -> bool:
    """
    Convert Playwright storageState format cookies.json to Netscape cookies.txt format.
    Returns True if conversion was successful, False otherwise.
    """
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        # Handle both raw list format and Playwright storageState format
        if isinstance(data, list):
            cookies = data
        elif isinstance(data, dict) and 'cookies' in data:
            cookies = data['cookies']
        else:
            return False
        
        lines = ["# Netscape HTTP Cookie File"]
        for cookie in cookies:
            domain = cookie.get('domain', '')
            # Netscape format: TRUE if domain starts with dot
            include_subdomains = "TRUE" if domain.startswith('.') else "FALSE"
            path = cookie.get('path', '/')
            secure = "TRUE" if cookie.get('secure', False) else "FALSE"
            # Convert expiry to integer timestamp
            expires = int(cookie.get('expires', 0)) if cookie.get('expires') else 0
            name = cookie.get('name', '')
            value = cookie.get('value', '')
            
            # Format: domain \t include_subdomains \t path \t secure \t expires \t name \t value
            line = f"{domain}\t{include_subdomains}\t{path}\t{secure}\t{expires}\t{name}\t{value}"
            lines.append(line)
        
        with open(txt_path, 'w') as f:
            f.write('\n'.join(lines))
        
        return True
    except Exception as e:
        print(f"Cookie conversion error: {e}")
        return False

def download_media(tweets: list, output_dir: str, root_url: str = None) -> dict:
    """
    Downloads media (videos and images) from the entire thread using gallery-dl.
    Returns a dictionary mapping tweet URL -> list of local relative paths.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    media_map = {}
    
    # gallery-dl configuration from user's successful debug script
    config_data = {
        "extractor": {
            "twitter": {
                "replies": "all",
                "conversation": "all",
                "quoted": True,
                "retweets": True,
                "api": "graphql",
                "tweet-metadata": True,
                "text-tweets": True,
                "videos": True,
                "images": True,
                "cards": True,
                "include": ["replies", "conversation", "quoted", "retweets"],
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "directory": [] # Flatten
            }
        }
    }
    
    config_path = os.path.join(output_dir, "gallery_dl_config.json")
    with open(config_path, 'w') as f:
        json.dump(config_data, f)

    if not root_url:
        return {}

    print(f"Running gallery-dl on thread root: {root_url}")

    try:
        cmd = [
            "./.venv/bin/gallery-dl",
            "--config", config_path,
            "--directory", output_dir,
            "--filename", "{tweet_id}_{num}.{extension}",
            root_url
        ]
        
        # Check for cookies (Netscape format)
        cookies_txt = os.path.join("data", "cookies.txt")
        cookies_json = os.path.join("data", "cookies.json")
        
        # Auto-convert from cookies.json if cookies.txt doesn't exist
        if not os.path.exists(cookies_txt) and os.path.exists(cookies_json):
            print("Converting cookies.json to cookies.txt for gallery-dl...")
            convert_playwright_cookies_to_netscape(cookies_json, cookies_txt)
        
        if os.path.exists(cookies_txt):
            cmd.extend(["--cookies", cookies_txt])

        
        # We don't strictly need to parse stdout if we just look at the directory afterwards
        subprocess.run(cmd, capture_output=True, text=True)
        
        # Get all files in the directory
        all_files = [os.path.join(output_dir, f) for f in os.listdir(output_dir) if os.path.isfile(os.path.join(output_dir, f))]
        
        # Map files to tweet IDs
        for tweet in tweets:
            tweet_id = tweet.get('id')
            if not tweet_id:
                continue
            
            tweet_url = tweet.get('url', '')
            if tweet_url.startswith('/'):
                full_url = f"https://x.com{tweet_url}"
            else:
                full_url = tweet_url
            
            matches = []
            for path in all_files:
                filename = os.path.basename(path)
                # Matches {tweet_id}_{num}.{ext}
                if filename.startswith(f"{tweet_id}_"):
                    # Use path relative to the "out" directory where the Markdown file will be
                    rel_path = os.path.relpath(path, start="out")
                    matches.append(rel_path)
            
            if matches:
                media_map[full_url] = matches
                print(f"Mapped {len(matches)} files to tweet {tweet_id}")

    except Exception as e:
        print(f"Error during media download: {e}")

    if os.path.exists(config_path):
        os.remove(config_path)
    
    # Fallback: Download images directly if gallery-dl didn't get them
    import requests
    for tweet in tweets:
        tweet_id = tweet.get('id')
        if not tweet_id:
            continue
        
        tweet_url = tweet.get('url', '')
        if tweet_url.startswith('/'):
            full_url = f"https://x.com{tweet_url}"
        else:
            full_url = tweet_url
        
        # Skip if already mapped by gallery-dl
        if full_url in media_map:
            continue
        
        images = tweet.get('images', [])
        if not images:
            continue
        
        downloaded = []
        for i, img_url in enumerate(images):
            try:
                # Convert to high quality URL
                high_quality_url = re.sub(r'name=\w+', 'name=large', img_url)
                if '?' not in high_quality_url:
                    high_quality_url += '?format=jpg&name=large'
                
                response = requests.get(high_quality_url, timeout=30)
                if response.status_code == 200:
                    # Determine extension
                    content_type = response.headers.get('content-type', '')
                    ext = 'jpg'
                    if 'png' in content_type:
                        ext = 'png'
                    elif 'gif' in content_type:
                        ext = 'gif'
                    
                    filename = f"{tweet_id}_{i+1}.{ext}"
                    filepath = os.path.join(output_dir, filename)
                    with open(filepath, 'wb') as f:
                        f.write(response.content)
                    
                    rel_path = os.path.relpath(filepath, start="out")
                    downloaded.append(rel_path)
            except Exception as e:
                print(f"Fallback download error for {img_url}: {e}")
        
        if downloaded:
            media_map[full_url] = downloaded
            print(f"Fallback: Downloaded {len(downloaded)} images for tweet {tweet_id}")
        
    return media_map

