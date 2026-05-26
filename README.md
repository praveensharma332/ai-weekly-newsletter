# AI Weekly Newsletter Generator

A production-grade AI-powered weekly newsletter generator that automatically collects AI news, research papers, and infrastructure updates from across the internet, synthesizes them using Google Gemini, and produces polished executive-quality engineering briefings.

## Features

- **Multi-Source Collection** — Aggregates from arXiv, HuggingFace, OpenAI, Anthropic, DeepMind, NVIDIA, Reddit, HackerNews, and more
- **Gemini AI Summarization** — Uses Google Gemini API for intelligent summarization and synthesis
- **Semantic Deduplication** — Prevents duplicate articles using sentence-transformer embeddings
- **Topic Clustering** — Groups related articles using agglomerative clustering
- **Educational Deep Dives** — Auto-generates byte-sized learning sections (KV Cache, RAG, LoRA, etc.)
- **Multiple Output Formats** — Generates Markdown, HTML, and JSON outputs
- **Beautiful Dashboard** — Local FastAPI web interface to browse archives and trigger runs
- **Vector Search** — Semantic search across all stored articles
- **Scheduling** — APScheduler integration for weekly/daily automated runs
- **Email Delivery** — Optional SMTP/Gmail support for newsletter distribution
- **Slack Integration** — Optional webhook support for Slack notifications

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.9+ |
| AI Provider | Google Gemini API (Primary) |
| Fallback LLM | Ollama (Local) |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Database | SQLite + SQLAlchemy |
| Web Framework | FastAPI + Uvicorn |
| Templating | Jinja2 |
| Scheduling | APScheduler |
| HTTP Client | httpx |
| RSS Parsing | feedparser |
| HTML Parsing | BeautifulSoup4 |

## Project Structure

```
ai-weekly-newsletter/
├── app/
│   ├── collectors/       # RSS and scraper modules
│   ├── summarizers/      # Article summarization pipeline
│   ├── generators/       # Newsletter compilation
│   ├── clustering/       # Semantic embeddings & clustering
│   ├── storage/          # SQLite database models
│   ├── scheduler/        # APScheduler configuration
│   ├── prompts/          # LLM prompt templates
│   ├── templates/        # Jinja2 HTML templates
│   ├── config/           # Application settings
│   ├── providers/        # LLM provider abstraction (Gemini, Ollama)
│   ├── utils/            # Email, Slack, logging utilities
│   └── main.py           # FastAPI dashboard application
├── data/
│   ├── newsletters/      # Generated newsletter outputs (by date)
│   ├── raw_articles/     # Cached raw article content
│   ├── embeddings/       # Stored embedding vectors
│   └── database/         # SQLite database file
├── logs/                 # Application logs
├── requirements.txt      # Python dependencies
├── run.py                # CLI entry point
├── setup.sh              # Setup and initialization script
├── sources.yaml          # RSS feed source configuration
├── .env.example          # Environment variable template
└── README.md             # This file
```

## Quick Start

### 1. Clone and Setup

```bash
cd ~/Desktop/sandbox/ai-weekly-newsletter

# Run the setup script
chmod +x setup.sh
./setup.sh
```

### 2. Configure Gemini API Key

1. Get a free API key from [Google AI Studio](https://aistudio.google.com/)
2. Edit the `.env` file:

```bash
GEMINI_API_KEY=your_actual_api_key_here
```

### 3. Activate Virtual Environment

```bash
source venv/bin/activate
```

### 4. Run the Newsletter Generator

```bash
# Launch the web dashboard (default)
python run.py

# Or trigger a manual newsletter generation
python run.py --weekly

# Test run without saving files
python run.py --dry-run

# Start the background scheduler service
python run.py --schedule
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `python run.py` | Launch local web dashboard at http://127.0.0.1:8000 |
| `python run.py --weekly` | Manually run weekly newsletter generation |
| `python run.py --daily` | Manually run daily briefing generation |
| `python run.py --dry-run` | Test pipeline without writing files or updating DB |
| `python run.py --schedule` | Start APScheduler background service |

## Web Dashboard

Access the dashboard at **http://127.0.0.1:8000** after running `python run.py`.

### Dashboard Features:
- **Console Panel** — View database statistics and archived newsletters
- **Archive Viewer** — Read full HTML newsletters in an embedded viewer
- **Vector Search** — Semantic search across all stored article summaries
- **Manual Trigger** — Run the newsletter pipeline from the browser

## Configuration

### Environment Variables (.env)

```bash
# Google Gemini API (Required)
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash
GEMINI_FALLBACK_MODEL=gemini-2.5-pro

# Ollama Local LLM (Optional)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3

# Embeddings
EMBEDDING_MODEL_NAME=all-MiniLM-L6-v2

# Email (Optional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
SMTP_FROM_EMAIL=your_email@gmail.com
SMTP_TO_EMAIL=recipient@example.com

# Slack (Optional)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

### Adding/Modifying RSS Sources

Edit `sources.yaml`:

```yaml
sources:
  research:
    - name: "arXiv Artificial Intelligence"
      url: "https://rss.arxiv.org/rss/cs.AI"
      type: "rss"
  
  companies:
    - name: "OpenAI Blog"
      url: "https://openai.com/blog/rss.xml"
      type: "rss"
```

### Customizing Prompts

Edit files in `app/prompts/`:

| File | Purpose |
|------|---------|
| `summarization.txt` | Single article summarization |
| `categorization.txt` | Article category classification |
| `clustering.txt` | Multi-article synthesis |
| `educational.txt` | Byte-sized learning generation |
| `final_newsletter.txt` | Final newsletter compilation |
| `executive_summary.txt` | Executive summary generation |

## Newsletter Output

Generated newsletters are saved to:

```
data/newsletters/YYYY-MM-DD/
├── newsletter.md      # Markdown format
├── newsletter.html    # Styled HTML format
└── newsletter.json    # Structured JSON data
```

### Newsletter Sections

1. **Executive Summary** — TL;DR bullet points
2. **Major AI Model Developments** — New models, benchmarks, releases
3. **Infrastructure & Hardware** — GPUs, training infrastructure
4. **AI Agents / MCP / Tooling** — Agent frameworks, tool use
5. **Enterprise AI** — Business applications
6. **Open Source & Research** — Papers, open-source releases
7. **Byte-Sized Learning** — Educational deep dive (e.g., KV Cache, RAG)
8. **Final Outlook** — Macro trends summary

## Scheduling

The scheduler runs the newsletter pipeline automatically.

### Default Schedule
- **Weekly**: Monday at 9:00 AM

### Start Scheduler Service

```bash
python run.py --schedule
```

The scheduler runs in the foreground. Use `Ctrl+C` to stop.

## Email Delivery

Configure SMTP in `.env` to enable email delivery:

```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_gmail_app_password
SMTP_FROM_EMAIL=your_email@gmail.com
SMTP_TO_EMAIL=recipient@example.com
```

> **Note**: For Gmail, use an [App Password](https://support.google.com/accounts/answer/185833), not your regular password.

## Slack Integration

Send newsletter notifications to Slack:

1. Create a [Slack Incoming Webhook](https://api.slack.com/messaging/webhooks)
2. Add to `.env`:

```bash
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T00/B00/xxx
```

3. The system will post a notification with the newsletter title and summary when generation completes.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web dashboard |
| `/api/newsletters` | GET | List all newsletters |
| `/api/newsletters/{date}` | GET | Get newsletter by date |
| `/api/stats` | GET | Database statistics |
| `/api/search?q=query` | GET | Semantic vector search |
| `/api/pipeline/run` | POST | Trigger newsletter generation |

## Troubleshooting

### "GEMINI_API_KEY is not configured"

Ensure your `.env` file contains a valid API key:
```bash
GEMINI_API_KEY=AIzaSy...
```

### "No articles fetched from sources"

- Check your internet connection
- Verify RSS URLs in `sources.yaml` are accessible
- Some feeds may be rate-limited; try again later

### "Only X unused articles found, requires at least 3"

The generator needs at least 3 unprocessed articles. Run `python run.py --weekly` to fetch new articles first.

### Embedding model download slow

The first run downloads the sentence-transformer model (~90MB). Subsequent runs use the cached model.

### Rate limit errors from Gemini

The system automatically retries with exponential backoff and falls back to `gemini-2.5-pro` if the primary model is rate-limited.

## Development

### Install Dependencies Manually

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Initialize Database

```bash
python -c "from app.storage.database import init_db; init_db()"
```

### Run Tests

```bash
# Dry run to test pipeline
python run.py --dry-run
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLI / Dashboard                          │
│                     (run.py / FastAPI)                          │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Scheduler (APScheduler)                     │
└─────────────────────────────────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐      ┌───────────────┐      ┌───────────────┐
│  RSS Collector│      │  Summarizer   │      │   Generator   │
│  (feedparser) │ ───▶ │  (Gemini API) │ ───▶ │  (Jinja2)     │
└───────────────┘      └───────────────┘      └───────────────┘
        │                       │                       │
        ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Semantic Embedder                            │
│              (sentence-transformers + sklearn)                  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   SQLite Database (SQLAlchemy)                  │
│                Articles │ Newsletters │ Embeddings              │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Output Generation                          │
│              Markdown │ HTML │ JSON │ Email │ Slack             │
└─────────────────────────────────────────────────────────────────┘
```

## License

MIT License - Feel free to use and modify.

## Credits

Built with:
- [Google Gemini API](https://ai.google.dev/)
- [Sentence Transformers](https://www.sbert.net/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy](https://www.sqlalchemy.org/)
