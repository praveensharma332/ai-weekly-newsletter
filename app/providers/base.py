from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseLLMProvider(ABC):
    """Abstract Base Class for LLM providers."""

    @abstractmethod
    def generate_summary(self, text: str, max_words: int = 150) -> str:
        """Generates a concise summary for a single article."""
        pass

    @abstractmethod
    def categorize_article(self, title: str, summary: str) -> str:
        """Categorizes an article into standard categories:
        - "Major AI Model Developments"
        - "Infrastructure & Hardware"
        - "AI Agents / MCP / Tooling"
        - "Enterprise AI"
        - "Open Source & Research"
        - "General AI News"
        """
        pass

    @abstractmethod
    def synthesize_cluster(self, topic: str, articles: List[Dict[str, Any]]) -> str:
        """Synthesizes a combined summary and key insights for a cluster of similar articles."""
        pass

    @abstractmethod
    def generate_educational_section(self, topic: str) -> str:
        """Generates a technically accurate, engineering-focused educational section for the newsletter."""
        pass

    @abstractmethod
    def generate_newsletter(self, clustered_articles: List[Dict[str, Any]], educational_section: str) -> Dict[str, Any]:
        """Synthesizes clustered topics and the educational section into a finalized newsletter.
        Returns a dict with keys: 'title', 'tldr', 'sections' (dict of category -> markdown content), and 'final_outlook'.
        """
        pass
