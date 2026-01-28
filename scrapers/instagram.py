import os
import time
from apify_client import ApifyClient
from dotenv import load_dotenv
from datetime import datetime
import logging

from .utils import download_media, load_metadata_from_file, save_metadata_to_file

logger = logging.getLogger(__name__)

load_dotenv()

IS_LOAD_METADATA_FROM_FILE = False
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")

SOURCE_TYPE = "instagram"
DOWNLOAD_DIR = "downloads/instagram"
OUTPUT_FILE = "report-output/instagram_posts.json"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

class InstagramScrapper():
    def __init__(self):
        self.actor_id = "apify/instagram-scraper"
        self.output_file = OUTPUT_FILE

    def scrape_media_from_instagram(self, page_url, scrap_at=None, max_items=10, enable_multiple_slides=False):
        logger.info(f"🚀 Scraping Instagram Page: {page_url}")
        
        if not APIFY_API_TOKEN:
            logger.error("❌ APIFY_API_TOKEN not found in environment variables")
            return []
        
        if IS_LOAD_METADATA_FROM_FILE:
            return load_metadata_from_file(OUTPUT_FILE)
        
        try:
            client = ApifyClient(APIFY_API_TOKEN)
            
            run_input = {
                "addParentData": False,
                "directUrls": [page_url],
                "enhanceUserSearchWithFacebookPage": False,
                "isUserReelFeedURL": False,
                "isUserTaggedFeedURL": False,
                "resultsLimit": max_items,
                "resultsType": "posts",
                "search": page_url,
                "skipPinnedPosts": True,
                "onlyPostsNewerThan": "0 days",
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
            logger.info(f"🎯 Found {len(posts)} posts from Instagram.")

            # Prepare download folder
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            page_name = page_url.rstrip("/").split("/")[-1] or "instagram_page"
            folder = os.path.join(DOWNLOAD_DIR, f"{page_name}_{timestamp}")
            os.makedirs(folder, exist_ok=True)

            saved_metadata = []
            post_key = "file_path"
            
            for i, item in enumerate(posts, start=1):
                filename_prefix = f"post{i}_media"
                file_path = None

                if item.get("videoUrl"):
                    media_url = item.get("displayUrl") or item["videoUrl"]
                    file_path = download_media(media_url, folder, filename_prefix)
                    
                elif item.get("childPosts"):
                    if enable_multiple_slides:
                        for idx, child in enumerate(item["childPosts"], start=1):
                            media_url = child.get("displayUrl") or child.get("videoUrl")
                            if media_url:
                                child_prefix = f"post{i}_media{idx}"
                                child_file_path = download_media(media_url, folder, child_prefix)
                                child[post_key] = child_file_path
                    else:
                        first_child = item["childPosts"][0]
                        media_url = first_child.get("displayUrl") or first_child.get("videoUrl")
                        if media_url:
                            file_path = download_media(media_url, folder, filename_prefix)
                            
                elif item.get("displayUrl"):
                    file_path = download_media(item["displayUrl"], folder, filename_prefix)

                if file_path:
                    item[post_key] = file_path
                    item["scraped_at"] = datetime.now().isoformat()
                    saved_metadata.append(item)

            save_metadata_to_file(saved_metadata, OUTPUT_FILE)
            logger.info("🏁 Instagram scraping completed!")
            
            return saved_metadata

        except Exception as e:
            logger.error(f"❌ Instagram scraping failed: {e}")
            return []