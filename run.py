import argparse
import sys
import time
import uvicorn
import logging

from app.storage.database import init_db, db_session
from app.storage.models import Article
from app.utils.logger import setup_logger
from app.providers import get_provider
from app.clustering.embedder import SemanticEmbedder
from app.collectors.rss import RSSCollector
from app.summarizers.summarizer import ArticleSummarizerPipeline
from app.generators.generator import WeeklyNewsletterGenerator
from app.scheduler.scheduler import NewsletterScheduler
from app.utils.email import send_newsletter_email
from app.utils.slack import send_slack_notification
from app.config.settings import settings

# Article thresholds
MIN_ARTICLES_FOR_NEWSLETTER = 3   # Absolute minimum to generate
TARGET_ARTICLES_FOR_NEWSLETTER = 20  # Ideal number - fetch more if below this

# Initialize base logging
setup_logger()
logger = logging.getLogger("newsletter.cli")

def run_pipeline(dry_run: bool = False) -> None:
    """Executes the end-to-end fetching, summarizing, and compilation pipeline manually."""
    logger.info(f"Starting newsletter compilation pipeline (Dry-run: {dry_run})...")
    
    # 1. Validate environment setup
    if not settings.validate():
        logger.warning("GEMINI_API_KEY is not configured in your .env file.")
        logger.warning("Please configure GEMINI_API_KEY to run the AI features.")
        logger.info("Proceeding using mock/offline fallbacks where possible...")

    # 2. Instantiate core modules
    try:
        llm = get_provider("gemini")
        embedder = SemanticEmbedder()
        generator = WeeklyNewsletterGenerator(llm_provider=llm, embedder=embedder)
    except Exception as e:
        logger.critical(f"Failed to initialize core modules: {e}")
        sys.exit(1)

    # 3. Check existing unused articles in DB first
    unused_count = db_session.query(Article).filter(Article.is_used == False).count()
    logger.info(f"Found {unused_count} unused articles already in database.")

    # 4. Fetch new articles if below target threshold
    if unused_count < TARGET_ARTICLES_FOR_NEWSLETTER:
        logger.info(f"Below target ({unused_count} < {TARGET_ARTICLES_FOR_NEWSLETTER}). Fetching new articles to supplement...")
        collector = RSSCollector()
        pipeline = ArticleSummarizerPipeline(llm_provider=llm, embedder=embedder)
        
        raw_items = collector.collect()
        if raw_items:
            new_articles = pipeline.process_collected_articles(raw_items)
            logger.info(f"Successfully processed {len(new_articles)} new articles.")
        elif unused_count < MIN_ARTICLES_FOR_NEWSLETTER:
            logger.warning("No feed items collected and insufficient articles in DB. Cannot generate newsletter.")
            return
        else:
            logger.warning(f"No new feed items, but {unused_count} existing articles available. Proceeding with those.")
    else:
        logger.info(f"Sufficient unused articles in DB ({unused_count} >= {TARGET_ARTICLES_FOR_NEWSLETTER}). Skipping RSS fetch.")

    # 5. Compile and generate newsletter
    newsletter = generator.generate_weekly_newsletter(dry_run=dry_run)
    
    if newsletter:
        logger.info("====================================================")
        logger.info(f"NEWSLETTER COMPILED SUCCESSFULLY: '{newsletter.title}'")
        logger.info("====================================================")
        
        # 6. Attempt email dispatch if not dry-run
        if not dry_run:
            subject = f"AI Weekly Engineering Brief: {newsletter.title}"
            date_str = newsletter.issue_date.strftime("%Y-%m-%d")
            html_path = settings.NEWSLETTERS_DIR / date_str / "newsletter.html"
            
            send_newsletter_email(
                subject=subject,
                html_content=newsletter.content_html,
                attachment_path=str(html_path)
            )
            
            # Send Slack notification
            send_slack_notification(
                title=newsletter.title,
                tldr=newsletter.tldr or "",
                issue_date=date_str
            )
    else:
        logger.warning("No newsletter briefing compiled this run (insufficient unused articles in DB).")
        logger.info("Add new articles or fetch newer feed posts to trigger compilation.")

def start_scheduler_service() -> None:
    """Launches the scheduler service and keeps the main thread alive."""
    logger.info("Starting background scheduler service...")
    scheduler = NewsletterScheduler()
    try:
        scheduler.start()
        logger.info("Scheduler service running. Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Stopping scheduler service...")
        scheduler.stop()
        logger.info("Scheduler service stopped.")
    except Exception as e:
        logger.critical(f"Scheduler service crashed: {e}")

def main() -> None:
    """CLI routing entry point."""
    parser = argparse.ArgumentParser(
        description="AI Weekly Newsletter Generator Command Line Console",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Define mutual exclusions for execution modes
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--weekly", action="store_true", help="Manually run the weekly briefing generation pipeline")
    group.add_argument("--daily", action="store_true", help="Manually run the daily brief generation pipeline")
    group.add_argument("--dry-run", action="store_true", help="Test-run the weekly pipeline without writing files or updating database")
    group.add_argument("--schedule", action="store_true", help="Launch the background scheduler service indefinitely")

    args = parser.parse_args()

    # 1. Initialize SQLite Database
    logger.info("Initializing database...")
    init_db()

    # 2. Route Execution based on CLI args
    if args.weekly or args.daily:
        run_pipeline(dry_run=False)
    elif args.dry_run:
        run_pipeline(dry_run=True)
    elif args.schedule:
        start_scheduler_service()
    else:
        # Default: Launch local management dashboard
        logger.info("Starting local management console dashboard on 127.0.0.1:8000...")
        uvicorn.run("app.main:app", host="127.0.0.1", port=8000, log_level="info")

if __name__ == "__main__":
    main()
