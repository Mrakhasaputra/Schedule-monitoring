"""
Scrapers package - Import semua scraper
"""

import os
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Import semua scraper
try:
    from .facebook import FacebookScrapper
    from .instagram import InstagramScrapper
    from .tiktok import TikTokScrapper
    from .youtube import YoutubeScrapper
    from .x import XScrapper
    from .website_bs import WebBsScrapper
    
    __all__ = [
        'FacebookScrapper',
        'InstagramScrapper',
        'TikTokScrapper',
        'YoutubeScrapper',
        'XScrapper',
        'WebBsScrapper'
    ]
    
except ImportError as e:
    print(f"⚠️ Warning: Could not import some scrapers: {e}")
    # Define placeholder classes
    class BaseScraper:
        def __init__(self):
            pass
    
    FacebookScrapper = BaseScraper
    InstagramScrapper = BaseScraper
    TikTokScrapper = BaseScraper
    YoutubeScrapper = BaseScraper
    XScrapper = BaseScraper
    WebBsScrapper = BaseScraper