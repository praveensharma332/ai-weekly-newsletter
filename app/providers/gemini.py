import time
import json
import logging
from typing import List, Dict, Any, Optional
import google.generativeai as genai
from google.generativeai.types import GenerationConfig

from app.providers.base import BaseLLMProvider
from app.config.settings import settings

logger = logging.getLogger("newsletter.providers.gemini")

class GeminiProvider(BaseLLMProvider):
    """Google Gemini LLM Provider."""

    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.model_name = settings.GEMINI_MODEL
        self.fallback_model_name = settings.GEMINI_FALLBACK_MODEL
        
        if self.api_key:
            genai.configure(api_key=self.api_key)
        else:
            logger.warning("Gemini API key is not configured. Running in offline/mock mode.")

    def _load_prompt(self, filename: str, default_prompt: str) -> str:
        """Loads a prompt from app/prompts/ directory with a default fallback."""
        prompt_path = settings.APP_DIR / "prompts" / filename
        if prompt_path.exists():
            try:
                return prompt_path.read_text(encoding="utf-8").strip()
            except Exception as e:
                logger.error(f"Error reading prompt file {filename}: {e}")
        return default_prompt

    def _call_gemini_with_retry(self, prompt: str, system_instruction: Optional[str] = None, json_mode: bool = False, max_retries: int = 3) -> str:
        """Calls Gemini API with retries and exponential backoff."""
        if not self.api_key:
            logger.error("Attempted Gemini API call but GEMINI_API_KEY is missing.")
            raise ValueError("GEMINI_API_KEY is not set. Please set it in your .env file.")

        model_to_use = self.model_name
        
        for attempt in range(max_retries):
            try:
                model = genai.GenerativeModel(
                    model_name=model_to_use,
                    system_instruction=system_instruction
                )
                
                generation_config = {}
                if json_mode:
                    generation_config["response_mime_type"] = "application/json"

                response = model.generate_content(
                    prompt,
                    generation_config=GenerationConfig(**generation_config)
                )
                
                if response and response.text:
                    return response.text.strip()
                else:
                    raise ValueError("Gemini API returned an empty response.")
                    
            except Exception as e:
                logger.warning(f"Gemini API attempt {attempt + 1} failed: {e}")
                if "ResourceExhausted" in str(e) or "429" in str(e):
                    # Rate limit hit, switch to fallback model or sleep longer
                    if attempt == 0 and self.fallback_model_name != self.model_name:
                        logger.info(f"Retrying with fallback model: {self.fallback_model_name}")
                        model_to_use = self.fallback_model_name
                    
                    sleep_time = (attempt + 1) * 5
                    logger.info(f"Sleeping for {sleep_time} seconds before retrying...")
                    time.sleep(sleep_time)
                else:
                    time.sleep(1)
                    
        raise RuntimeError(f"Failed to generate content from Gemini API after {max_retries} attempts.")

    def generate_summary(self, text: str, max_words: int = 150) -> str:
        """Summarizes a single article using Gemini."""
        default_sys = "You are an expert AI Research Analyst and Technical Writer."
        system_instruction = self._load_prompt("system.txt", default_sys)
        
        default_prompt = (
            "Summarize the following technical article. Focus on the core engineering decisions, "
            "architectural details, models used, and key findings. Avoid fluffy PR language. "
            "Keep the summary technically deep but concise (under {max_words} words).\n\n"
            "Article content:\n{text}"
        )
        prompt_template = self._load_prompt("summarization.txt", default_prompt)
        prompt = prompt_template.format(text=text, max_words=max_words)

        try:
            return self._call_gemini_with_retry(prompt, system_instruction=system_instruction)
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            # Smart fallback: extract first complete sentences up to ~300 chars
            fallback_text = text[:500]
            # Find last complete sentence
            for punct in ['. ', '.\n', '! ', '? ']:
                last_punct = fallback_text.rfind(punct)
                if last_punct > 100:
                    fallback_text = fallback_text[:last_punct + 1]
                    break
            return fallback_text.strip()

    def categorize_article(self, title: str, summary: str) -> str:
        """Categorizes an article into standard categories."""
        default_sys = "You are an expert AI taxonomy and categorization engine."
        system_instruction = self._load_prompt("categorization_system.txt", default_sys)

        default_prompt = (
            "Given the article title and summary, select exactly one category that fits the best from this list:\n"
            "- Major AI Model Developments\n"
            "- Infrastructure & Hardware\n"
            "- AI Agents / MCP / Tooling\n"
            "- Enterprise AI\n"
            "- Open Source & Research\n"
            "- General AI News\n\n"
            "Respond with ONLY the exact name of the category from the list above. Do not include markdown or explanations.\n\n"
            "Title: {title}\n"
            "Summary: {summary}"
        )
        prompt_template = self._load_prompt("categorization.txt", default_prompt)
        prompt = prompt_template.format(title=title, summary=summary)

        try:
            category = self._call_gemini_with_retry(prompt, system_instruction=system_instruction)
            # Normalize response to handle any quotes or spacing issues
            category = category.strip('`"\' ')
            valid_categories = [
                "Major AI Model Developments",
                "Infrastructure & Hardware",
                "AI Agents / MCP / Tooling",
                "Enterprise AI",
                "Open Source & Research",
                "General AI News"
            ]
            for vc in valid_categories:
                if vc.lower() in category.lower():
                    return vc
            return "General AI News"
        except Exception as e:
            logger.error(f"Categorization failed: {e}")
            return "General AI News"

    def synthesize_cluster(self, topic: str, articles: List[Dict[str, Any]]) -> str:
        """Synthesizes a combined summary for a cluster of similar articles."""
        default_sys = "You are an elite AI technical reporter who synthesizes multiple overlapping engineering updates."
        system_instruction = self._load_prompt("clustering_system.txt", default_sys)

        articles_text = ""
        for i, art in enumerate(articles):
            articles_text += f"Article [{i+1}]: {art.get('title')}\nSource: {art.get('source')}\nSummary: {art.get('summary')}\n\n"

        default_prompt = (
            "Analyze the following group of related articles on the topic of '{topic}'. "
            "Write a synthesized weekly briefing paragraph that connects these developments. "
            "Explain *why* this group of updates matters to AI software engineers and infrastructure architects. "
            "Identify the underlying industry trend, architectural consensus, or hardware shifts. "
            "Be technically precise, concise, and professional.\n\n"
            "Articles:\n{articles_text}"
        )
        prompt_template = self._load_prompt("clustering.txt", default_prompt)
        prompt = prompt_template.format(topic=topic, articles_text=articles_text)

        try:
            return self._call_gemini_with_retry(prompt, system_instruction=system_instruction)
        except Exception as e:
            logger.error(f"Cluster synthesis failed: {e}")
            return f"Ongoing updates regarding {topic} across several sources."

    def generate_educational_section(self, topic: str) -> str:
        """Generates a technically accurate, engineering-focused educational section."""
        default_sys = "You are a Principal AI Infrastructure Architect explaining complex topics in standard technical terms."
        system_instruction = self._load_prompt("educational_system.txt", default_sys)

        default_prompt = (
            "Create a highly informative educational deep-dive section on '{topic}'.\n"
            "The explanation must be:\n"
            "1. Beginner friendly but technically accurate and rigorous.\n"
            "2. Highly engineering focused (discuss performance, memory overhead, optimization, GPU bottlenecks, etc.).\n"
            "3. Concise but deep.\n\n"
            "Use clear headings, markdown lists, and small ascii diagrams if helpful to explain mechanics. "
            "Structure as:\n"
            "- **The Core Concept**: What is it and why does it exist?\n"
            "- **How It Works**: Mechanistic step-by-step breakdown.\n"
            "- **Engineering Considerations**: Memory, GPU execution, performance trade-offs, and standard scaling behaviors."
        )
        prompt_template = self._load_prompt("educational.txt", default_prompt)
        prompt = prompt_template.format(topic=topic)

        try:
            return self._call_gemini_with_retry(prompt, system_instruction=system_instruction)
        except Exception as e:
            logger.error(f"Educational generation failed: {e}")
            return f"### Educational Spotlight: {topic}\n\nDetailed walkthrough of {topic} is currently unavailable."

    def generate_newsletter(self, clustered_articles: List[Dict[str, Any]], educational_section: str) -> Dict[str, Any]:
        """Synthesizes clustered topics and the educational section into a finalized newsletter."""
        default_sys = "You are a Chief Editor publishing a high-tier weekly briefing for AI engineers."
        system_instruction = self._load_prompt("newsletter_system.txt", default_sys)

        # Build list of developments grouped by category
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
                developments_text += f"Synthesis/Summary: {it.get('synthesis') or it.get('summary')}\n\n"

        default_prompt = (
            "We are preparing the final Weekly Technical Newsletter. Below are the grouped developments and a premade educational section.\n\n"
            "Draft a complete newsletter containing:\n"
            "1. An AI-generated catchy, professional title.\n"
            "2. An Executive Summary / TLDR (a bulleted overview of the 3-4 most critical shifts of the week).\n"
            "3. Structured Markdown sections for each active development category, writing clean technical copy that ties the developments together beautifully. Add clickable markdown links to the sources.\n"
            "4. A concluding 'Final Outlook' explaining the macro trends observed this week.\n\n"
            "Ensure the output is formatted as a JSON object with these EXACT keys:\n"
            "- \"title\": \"The generated newsletter title\"\n"
            "- \"tldr\": \"A 3-4 bullet executive summary in markdown\"\n"
            "- \"sections\": {\n"
            "    \"Major AI Model Developments\": \"Markdown content for developments\",\n"
            "    \"Infrastructure & Hardware\": \"Markdown content\",\n"
            "    \"AI Agents / MCP / Tooling\": \"Markdown content\",\n"
            "    \"Enterprise AI\": \"Markdown content\",\n"
            "    \"Open Source & Research\": \"Markdown content\",\n"
            "    \"General AI News\": \"Markdown content\"\n"
            "  },\n"
            "- \"final_outlook\": \"Macro outlook summary in markdown\"\n\n"
            "Data to utilize:\n"
            "{developments_text}\n\n"
            "Educational Section (Integrate this under the section 'Byte-Sized Learning: KV Cache' or appropriate topic name):\n"
            "{educational_section}"
        )
        prompt_template = self._load_prompt("final_newsletter.txt", default_prompt)
        prompt = prompt_template.format(developments_text=developments_text, educational_section=educational_section)

        try:
            response_json_text = self._call_gemini_with_retry(prompt, system_instruction=system_instruction, json_mode=True)
            return json.loads(response_json_text)
        except Exception as e:
            logger.error(f"Final newsletter compilation failed: {e}")
            # Return a simple fallback newsletter dict
            return {
                "title": "AI Weekly Engineering Briefing",
                "tldr": "Weekly summary of latest AI advancements in model training, infrastructure, and agents.",
                "sections": {cat: "\n\n".join([f"- [{it.get('title')}]({it.get('url')}): {it.get('summary')}" for it in items]) for cat, items in categories_dict.items()},
                "final_outlook": "AI capabilities are expanding across hardware optimization and model alignment."
            }
