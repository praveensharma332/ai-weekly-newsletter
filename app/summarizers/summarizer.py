import logging
from typing import List, Dict, Any

from app.storage.database import db_session
from app.storage.models import Article
from app.providers.base import BaseLLMProvider
from app.collectors.scraper import WebScraper
from app.clustering.embedder import SemanticEmbedder
from app.utils.clean import generate_dedup_hash

logger = logging.getLogger("newsletter.summarizers.summarizer")

class ArticleSummarizerPipeline:
    """Orchestrates content scraping, summarization, categorization, embedding generation, and DB storage."""

    def __init__(self, llm_provider: BaseLLMProvider, embedder: SemanticEmbedder):
        self.llm = llm_provider
        self.embedder = embedder
        self.scraper = WebScraper()

    def process_collected_articles(self, raw_items: List[Dict[str, Any]]) -> List[Article]:
        """Takes raw collected feed items, deduplicates, scrapes full content if needed, summarizes, embeds, and saves to DB."""
        processed_articles = []
        
        logger.info(f"Processing {len(raw_items)} raw feed items...")

        for idx, item in enumerate(raw_items):
            title = item.get("title", "Untitled").strip()
            url = item.get("url", "").strip()
            source = item.get("source", "Unknown").strip()
            publish_date = item.get("publish_date")
            raw_summary = item.get("raw_content", "")

            if not url or not title:
                continue

            # 1. Compute stable deduplication hash
            dedup_hash = generate_dedup_hash(title, url)

            # 2. Check SQLite for duplicates instantly
            existing_db_article = db_session.query(Article).filter(Article.hash == dedup_hash).first()
            if existing_db_article:
                logger.debug(f"Article already exists in DB (skipping): '{title}'")
                continue

            logger.info(f"[{idx+1}/{len(raw_items)}] Processing new article: '{title}' ({source})...")

            # 3. Scrape full content as fallback if feed is too short (less than 600 chars)
            scraped_content = ""
            if len(raw_summary) < 600:
                logger.info(f"Feed description too short ({len(raw_summary)} chars). Attempting to scrape full article page...")
                scraped_content = self.scraper.scrape(url) or ""

            full_content = scraped_content if len(scraped_content) > len(raw_summary) else raw_summary
            
            if len(full_content.strip()) < 100:
                logger.warning(f"Insufficient text content extracted for '{title}'. Skipping summarization.")
                continue

            # 4. Generate summary using LLM
            logger.info(f"Generating summary via LLM for '{title}'...")
            summary = self.llm.generate_summary(full_content)

            # 5. Categorize article
            logger.info(f"Categorizing article: '{title}'...")
            category = self.llm.categorize_article(title, summary)

            # 6. Compute semantic embedding
            logger.info(f"Computing semantic embedding vector...")
            embedding_vector = self.embedder.embed_text(summary)

            # 7. Create Article DB model and persist
            try:
                db_article = Article(
                    title=title,
                    source=source,
                    url=url,
                    publish_date=publish_date,
                    cleaned_content=full_content,
                    summary=summary,
                    category=category,
                    hash=dedup_hash
                )
                if embedding_vector:
                    db_article.embedding = embedding_vector
                    
                db_session.add(db_article)
                db_session.commit()
                processed_articles.append(db_article)
                logger.info(f"Successfully processed and stored article: '{title}' -> Category: '{category}'")
            except Exception as e:
                db_session.rollback()
                logger.error(f"Failed to store article '{title}' in database: {e}")

        logger.info(f"Summarizer pipeline execution finished. Successfully stored {len(processed_articles)} new articles.")
        return processed_articles
