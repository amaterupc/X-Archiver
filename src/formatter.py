import os

def format_to_markdown(tweets: list, media_map: dict = None) -> str:
    """
    Converts a list of tweet dictionaries into a blog-style Markdown string.
    """
    if not tweets:
        return "No tweets found."
    
    if media_map is None:
        media_map = {}

    markdown_output = []
    
    # Header logic
    first_tweet = tweets[0]
    title = first_tweet['text'][:50].replace('\n', ' ') + "..."
    markdown_output.append(f"# {title}\n")
    markdown_output.append(f"**Source:** [Start of Thread]({first_tweet.get('url', '#')})\n")
    markdown_output.append(f"**Date:** {first_tweet.get('timestamp', 'Unknown')}\n")
    markdown_output.append("---\n")

    for tweet in tweets:
        text = tweet['text']
        formatted_text = text.replace('\n', '\n\n')
        markdown_output.append(formatted_text)
        
        tweet_url = tweet.get('url', '')
        if tweet_url.startswith('/'):
            tweet_url = f"https://x.com{tweet_url}"
            
        # Add media associated with this tweet
        if tweet_url in media_map:
            for media_path in media_map[tweet_url]:
                ext = os.path.splitext(media_path)[1].lower()
                if ext in ['.mp4', '.webm', '.mkv']:
                    markdown_output.append(f"\n<video src=\"{media_path}\" controls style=\"max-width: 100%;\"></video>\n")
                elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                    markdown_output.append(f"\n![Image]({media_path})\n")
        else:
            # Fallback for images found by Playwright but not gallery-dl (unlikely now)
            if tweet.get('images'):
                for img_url in tweet['images']:
                    markdown_output.append(f"\n![Image]({img_url})\n")
        
        markdown_output.append("\n")

    return "\n".join(markdown_output)
