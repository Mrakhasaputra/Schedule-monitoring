import os
import time
import requests
from apify_client import ApifyClient
from dotenv import load_dotenv
from datetime import datetime
import logging

from .utils import download_media, load_metadata_from_file, save_metadata_to_file, parse_flexible_timestamp

logger = logging.getLogger(__name__)

# === Load environment ===
load_dotenv()

IS_LOAD_METADATA_FROM_FILE = False
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")

SOURCE_TYPE = "tiktok"
DOWNLOAD_DIR = "downloads/tiktok"
OUTPUT_FILE = "report-output/tiktok_posts.json"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

class TikTokScrapper():
    def __init__(self):
        self.actor_id = "clockworks/tiktok-scraper"
        self.output_file = OUTPUT_FILE
        self.api_tiktok = "https://www.tikwm.com/api"

    def scrape_media_from_tiktok(self, scrap_at=None, max_items=10, page_url=None, username=None, enable_multiple_slides=False):
        logger.info(f"🚀 Scraping TikTok - URL: {page_url}, Username: {username}")
        
        if not APIFY_API_TOKEN:
            logger.error("❌ APIFY_API_TOKEN not found in environment variables")
            return []
        
        if IS_LOAD_METADATA_FROM_FILE:
            return load_metadata_from_file(OUTPUT_FILE)
        
        try:
            client = ApifyClient(APIFY_API_TOKEN)
            
            run_input = {
                "excludePinnedPosts": True,
                "proxyCountryCode": "US",
                "resultsPerPage": max_items,
                "scrapeRelatedVideos": False,
                "shouldDownloadAvatars": False,
                "shouldDownloadCovers": False,
                "shouldDownloadMusicCovers": False,
                "shouldDownloadSlideshowImages": True,
                "shouldDownloadSubtitles": False,
                "shouldDownloadVideos": True
            }

            if username:
                run_input["profiles"] = [username]

            if page_url:
                run_input["postURLs"] = [page_url]

            if scrap_at:
                run_input["newestPostDate"] = scrap_at
            else:
                run_input["oldestPostDateUnified"] = "1 day"

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
            logger.info(f"🎯 Found {len(posts)} posts from TikTok.")

            # Prepare download folder
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            default_page_name = "tiktok_page"
            if page_url:
                page_name = page_url.rstrip("/").split("/")[-1].replace("@", "")
            else:
                page_name = username.replace("@", "") if username else default_page_name
                
            folder = os.path.join(DOWNLOAD_DIR, f"{page_name}_{timestamp}")
            os.makedirs(folder, exist_ok=True)

            saved_metadata = []
            post_key = "file_path"
            
            for i, post in enumerate(posts, start=1):
                video_id = post.get("id")
                video_url = post.get("webVideoUrl")
                slideshow_images = post.get("slideshowImageLinks", [])
                video_meta = post.get("videoMeta", {})
                thumbnail_url = video_meta.get("originalCoverUrl") or video_meta.get("coverUrl")

                if slideshow_images:
                    if enable_multiple_slides:
                        # Ambil semua slide
                        for slide_index, img in enumerate(slideshow_images):
                            media_url = img.get("downloadLink")
                            if not media_url:
                                continue
                            filename_prefix = f"post{i}_media{slide_index}"
                            file_path = download_media(media_url, folder, filename_prefix)
                            if file_path:
                                img["file_path"] = file_path
                    else:
                        # Ambil slide pertama saja
                        first_slide = slideshow_images[0]
                        media_url = first_slide.get("downloadLink")
                        if media_url:
                            filename_prefix = f"post{i}_media"
                            file_path = download_media(media_url, folder, filename_prefix)
                            if file_path:
                                first_slide["file_path"] = file_path

                elif thumbnail_url:
                    logger.info(f"Downloading thumbnail for post {video_id}")
                    filename_prefix = f"post{i}_media"
                    file_path = download_media(thumbnail_url, folder, filename_prefix)
                    if file_path:
                        post[post_key] = file_path
                        
                elif video_url:
                    api = f"{self.api_tiktok}/?url={video_url}"
                    try:
                        response = requests.get(api, timeout=20)
                        data = response.json()
                        download_url = data.get("data", {}).get("play", "")
                        if download_url:
                            filename_prefix = f"post{i}_media"
                            file_path = download_media(download_url, folder, filename_prefix)
                            if file_path:
                                post[post_key] = file_path
                    except Exception as e:
                        logger.error(f"⚠️ Failed to download video for post {video_id}: {e}")
                
                if post.get(post_key):
                    post["scraped_at"] = datetime.now().isoformat()
                    saved_metadata.append(post)

            save_metadata_to_file(saved_metadata, OUTPUT_FILE)
            logger.info("🏁 TikTok scraping completed!")
            
            return saved_metadata

        except Exception as e:
            logger.error(f"❌ TikTok scraping failed: {e}")
            return []