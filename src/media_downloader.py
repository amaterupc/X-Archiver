import os
import subprocess
import json
import re

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
        
    return media_map
