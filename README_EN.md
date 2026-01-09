# X-Archiver

<div align="center">

**A tool to convert X (formerly Twitter) threads into blog-style Markdown articles**

English | [日本語](./README.md)

</div>

## Folder Structure

- `main.py`: Main executable. Orchestrates everything from fetching to conversion.
- `src/`: Core logic (fetching, formatting, media saving).
- `data/`: Stores authentication info (`cookies.json`).
- `out/`: Stores generated Markdown files and media (images/videos).
- `debug/`: Stores screenshots for troubleshooting.
- `docs/`: Documents like Requirements, Design specifications, and Release notes.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

2. Configure Login Information (Recommended):
   X (Twitter) does not display thread replies when not logged in. To fetch all tweets, please set up login info using these steps:

   1. Use a browser extension (e.g., [Get cookies.txt locally](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) / [GitHub](https://github.com/kairi003/Get-cookies.txt-Locally)) to export cookies for `x.com` in **JSON format**.
   2. Create a `data` folder in the project root and save it as `cookies.json`.
   
   *Note: If `data/cookies.json` is missing, only the initial tweet will be fetched.*

## Usage

Run by specifying the URL of the first post in the thread:

```bash
python main.py "https://x.com/username/status/1234567890"
```

### Options

* `--no-media`: Use original links instead of downloading images and videos locally.
* `--no-headless`: Run the browser in headful mode (with a window) to observe operations.

## Output
- `out/thread_<ID>.md`: The generated blog post.
- `out/media/<ID>/`: Local image and video files from the tweets.

> **Note**: When downloading media, `gallery-dl` scans the entire thread, which may result in media from outside the target range (e.g., past replies) being downloaded to `out/media/<ID>/`. This is intended to ensure video files are correctly identified. In the Markdown article, only media directly associated with the fetched tweets will be displayed.

## Technology Stack
- **Scraping**: Playwright (Headless mode)
- **Media Download**: gallery-dl
- **Formatting**: Python string formatting (Markdown)
