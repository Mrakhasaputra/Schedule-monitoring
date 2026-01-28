import os
import time
from apify_client import ApifyClient
from dotenv import load_dotenv
from datetime import datetime, timedelta
import logging

from .utils import download_media, load_metadata_from_file, save_metadata_to_file

# Setup logging
logger = logging.getLogger(__name__)

# === Load environment ===
load_dotenv()

IS_LOAD_METADATA_FROM_FILE = False
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")

SOURCE_TYPE = "facebook"
DOWNLOAD_DIR = "downloads/facebook"
OUTPUT_FILE = "report-output/facebook_posts.json"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

class FacebookScrapper():
    def __init__(self):
        self.actor_id = "KoJrdxJCTtpon81KY"
        self.output_file = OUTPUT_FILE

    def scrape_media_from_facebook(self, page_url, scrap_at=None, max_items=10, enable_multiple_slides=False):
        """Scrape media from Facebook page"""
        logger.info(f"🚀 Scraping Facebook Page: {page_url}")
        
        if not APIFY_API_TOKEN:
            logger.error("❌ APIFY_API_TOKEN not found in environment variables")
            return []
        
        if IS_LOAD_METADATA_FROM_FILE:
            saved_metadata = load_metadata_from_file(OUTPUT_FILE)
            return saved_metadata
        
        try:
            client = ApifyClient(APIFY_API_TOKEN)
            
            run_input = {
                "captionText": True,
                "resultsLimit": max_items,
                "startUrls": [{"url": page_url}],
            }

            # Handle date filtering if provided
            if scrap_at:
                if not isinstance(scrap_at, str):
                    scrap_at = scrap_at.strftime("%Y-%m-%d")
                    
                scrap_date = datetime.strptime(scrap_at, "%Y-%m-%d")
                start_date = scrap_date.strftime("%Y-%m-%dT00:00:00.000Z")
                end_date = (scrap_date + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00.000Z")
                
                run_input["onlyPostsNewerThan"] = start_date
                run_input["onlyPostsOlderThan"] = end_date
            else:
                run_input["onlyPostsOlderThan"] = "1 day"

            logger.info("Starting Apify actor...")
            run = client.actor(self.actor_id).call(run_input=run_input)
            run_id = run["id"]

            # Wait for completion
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
            logger.info(f"🎯 Found {len(posts)} posts from Facebook page.")

            # Prepare download folder
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            page_name = page_url.rstrip("/").split("/")[-1] or "facebook_page"
            folder = os.path.join(DOWNLOAD_DIR, f"{page_name}_{timestamp}")
            os.makedirs(folder, exist_ok=True)

            saved_metadata = []
            post_key = "file_path"
            
            for i, post in enumerate(posts, start=1):
                text = post.get("text", "")
                text_preview = text[:80].replace("\n", " ")
                logger.info(f"📍 Post {i}: {text_preview}...")

                # Extract media URLs
                media_urls = []
                if post.get("media"):
                    for m in post["media"]:
                        media_type = m.get("__typename") or m.get("__isMedia")

                        if media_type == "Video":
                            if m.get("thumbnail"):
                                media_urls.append(m["thumbnail"])
                            elif m.get("first_frame_thumbnail"):
                                media_urls.append(m["first_frame_thumbnail"])
                            elif m.get("videoDeliveryLegacyFields"):
                                legacy = m["videoDeliveryLegacyFields"]
                                url = legacy.get("browser_native_hd_url") or legacy.get("browser_native_sd_url")
                                if url:
                                    media_urls.append(url)
                        else:
                            if m.get("image") and m["image"].get("uri"):
                                media_urls.append(m["image"]["uri"])
                            elif m.get("photo_image") and m["photo_image"].get("uri"):
                                media_urls.append(m["photo_image"]["uri"])

                if not media_urls:
                    logger.warning("⚠️ No media found, skipping this post.")
                    continue

                if not enable_multiple_slides:
                    media_urls = media_urls[:1]

                for j, media_url in enumerate(media_urls, start=0):
                    filename_prefix = f"post{i}_media{j+1}"
                    file_path = download_media(media_url, folder, filename_prefix)
                    
                    if not file_path:
                        continue

                    new_entry = post.copy()
                    new_entry[post_key] = file_path
                    new_entry["child_index"] = j
                    new_entry["scraped_at"] = datetime.now().isoformat()

                    saved_metadata.append(new_entry)

            # Save results
            save_metadata_to_file(saved_metadata, OUTPUT_FILE)
            logger.info("🏁 Facebook scraping completed!")
            
            return saved_metadata

        except Exception as e:
            logger.error(f"❌ Facebook scraping failed: {e}")
            return []