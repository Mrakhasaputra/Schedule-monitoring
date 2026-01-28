import os
import requests
import json
from datetime import datetime
from urllib.parse import urlparse

def download_media(url, folder, filename_prefix):
    """Download media from URL"""
    try:
        if not url:
            return None
        
        # Extract file extension
        parsed = urlparse(url)
        path = parsed.path
        ext = os.path.splitext(path)[1] if os.path.splitext(path)[1] else '.jpg'
        
        # Clean filename
        clean_filename = filename_prefix.replace('/', '_').replace('\\', '_')
        filename = f"{clean_filename}{ext}"
        filepath = os.path.join(folder, filename)
        
        # Download
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print(f"✅ Downloaded: {filename}")
        return filepath
        
    except Exception as e:
        print(f"❌ Failed to download {url}: {e}")
        return None

def load_metadata_from_file(filepath):
    """Load metadata from JSON file"""
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"❌ Failed to load metadata: {e}")
    return []

def save_metadata_to_file(data, filepath):
    """Save metadata to JSON file"""
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"💾 Metadata saved to: {filepath}")
    except Exception as e:
        print(f"❌ Failed to save metadata: {e}")

def parse_flexible_timestamp(timestamp_str):
    """Parse flexible timestamp string"""
    if not timestamp_str:
        return None
    
    formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M:%S",
        "%d-%m-%Y %H:%M:%S"
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(timestamp_str, fmt)
        except:
            continue
    
    return None