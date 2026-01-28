import os
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import requests
from dotenv import load_dotenv
from datetime import datetime
from moviepy import ImageSequenceClip
from PIL import Image
import logging

from .utils import download_media, load_metadata_from_file, save_metadata_to_file

logger = logging.getLogger(__name__)

# === Load environment ===
load_dotenv()

IS_LOAD_METADATA_FROM_FILE = False

SOURCE_TYPE = "website_bs"
DOWNLOAD_DIR = "downloads/website_bs"
OUTPUT_FILE = "report-output/website_bs_posts.json"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

class WebBsScrapper():
    def __init__(self):
        self.output_file = OUTPUT_FILE

    def scrape_media_from_website_bs(self, page_url, scraping_config=None):
        logger.info(f"🚀 Scraping Website: {page_url}")
        
        if IS_LOAD_METADATA_FROM_FILE:
            return load_metadata_from_file(OUTPUT_FILE)

        if scraping_config is None:
            scraping_config = {
                "selectors": {"images": "img"},
                "is_combine_image_into_video": False,
                "is_description": False,
                "filename_prefix": "default"
            }

        try:
            # Send GET request to the page_url
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(page_url, headers=headers, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"❌ Error accessing page: {response.status_code}")
                return []
            
            soup = BeautifulSoup(response.content, 'html.parser')
            downloaded_images = set()
            saved_metadata = []
            images_list = []

            # Prepare download folder
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            page_name = page_url.rstrip("/").split("/")[-1] or "home"
            folder = os.path.join(DOWNLOAD_DIR, f"{page_name}_{timestamp}")
            os.makedirs(folder, exist_ok=True)

            # Extract elements based on config
            selectors = scraping_config.get("selectors", {})
            is_combine_image_into_video = scraping_config.get("is_combine_image_into_video", False)
            is_description = scraping_config.get("is_description", False)
            filename_prefix = scraping_config.get("filename_prefix", "item")
            description_selectors = scraping_config.get("description_selectors", [])

            if "container" in selectors:
                container = soup.select_one(selectors["container"])
                if not container:
                    logger.warning(f"⚠️ Container not found: {selectors['container']}")
                    return []
                
                if "target_elements" in selectors:
                    target_elements = container.select(selectors["target_elements"])
                else:
                    target_elements = []
            else:
                if "target_elements" in selectors:
                    target_elements = soup.select(selectors["target_elements"])
                else:
                    target_elements = []

            logger.info(f"Found {len(target_elements)} target elements")

            for index, element in enumerate(target_elements, start=1):
                img_url = self._extract_image_url(element, selectors.get("image_attribute", "src"))
                
                if not img_url:
                    continue
                
                img_url = urljoin(page_url, img_url.strip())
                
                if img_url in downloaded_images:
                    continue
                downloaded_images.add(img_url)

                file_prefix = f"{filename_prefix}_{index}"
                file_path = download_media(img_url, folder, file_prefix)
                
                if file_path and is_combine_image_into_video:
                    images_list.append(file_path)

                description = ""
                if is_description:
                    description = self._extract_description(
                        element, 
                        page_url, 
                        description_selectors,
                        selectors.get("link_attribute", "href")
                    )

                saved_metadata.append({
                    "img_url": img_url,
                    "file_path": file_path,
                    "description": description,
                    "category": "image",
                    "scraped_at": datetime.now().isoformat()
                })

            # Combine images into video if requested
            if is_combine_image_into_video and images_list:
                video_path = self._combine_images_to_video(images_list, folder, filename_prefix)
                if video_path:
                    saved_metadata.append({
                        "img_url": page_url + f" Video {index}",
                        "file_path": video_path,
                        "description": "",
                        "category": "video",
                        "scraped_at": datetime.now().isoformat()
                    })

            save_metadata_to_file(saved_metadata, OUTPUT_FILE)
            logger.info(f"🏁 Website scraping completed! Saved {len(saved_metadata)} items")
            
            return saved_metadata

        except Exception as e:
            logger.error(f"❌ Website scraping failed: {e}")
            return []

    def _extract_image_url(self, element, attribute):
        """Extract image URL from element based on attribute type."""
        if attribute == "data-image":
            return element.get("data-image")
        elif attribute == "src":
            img_tag = element if element.name == "img" else element.find("img")
            if img_tag:
                return img_tag.get("src")
            # Try data-src for lazy loading
            elif element.get("data-src"):
                return element.get("data-src")
        return None

    def _extract_description(self, element, page_url, description_selectors, link_attribute):
        """Extract description by following links and parsing content."""
        parent_a = element.find_parent("a") if element.name != "a" else element
        
        if not parent_a:
            parent_a = element.find("a")
        
        if not parent_a or not parent_a.get(link_attribute):
            return ""

        link_url = urljoin(page_url, parent_a[link_attribute])
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            desc_response = requests.get(link_url, headers=headers, timeout=10)
            desc_soup = BeautifulSoup(desc_response.content, "html.parser")
            
            for selector in description_selectors:
                target_div = desc_soup.select_one(selector)
                if target_div:
                    return target_div.get_text(strip=True)
            
            main_tag = desc_soup.find("main")
            if main_tag:
                return main_tag.get_text(strip=True)
                
        except Exception as e:
            logger.warning(f"⚠️ Failed to get description from {link_url}: {e}")
        
        return ""

    def _combine_images_to_video(self, images_list, folder, filename_prefix):
        """Combine multiple images into a video."""
        if len(images_list) <= 1:
            return None

        resized = []
        try:
            target_size = None
            for i, path in enumerate(images_list):
                with Image.open(path) as img:
                    if target_size is None:
                        target_size = img.size
                    img = img.convert("RGB")
                    img = img.resize(target_size)
                    new_path = os.path.join(folder, f"resize_{i}.jpg")
                    img.save(new_path)
                    resized.append(new_path)

            # Combine into video
            clip = ImageSequenceClip(resized, fps=1)
            combined_video_path = os.path.join(folder, f"{filename_prefix}_combined_video.mp4")
            clip.write_videofile(combined_video_path, codec="libx264")
            
            logger.info(f"✅ Combined {len(images_list)} images into video")
            return combined_video_path
            
        except Exception as e:
            logger.error(f"⚠️ Error combining images to video: {e}")
            return None
        finally:
            # Cleanup temporary files
            for path in resized:
                try:
                    os.remove(path)
                except:
                    pass