import httpx
import logging
from bs4 import BeautifulSoup
from typing import Optional

from app.utils.clean import clean_html

logger = logging.getLogger("newsletter.collectors.scraper")

class WebScraper:
    """Robust web page scraper to extract article bodies and strip boilerplate."""

    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5"
        }

    def scrape(self, url: str) -> Optional[str]:
        """Downloads and extracts clean article body text from a URL."""
        logger.info(f"Scraping content from URL: {url}...")
        
        # Avoid scraping pdfs or reddit links directly unless they are article pages
        if url.endswith(".pdf"):
            logger.info("Skipping scraping: PDF file detected.")
            return None
            
        try:
            with httpx.Client(headers=self.headers, timeout=25.0, follow_redirects=True) as client:
                response = client.get(url)
                if response.status_code != 200:
                    logger.warning(f"Failed to fetch {url}. Status code: {response.status_code}")
                    return None
                    
                html = response.text
                
            soup = BeautifulSoup(html, "html.parser")
            
            # Try to identify main article container
            article_body = None
            
            # Common article container tags
            candidates = [
                soup.find("article"),
                soup.find(attrs={"itemprop": "articleBody"}),
                soup.find(id="article-body"),
                soup.find(class_="article-body"),
                soup.find(class_="post-content"),
                soup.find(class_="entry-content"),
                soup.find(class_="main-content"),
                soup.find(id="main-content")
            ]
            
            for candidate in candidates:
                if candidate:
                    article_body = candidate
                    break
                    
            # Fallback to broad body if no specific article container is found
            if not article_body:
                article_body = soup.find("body") or soup
                
            cleaned_text = clean_html(str(article_body))
            
            if len(cleaned_text.strip()) < 100:
                # If parsed article is too short, try raw soup text as a final fallback
                cleaned_text = clean_html(html)
                
            logger.info(f"Successfully scraped and cleaned {len(cleaned_text)} characters from {url}.")
            return cleaned_text
            
        except Exception as e:
            logger.error(f"Scraper failed for URL {url}: {e}")
            return None
