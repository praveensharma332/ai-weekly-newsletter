import os
import json
import logging
import random
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape
import markdown

from app.storage.database import db_session
from app.storage.models import Article, Newsletter
from app.providers.base import BaseLLMProvider
from app.clustering.embedder import SemanticEmbedder
from app.config.settings import settings

logger = logging.getLogger("newsletter.generators.generator")

class WeeklyNewsletterGenerator:
    """Orchestrates clustering, synthesis, compilation, and file output of weekly newsletters."""

    def __init__(self, llm_provider: BaseLLMProvider, embedder: SemanticEmbedder):
        self.llm = llm_provider
        self.embedder = embedder
        
        # Configure Jinja2 environment with auto-escaping for HTML
        template_dir = settings.APP_DIR / "templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html", "xml"])
        )

        self.educational_topics = [
            "KV Cache", "Retrieval-Augmented Generation (RAG)", "Attention Mechanism",
            "Model Quantization", "Model Context Protocol (MCP)", "Vector Databases",
            "GPU Memory Layout", "Mixture of Experts (MoE)", "AI Agents & Tooling",
            "Prompt Caching", "LoRA & QLoRA", "Supervised Fine-Tuning"
        ]

    def _select_educational_topic(self, articles: List[Article]) -> str:
        """Selects a highly relevant educational topic based on this week's articles."""
        combined_text = " ".join([a.title + " " + (a.summary or "") for a in articles]).lower()
        
        # Look for keywords to match an educational topic
        topic_keywords = {
            "KV Cache": ["cache", "kv", "inference speed", "generation speed"],
            "Retrieval-Augmented Generation (RAG)": ["rag", "retrieval", "search", "vector db", "knowledge database"],
            "Attention Mechanism": ["attention", "transformer", "self-attention", "flashattention"],
            "Model Quantization": ["quantization", "quantize", "int8", "fp4", "awq", "gptq"],
            "Model Context Protocol (MCP)": ["mcp", "protocol", "context protocol", "agent connector"],
            "Vector Databases": ["vector database", "pinecone", "milvus", "qdrant", "chroma"],
            "GPU Memory Layout": ["gpu", "vram", "hbm", "a100", "h100", "memory bandwidth"],
            "Mixture of Experts (MoE)": ["moe", "mixture of experts", "experts", "sparse model"],
            "AI Agents & Tooling": ["agent", "agents", "tool use", "function calling", "autogen", "crewai"],
            "Prompt Caching": ["prompt cache", "caching", "anthropic cache", "context caching"],
            "LoRA & QLoRA": ["lora", "qlora", "peft", "adapter", "parameter efficient"],
            "Supervised Fine-Tuning": ["fine-tuning", "sft", "rlhf", "dpo", "alignment"]
        }

        scored_topics = []
        for topic, keywords in topic_keywords.items():
            score = sum([combined_text.count(kw) for kw in keywords])
            scored_topics.append((topic, score))

        # Sort by score descending
        scored_topics.sort(key=lambda x: x[1], reverse=True)
        
        if scored_topics[0][1] > 0:
            logger.info(f"Automatically selected highly relevant educational topic: {scored_topics[0][0]}")
            return scored_topics[0][0]
            
        selected = random.choice(self.educational_topics)
        logger.info(f"No clear topic keywords found. Randomly selected educational topic: {selected}")
        return selected

    def generate_weekly_newsletter(self, dry_run: bool = False) -> Optional[Newsletter]:
        """Collects articles from current week, clusters them, synthesizes summaries, compiles and archives the newsletter."""
        # 1. Fetch articles from the current week (last 7 days) - reusable within the same week
        from datetime import datetime, timedelta
        week_ago = datetime.now() - timedelta(days=7)
        
        weekly_articles = db_session.query(Article).filter(
            Article.created_at >= week_ago
        ).order_by(Article.created_at.desc()).all()
        
        # Fallback: if no recent articles, try unused articles from any time
        if len(weekly_articles) < 3:
            logger.info("Not enough articles from this week. Checking all unused articles...")
            weekly_articles = db_session.query(Article).filter(Article.is_used == False).all()
        
        if len(weekly_articles) < 3:
            logger.warning(f"Only {len(weekly_articles)} articles found in DB. AI generation requires at least 3 articles. Skipping generation.")
            return None

        logger.info(f"Retrieved {len(weekly_articles)} articles from this week for newsletter compilation.")

        # 2. Select educational topic
        edu_topic = self._select_educational_topic(weekly_articles)
        logger.info(f"Generating educational section for '{edu_topic}'...")
        educational_html_markdown = self.llm.generate_educational_section(edu_topic)

        # Convert list of Article ORM models to raw dict list for embedder/clustering
        articles_data = [art.to_dict() for art in weekly_articles]
        for idx, art in enumerate(articles_data):
            art["embedding"] = weekly_articles[idx].embedding

        # 3. Cluster articles and synthesize
        # Group articles by category
        by_category = {}
        for art in articles_data:
            cat = art.get("category") or "General AI News"
            by_category.setdefault(cat, []).append(art)

        synthesized_batch = []
        
        for category, items in by_category.items():
            logger.info(f"Clustering and synthesizing category '{category}' with {len(items)} articles...")
            
            # If a category has multiple articles, cluster them semantically
            if len(items) >= 3:
                clusters = self.embedder.cluster_articles(items)
                for cluster in clusters:
                    if len(cluster) == 1:
                        # Single article cluster, summary acts as synthesis
                        art = cluster[0]
                        art["synthesis"] = art.get("summary")
                        synthesized_batch.append(art)
                    else:
                        # Multiple articles in cluster, run LLM synthesis
                        representative = cluster[0]
                        topic_title = representative.get("title")
                        logger.info(f"Synthesizing cluster of {len(cluster)} articles represented by '{topic_title}'...")
                        synthesis_text = self.llm.synthesize_cluster(topic_title, cluster)
                        
                        # Create a merged synthetic article item
                        merged = {
                            "title": f"Trend: {topic_title} (and others)",
                            "source": ", ".join(list(set([a.get("source") for a in cluster]))),
                            "url": representative.get("url"),
                            "summary": representative.get("summary"),
                            "synthesis": synthesis_text,
                            "category": category
                        }
                        synthesized_batch.append(merged)
            else:
                # 1 or 2 items: no clustering needed, copy summary to synthesis
                for art in items:
                    art["synthesis"] = art.get("summary")
                    synthesized_batch.append(art)

        # 4. Generate final newsletter structure using LLM
        logger.info("Compiling final structured newsletter using LLM...")
        newsletter_payload = self.llm.generate_newsletter(synthesized_batch, educational_html_markdown)

        title = newsletter_payload.get("title", "AI Weekly Engineering Briefing")
        tldr = newsletter_payload.get("tldr", "")
        sections = newsletter_payload.get("sections", {})
        final_outlook = newsletter_payload.get("final_outlook", "")

        # 5. Assemble Markdown
        md_content = f"# {title}\n\n"
        md_content += f"## Executive Summary & TL;DR\n\n{tldr}\n\n"
        
        for category, content in sections.items():
            if content.strip():
                md_content += f"## {category}\n\n{content}\n\n"

        md_content += f"## Final Outlook\n\n{final_outlook}\n\n"

        # 6. Render HTML using Jinja2 Template
        try:
            template = self.jinja_env.get_template("newsletter.html")
            
            # Convert markdown sections to HTML for insertion in template
            html_sections = {}
            for cat, md in sections.items():
                if md.strip():
                    html_sections[cat] = markdown.markdown(md, extensions=["extra", "codehilite"])
                    
            html_tldr = markdown.markdown(tldr, extensions=["extra"])
            html_outlook = markdown.markdown(final_outlook, extensions=["extra"])
            
            issue_date_str = date.today().strftime("%B %d, %Y")
            
            html_content = template.render(
                title=title,
                issue_date=issue_date_str,
                tldr=html_tldr,
                sections=html_sections,
                final_outlook=html_outlook,
                edu_topic=edu_topic
            )
        except Exception as e:
            logger.error(f"HTML Template rendering failed: {e}")
            # Fallback to basic HTML conversion of markdown content
            html_content = f"<html><body>{markdown.markdown(md_content)}</body></html>"

        if dry_run:
            logger.info("Dry run enabled. Skipping database persistence and file writes.")
            # Print sample to log
            logger.info(f"Dry Run Generated: {title}")
            return None

        # 7. Write to Local Filesystem under YYYY-MM-DD
        current_date_str = date.today().strftime("%Y-%m-%d")
        output_dir = settings.NEWSLETTERS_DIR / current_date_str
        output_dir.mkdir(parents=True, exist_ok=True)

        md_path = output_dir / "newsletter.md"
        html_path = output_dir / "newsletter.html"
        json_path = output_dir / "newsletter.json"

        # Protection: ensure paths do not escape the newsletter directory (Path traversal prevention)
        # Dates generated as %Y-%m-%d are strictly alpha-numeric and hyphens, preventing traversal.
        
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(newsletter_payload, f, indent=2, ensure_ascii=False)

        logger.info(f"Newsletter files saved to {output_dir}")

        # 8. Store in Database
        try:
            db_newsletter = Newsletter(
                issue_date=date.today(),
                title=title,
                tldr=tldr,
                content_markdown=md_content,
                content_html=html_content,
                raw_json_data=json.dumps(newsletter_payload, ensure_ascii=False)
            )
            db_session.add(db_newsletter)
            
            # 9. Mark articles as used
            for art in weekly_articles:
                art.is_used = True
                
            db_session.commit()
            logger.info("Newsletter registered and articles marked as used in DB.")
            return db_newsletter
        except Exception as e:
            db_session.rollback()
            logger.error(f"Failed to save newsletter to database: {e}")
            return None
