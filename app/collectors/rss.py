import time
import yaml
import logging
import feedparser
import httpx
from datetime import datetime
from typing import List, Dict, Any, Optional

from app.collectors.base import BaseCollector
from app.config.settings import settings

logger = logging.getLogger("newsletter.collectors.rss")

class RSSCollector(BaseCollector):
    """RSS Feed Collector using feedparser."""

    def __init__(self, sources_file_path: Optional[str] = None):
        if sources_file_path is None:
            self.sources_file = settings.PROJECT_ROOT / "sources.yaml"
        else:
            self.sources_file = Path(sources_file_path)
            
        self.sources = self._load_sources()

    def _load_sources(self) -> Dict[str, Any]:
        """Loads and parses the sources.yaml file."""
        if not self.sources_file.exists():
            logger.error(f"Sources file not found at {self.sources_file}. Returning empty sources dict.")
            return {"sources": {}}
            
        try:
            with open(self.sources_file, "r") as f:
                return yaml.safe_load(f) or {"sources": {}}
        except Exception as e:
            logger.error(f"Failed to load sources.yaml: {e}")
            return {"sources": {}}

    def collect(self) -> List[Dict[str, Any]]:
        """Iterates over feeds, downloads and parses feed items."""
        all_articles = []
        sources_dict = self.sources.get("sources", {})
        
        # Merge all categories of sources into a single list of tuples (category, source_info)
        feed_items = []
        for category, sources in sources_dict.items():
            for src in sources:
                if src.get("type") == "rss":
                    feed_items.append((category, src))

        logger.info(f"Starting collection from {len(feed_items)} RSS feed sources...")

        for category, src in feed_items:
            name = src.get("name", "Unknown Source")
            url = src.get("url")
            headers = src.get("headers", {})

            if not url:
                continue

            logger.info(f"Fetching RSS feed: {name} ({url})...")
            try:
                # Use custom headers (crucial for Reddit feeds)
                if headers:
                    with httpx.Client(headers=headers, timeout=20.0, follow_redirects=True) as client:
                        response = client.get(url)
                        response.raise_for_status()
                        feed_data = feedparser.parse(response.content)
                else:
                    # Feedparser standard download
                    feed_data = feedparser.parse(url)

                if not feed_data.entries:
                    logger.warning(f"No feed entries found for {name}.")
                    continue

                logger.info(f"Successfully fetched {len(feed_data.entries)} entries from {name}.")
                
                # Limit to latest 10 items per feed per run to avoid overload and API exhaustion
                for entry in feed_data.entries[:10]:
                    title = entry.get("title", "Untitled")
                    link = entry.get("link")
                    
                    if not link:
                        continue

                    # Parse publishing date
                    pub_date = datetime.utcnow()
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        try:
                            pub_date = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                        except Exception:
                            pass
                    elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                        try:
                            pub_date = datetime.fromtimestamp(time.mktime(entry.updated_parsed))
                        except Exception:
                            pass

                    # Extract description or summary
                    raw_content = entry.get("summary", "")
                    if not raw_content and hasattr(entry, "description"):
                        raw_content = entry.description
                    if not raw_content and hasattr(entry, "content"):
                        raw_content = entry.content[0].value if entry.content else ""

                    article = {
                        "title": title,
                        "source": name,
                        "url": link,
                        "publish_date": pub_date,
                        "raw_content": raw_content or title,
                        "category_feed": category
                    }
                    all_articles.append(article)

            except Exception as e:
                logger.error(f"Failed to fetch or parse feed {name}: {e}")
                continue

        logger.info(f"RSS collection completed. Collected {len(all_articles)} total raw items.")
        
        # IMPORTANT: Limit total articles to avoid API quota exhaustion
        # Sort by publish date (most recent first) and take top 30
        MAX_ARTICLES_PER_RUN = 30
        if len(all_articles) > MAX_ARTICLES_PER_RUN:
            all_articles.sort(key=lambda x: x.get("publish_date", datetime.min), reverse=True)
            all_articles = all_articles[:MAX_ARTICLES_PER_RUN]
            logger.info(f"Limited to {MAX_ARTICLES_PER_RUN} most recent articles to respect API quotas.")
        
        return all_articles
