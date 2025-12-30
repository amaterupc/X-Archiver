import sys
import argparse
import os
import re
from src.fetcher import get_thread
from src.formatter import format_to_markdown
from src.media_downloader import download_media

def main():
    parser = argparse.ArgumentParser(description="Convert an X thread to a blog-style Markdown file.")
    parser.add_argument("url", help="The URL of the first tweet in the thread.")
    parser.add_argument("--output", "-o", help="Output filename (optional). Default is out/thread_<id>.md")
    parser.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True, help="Run browser in headless mode.")
    parser.add_argument("--media", action=argparse.BooleanOptionalAction, default=True, help="Download images and videos locally.")
    
    args = parser.parse_args()
    
    # Ensure out directory exists
    os.makedirs("out", exist_ok=True)
    
    url = args.url
    print(f"fetching thread from: {url}")
    
    # 1. Fetch thread content using Playwright
    tweets = get_thread(url, headless=args.headless)
    
    if not tweets:
        print("Failed to retrieve tweets.")
        sys.exit(1)
        
    print(f"Successfully retrieved {len(tweets)} tweets.")
    
    # Extract ID for folder naming
    match = re.search(r'/status/(\d+)', url)
    tweet_id = match.group(1) if match else "unknown"
    
    # 2. Download media using gallery-dl
    media_map = {}
    if args.media:
        media_dir = os.path.join("out", "media", tweet_id)
        # Use cookies if available
        cookies_path = os.path.join("data", "cookies.json")
        print(f"Downloading media to {media_dir}...")
        media_map = download_media(tweets, media_dir, root_url=url)
    
    # 3. Format to Markdown
    markdown_content = format_to_markdown(tweets, media_map)
    
    # Determine output filename
    if args.output:
        filename = args.output
    else:
        if tweet_id != "unknown":
            filename = os.path.join("out", f"thread_{tweet_id}.md")
        else:
            filename = os.path.join("out", "thread_output.md")
            
    with open(filename, "w", encoding="utf-8") as f:
        f.write(markdown_content)
        
    print(f"Saved blog post to {filename}")

if __name__ == "__main__":
    main()
