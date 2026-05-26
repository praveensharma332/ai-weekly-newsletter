import httpx
import json
import logging
from typing import List, Dict, Any, Optional

from app.providers.base import BaseLLMProvider
from app.config.settings import settings

logger = logging.getLogger("newsletter.providers.ollama")

class OllamaProvider(BaseLLMProvider):
    """Local Ollama LLM Provider (Fallback)."""

    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model_name = settings.OLLAMA_MODEL

    def _call_ollama(self, prompt: str, system_instruction: Optional[str] = None, json_mode: bool = False) -> str:
        """Helper to invoke local Ollama server endpoint."""
        url = f"{self.base_url.rstrip('/')}/api/generate"
        
        full_prompt = prompt
        if system_instruction:
            full_prompt = f"System: {system_instruction}\n\nUser: {prompt}"

        payload = {
            "model": self.model_name,
            "prompt": full_prompt,
            "stream": False
        }
        if json_mode:
            payload["format"] = "json"

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("response", "").strip()
        except Exception as e:
            logger.error(f"Ollama API call failed: {e}")
            raise RuntimeError(f"Ollama API call failed: {e}")

    def generate_summary(self, text: str, max_words: int = 150) -> str:
        """Summarizes a single article using Ollama."""
        prompt = (
            f"Summarize this AI engineering article under {max_words} words. Focus strictly on technical "
            f"details, architectural designs, and performance results. Avoid marketing fluff.\n\n"
            f"Article content:\n{text}"
        )
        try:
            return self._call_ollama(prompt, system_instruction="You are an expert AI software engineer.")
        except Exception:
            return text[:400] + "..."

    def categorize_article(self, title: str, summary: str) -> str:
        """Categorizes an article into standard categories using Ollama."""
        prompt = (
            "Select exactly one category for this article from:\n"
            "- Major AI Model Developments\n"
            "- Infrastructure & Hardware\n"
            "- AI Agents / MCP / Tooling\n"
            "- Enterprise AI\n"
            "- Open Source & Research\n"
            "- General AI News\n\n"
            "Provide ONLY the category name. Do not explain.\n\n"
            f"Title: {title}\nSummary: {summary}"
        )
        try:
            res = self._call_ollama(prompt, system_instruction="You are a strict categorization module.")
            res = res.strip('`"\' ')
            valid_categories = [
                "Major AI Model Developments",
                "Infrastructure & Hardware",
                "AI Agents / MCP / Tooling",
                "Enterprise AI",
                "Open Source & Research",
                "General AI News"
            ]
            for vc in valid_categories:
                if vc.lower() in res.lower():
                    return vc
            return "General AI News"
        except Exception:
            return "General AI News"

    def synthesize_cluster(self, topic: str, articles: List[Dict[str, Any]]) -> str:
        """Synthesizes a combined summary for a cluster of similar articles using Ollama."""
        articles_text = ""
        for i, art in enumerate(articles):
            articles_text += f"Article [{i+1}]: {art.get('title')}\nSummary: {art.get('summary')}\n\n"

        prompt = (
            f"Analyze these articles regarding '{topic}' and synthesize a cohesive engineering "
            f"update. Explain the technical implications for AI development.\n\n"
            f"Articles:\n{articles_text}"
        )
        try:
            return self._call_ollama(prompt, system_instruction="You are a senior technical writer.")
        except Exception:
            return f"Topic: {topic} - Synthesized updates from multiple sources."

    def generate_educational_section(self, topic: str) -> str:
        """Generates a technically accurate, engineering-focused educational section using Ollama."""
        prompt = (
            f"Create a deep-dive educational section on '{topic}'. Focus on technical mechanics, "
            f"GPU memory overhead, optimization math, and architectural bottlenecks.\n\n"
            f"Use three headings:\n"
            f"1. **The Core Concept**\n"
            f"2. **How It Works**\n"
            f"3. **Engineering Considerations**"
        )
        try:
            return self._call_ollama(prompt, system_instruction="You are a Principal Architect.")
        except Exception:
            return f"### Educational Spotlight: {topic}\n\nCould not generate local educational spotlight."

    def generate_newsletter(self, clustered_articles: List[Dict[str, Any]], educational_section: str) -> Dict[str, Any]:
        """Synthesizes clustered topics and the educational section into a finalized newsletter using Ollama."""
        categories_dict = {}
        for item in clustered_articles:
            cat = item.get("category", "General AI News")
            categories_dict.setdefault(cat, []).append(item)

        developments_text = ""
        for cat, items in categories_dict.items():
            developments_text += f"## CATEGORY: {cat}\n\n"
            for it in items:
                developments_text += f"### {it.get('title')} (Source: {it.get('source')})\n"
                developments_text += f"URL: {it.get('url')}\n"
                developments_text += f"Summary: {it.get('summary')}\n\n"

        prompt = (
            "Given these developments and an educational piece, synthesize a Weekly AI Engineering Newsletter. "
            "Respond in JSON format with exact keys: 'title', 'tldr', 'sections' (dictionary mapping category -> markdown content), and 'final_outlook'.\n\n"
            f"Developments:\n{developments_text}\n\n"
            f"Educational Spotlight:\n{educational_section}"
        )
        try:
            res = self._call_ollama(prompt, system_instruction="You are an editor outputting JSON only.", json_mode=True)
            return json.loads(res)
        except Exception:
            return {
                "title": "AI Weekly Engineering Briefing (Ollama)",
                "tldr": "Weekly summary of latest AI advancements using local LLMs.",
                "sections": {cat: "\n\n".join([f"- [{it.get('title')}]({it.get('url')}): {it.get('summary')}" for it in items]) for cat, items in categories_dict.items()},
                "final_outlook": "Ongoing technological acceleration observed this week."
            }
