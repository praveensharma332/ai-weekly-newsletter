import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.collectors.rss import RSSCollector
from app.summarizers.summarizer import ArticleSummarizerPipeline
from app.generators.generator import WeeklyNewsletterGenerator
from app.providers import get_provider
from app.clustering.embedder import SemanticEmbedder
from app.storage.database import db_session
from app.storage.models import Article
from app.utils.logger import setup_logger
from app.utils.email import send_newsletter_email

logger = logging.getLogger("newsletter.scheduler")

# Article thresholds
MIN_ARTICLES_FOR_NEWSLETTER = 3   # Absolute minimum to generate
TARGET_ARTICLES_FOR_NEWSLETTER = 20  # Ideal number - fetch more if below this

class NewsletterScheduler:
    """Manages weekly and daily scheduled runs using APScheduler."""

    def __init__(self):
        self.scheduler = BackgroundScheduler()
        # Ensure base logging is configured
        setup_logger()

    def run_newsletter_pipeline(self) -> None:
        """Executes the entire end-to-end collection, summarization, clustering, and compilation pipeline."""
        logger.info("=== STARTING SCHEDULED NEWSLETTER GENERATION RUN ===")
        start_time = datetime.now()

        try:
            # 1. Instantiate core dependencies
            llm = get_provider("gemini")
            embedder = SemanticEmbedder()
            generator = WeeklyNewsletterGenerator(llm_provider=llm, embedder=embedder)

            # 2. Check existing unused articles in DB first
            unused_count = db_session.query(Article).filter(Article.is_used == False).count()
            logger.info(f"Found {unused_count} unused articles already in database.")

            # 3. Fetch new articles if below target threshold
            if unused_count < TARGET_ARTICLES_FOR_NEWSLETTER:
                logger.info(f"Below target ({unused_count} < {TARGET_ARTICLES_FOR_NEWSLETTER}). Fetching new articles to supplement...")
                collector = RSSCollector()
                pipeline = ArticleSummarizerPipeline(llm_provider=llm, embedder=embedder)
                
                raw_items = collector.collect()
                if raw_items:
                    new_articles = pipeline.process_collected_articles(raw_items)
                    logger.info(f"Processed {len(new_articles)} new articles during this run.")
                elif unused_count < MIN_ARTICLES_FOR_NEWSLETTER:
                    logger.warning("No feed items collected and insufficient articles in DB. Aborting.")
                    return
                else:
                    logger.warning(f"No new feed items, but {unused_count} existing articles available. Proceeding.")
            else:
                logger.info(f"Sufficient unused articles in DB ({unused_count} >= {TARGET_ARTICLES_FOR_NEWSLETTER}). Skipping RSS fetch.")

            # 4. Synthesize and compile newsletter
            newsletter = generator.generate_weekly_newsletter(dry_run=False)
            
            if newsletter:
                logger.info(f"Successfully compiled newsletter issue: '{newsletter.title}'")
                
                # 5. Dispatch email if SMTP configured
                subject = f"AI Weekly Engineering Brief: {newsletter.title}"
                # Path to HTML version
                from app.config.settings import settings
                date_str = newsletter.issue_date.strftime("%Y-%m-%d")
                html_path = settings.NEWSLETTERS_DIR / date_str / "newsletter.html"
                
                email_sent = send_newsletter_email(
                    subject=subject,
                    html_content=newsletter.content_html,
                    attachment_path=str(html_path)
                )
                if email_sent:
                    logger.info("Newsletter successfully dispatched via email.")
            else:
                logger.warning("No newsletter generated (insufficient unused articles in DB).")

        except Exception as e:
            logger.exception(f"Critical failure during scheduled pipeline execution: {e}")

        duration = datetime.now() - start_time
        logger.info(f"=== NEWSLETTER PIPELINE RUN COMPLETED IN {duration} ===")

    def start(self) -> None:
        """Starts background scheduler and configs weekly run (every Monday at 9AM)."""
        if self.scheduler.running:
            logger.warning("Scheduler is already running.")
            return

        # 1. Add weekly job: Monday 9:00 AM
        weekly_trigger = CronTrigger(day_of_week="mon", hour=9, minute=0)
        self.scheduler.add_job(
            self.run_newsletter_pipeline,
            trigger=weekly_trigger,
            id="weekly_newsletter_job",
            name="Weekly Newsletter Fetch & Compile",
            replace_existing=True
        )
        logger.info("Scheduled weekly newsletter job for Mondays at 9:00 AM.")

        # 2. Start scheduler
        self.scheduler.start()
        logger.info("Background scheduler started successfully.")

    def stop(self) -> None:
        """Stops background scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler shut down successfully.")
