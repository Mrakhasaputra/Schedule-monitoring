import os
import time
from apify_client import ApifyClient
from dotenv import load_dotenv
from datetime import datetime
import logging
import requests

from .utils import load_metadata_from_file, save_metadata_to_file, parse_flexible_timestamp

logger = logging.getLogger(__name__)

# === Load environment ===
load_dotenv()

IS_LOAD_METADATA_FROM_FILE = False
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
YOUTUBE_RAPIDAPI_HOST = os.getenv("YOUTUBE_RAPIDAPI_HOST")
URL_YOUTUBE_DOWNLOADER = os.getenv("URL_YOUTUBE_DOWNLOADER")

SOURCE_TYPE = "youtube"
DOWNLOAD_DIR = "downloads/youtube"
OUTPUT_FILE = "report-output/youtube_posts.json"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

class YoutubeScrapper():
    def __init__(self):
        self.actor_id = "streamers/youtube-scraper"
        self.output_file = OUTPUT_FILE

    def download_video(self, folder, video_id, title):
        logger.info(f"⬇️ Downloading video '{title}'...")

        video_id = video_id.split("?")[0].strip()

        if not RAPIDAPI_KEY or not YOUTUBE_RAPIDAPI_HOST:
            logger.error("❌ RAPIDAPI credentials not found")
            return None

        url = URL_YOUTUBE_DOWNLOADER
        querystring = {"videoId": video_id, "urlAccess": "normal"}
        headers = {
            "x-rapidapi-key": RAPIDAPI_KEY,
            "x-rapidapi-host": YOUTUBE_RAPIDAPI_HOST
        }

        try:
            response = requests.get(url, headers=headers, params=querystring, timeout=30)
            response.raise_for_status()
            data = response.json()

            if "thumbnails" in data and len(data["thumbnails"]) > 0:
                thumbnail_url = data["thumbnails"][-1]["url"]
                ext = "webp" if "webp" in thumbnail_url else "jpg"
                logger.info(f"Thumbnail found: {thumbnail_url}")

                filename = f"{folder}/{video_id}.{ext}"
                try:
                    img_data = requests.get(thumbnail_url, timeout=30).content
                    with open(filename, "wb") as f:
                        f.write(img_data)
                    logger.info("✅ Thumbnail downloaded successfully")
                    return filename
                except Exception as e:
                    logger.error(f"❌ Failed to download thumbnail: {e}")

            if "videos" not in data or len(data["videos"]) == 0:
                logger.error(f"❌ No download link found for '{title}'")
                return None

            video_link = data["videos"]["items"][0]["url"]
            filename = f"{folder}/{video_id}.mp4"

            video_data = requests.get(video_link, stream=True, timeout=60)
            video_data.raise_for_status()
            
            with open(filename, "wb") as f:
                for chunk in video_data.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
            
            logger.info("✅ Video downloaded successfully")
            return filename

        except Exception as e:
            logger.error(f"❌ Failed to download video '{title}': {e}")
            return None

    def scrape_media_from_youtube(self, page_url, scrap_at=None, max_items=10):
        logger.info(f"🚀 Scraping YouTube Page: {page_url}")
        
        if not APIFY_API_TOKEN:
            logger.error("❌ APIFY_API_TOKEN not found in environment variables")
            return []
        
        if IS_LOAD_METADATA_FROM_FILE:
            return load_metadata_from_file(OUTPUT_FILE)
        
        try:
            client = ApifyClient(APIFY_API_TOKEN)
            
            run_input = {
                "maxResultStreams": 0,
                "maxResults": max_items,
                "maxResultsShorts": 0,
                "startUrls": [{"url": page_url}],
            }

            logger.info("Starting Apify actor...")
            run = client.actor(self.actor_id).call(run_input=run_input)
            run_id = run["id"]

            while True:
                run_info = client.run(run_id).get()
                status = run_info["status"]
                logger.info(f"Current status: {status}")
                if status in ["SUCCEEDED", "FAILED", "ABORTED"]:
                    logger.info(f"Actor finished with status: {status}")
                    break
                time.sleep(5)

            logger.info("📦 Fetching scrape results...")
            posts = list(client.dataset(run["defaultDatasetId"]).iterate_items())
            logger.info(f"🎯 Found {len(posts)} posts from YouTube.")

            # Prepare download folder
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            page_name = page_url.rstrip("/").split("/")[-1] or "youtube_page"
            folder = os.path.join(DOWNLOAD_DIR, f"{page_name}_{timestamp}")
            os.makedirs(folder, exist_ok=True)

            saved_metadata = []
            post_key = "file_path"
            
            for i, vid in enumerate(posts[:max_items], start=1):
                video_id = vid.get("id")
                url = vid.get("url")
                title = vid.get("title", "untitled")

                # Parse upload time
                raw_upload_at = vid.get("date")
                upload_at_dt = parse_flexible_timestamp(raw_upload_at)      
                if upload_at_dt:
                    upload_at = upload_at_dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")
                else:
                    upload_at = raw_upload_at

                if not url:
                    continue

                actual_file_path = self.download_video(folder, video_id, title)

                video_id = video_id.split("?")[0].strip()
                file_path = actual_file_path if actual_file_path else f"{folder}/{video_id}.mp4"

                saved_metadata.append({
                    "page_url": url,
                    "title": title,
                    "text": vid.get("text", ""),
                    "upload_at": upload_at,
                    post_key: file_path,
                    "scraped_at": datetime.now().isoformat()
                })

            save_metadata_to_file(saved_metadata, OUTPUT_FILE)
            logger.info("🏁 YouTube scraping completed!")
            
            return saved_metadata

        except Exception as e:
            logger.error(f"❌ YouTube scraping failed: {e}")
            return []