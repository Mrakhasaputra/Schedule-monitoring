import os
from dotenv import load_dotenv
from datetime import datetime
import logging
import requests

from .utils import download_media, load_metadata_from_file, save_metadata_to_file

logger = logging.getLogger(__name__)

# === Load environment ===
load_dotenv()

IS_LOAD_METADATA_FROM_FILE = False
TWITTER_API_KEY = os.getenv("X_API_KEY")  
X_RAPID_API_KEY = os.getenv("RAPIDAPI_KEY")
X_RAPIDAPI_HOST = os.getenv("X_RAPIDAPI_HOST")
URL_TWITTER_API_IO = os.getenv("URL_TWITTER_API_IO")
X_RAPID_API_URL = os.getenv("X_RAPID_API_URL")

SOURCE_TYPE = "x"
DOWNLOAD_DIR = "downloads/x"
OUTPUT_FILE = "report-output/x_posts.json"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

class XScrapper():
    def __init__(self):
        self.output_file = OUTPUT_FILE

    def fetch_from_twitterapi_io(self, username):
        try:
            logger.info("Fetching tweets from twitterapi.io...")
            
            if not TWITTER_API_KEY:
                raise ValueError("X_API_KEY not found")
                
            headers = {"X-API-Key": TWITTER_API_KEY}
            url_user_tweets = URL_TWITTER_API_IO
            params_tweets = {"userName": username}

            r = requests.get(url_user_tweets, headers=headers, params=params_tweets, timeout=15)
            r.raise_for_status()
            res_json = r.json()

            tweets = res_json.get("data", {}).get("tweets", [])
            if not tweets:
                raise ValueError("empty tweets")

            logger.info(f"✅ Got {len(tweets)} latest tweets from @{username} via twitterapi.io")
            return tweets
        except Exception as e:
            logger.error(f"❌ Failed to fetch from twitterapi.io: {e}")
            logger.info("↩️ Fallback to RapidAPI...")
            return self.fetch_from_rapidapi(username)
        
    def fetch_from_rapidapi(self, username):
        try:
            if not X_RAPID_API_KEY or not X_RAPIDAPI_HOST:
                raise ValueError("RapidAPI credentials not found")
                
            rapid_api_url = X_RAPID_API_URL
            querystring = {
                "username": username,
                "limit": "10",
                "include_replies": "false",
                "include_pinned": "false"
            }
            
            headers = {
                "x-rapidapi-key": X_RAPID_API_KEY,
                "x-rapidapi-host": X_RAPIDAPI_HOST
            }

            r = requests.get(rapid_api_url, headers=headers, params=querystring, timeout=15)
            r.raise_for_status()
            res_json = r.json()

            tweets = res_json.get("results") or res_json.get("tweets") or res_json.get("data", [])
            logger.info(f"✅ Got {len(tweets)} latest tweets from @{username} via RapidAPI")
            return tweets
        except Exception as e:
            logger.error(f"❌ Failed to fetch from RapidAPI: {e}")
            return []
            

    def scrape_media_from_x(self, scrap_at=None, max_items=10, username=None, page_url=None, enable_fetch_from_twitterapi_io=False, enable_multiple_slides=False):
        logger.info(f"🚀 Scraping X - Username: {username}, URL: {page_url}")
        
        if page_url:
            logger.warning("Only username scraping is supported currently, not direct page URLs")
            return []
            
        if not username:
            logger.error("❌ Username is required for X scraping")
            return []
        
        if IS_LOAD_METADATA_FROM_FILE:
            return load_metadata_from_file(OUTPUT_FILE)
        
        try:
            tweets = []
            
            if enable_fetch_from_twitterapi_io and TWITTER_API_KEY:
                tweets = self.fetch_from_twitterapi_io(username)
            else:
                tweets = self.fetch_from_rapidapi(username)
            
            posts = tweets[:max_items] if tweets else []

            # Prepare download folder
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            page_name = username.replace("@", "") if username else "x_page"
            folder = os.path.join(DOWNLOAD_DIR, f"{page_name}_{timestamp}")
            os.makedirs(folder, exist_ok=True)

            saved_metadata = []
            
            for i, tweet in enumerate(posts, start=1):
                tweet_id = tweet.get("tweet_id") or tweet.get("id")
                text = tweet.get("text") or tweet.get("full_text") or ""
                upload_at = tweet.get("creation_date")
                tweet_url = None

                extended_entities = tweet.get("extended_entities") or tweet.get("extendedEntities") or {}
                media_list = extended_entities.get("media", [])

                if media_list:
                    first_media = media_list[0]
                    tweet_url = first_media.get("display_url") or first_media.get("expanded_url")

                if not tweet_url:
                    tweet_url = f"https://x.com/{username}/status/{tweet_id}"

                if not media_list:
                    continue

                if not enable_multiple_slides:
                    media_list = media_list[:1]

                for media in media_list:
                    media_type = media.get("type")
                    media_url = None

                    if media_type in ["video", "animated_gif"]:
                        thumbnail = media.get("media_url_https") or media.get("media_url")

                        if thumbnail:
                            media_url = thumbnail
                        else:
                            variants = media.get("video_info", {}).get("variants", [])
                            mp4_variants = [v for v in variants if v.get("content_type") == "video/mp4"]
                            if mp4_variants:
                                media_url = sorted(mp4_variants, key=lambda v: v.get("bitrate", 0))[-1]["url"]
                    else:
                        media_url = media.get("media_url_https") or media.get("media_url")

                    if not media_url:
                        continue

                    filename = f"tweet_{tweet_id}_{media_type}_{i}"
                    file_path = download_media(media_url, folder, filename)

                    if file_path:
                        saved_metadata.append({
                            "id": tweet_id,
                            "url": tweet_url,
                            "text": text,
                            "media_type": media_type,
                            "upload_at": upload_at,
                            "file_path": file_path,
                            "scraped_at": datetime.now().isoformat()
                        })

            save_metadata_to_file(saved_metadata, OUTPUT_FILE)
            logger.info(f"🏁 X scraping completed! Saved {len(saved_metadata)} items")
            
            return saved_metadata

        except Exception as e:
            logger.error(f"❌ X scraping failed: {e}")
            return []