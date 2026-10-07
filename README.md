# AI News Aggregator

An end-to-end pipeline that collects AI news from YouTube, OpenAI and Anthropic, summarizes it with Google Gemini, ranks the stories against a personal interest profile, and emails you a daily digest.

**Stack:** Python 3.12 · Google Gemini · PostgreSQL · SQLAlchemy · Pydantic · Docker Compose · uv

## How It Works

```text
Sources (YouTube, OpenAI, Anthropic)
        │
        ▼
Scrapers  ──►  PostgreSQL
                  │
                  ├── YouTube transcripts
                  └── Anthropic pages → Markdown (Docling)
                  │
                  ▼
Gemini digest generation (title + summary)
                  │
                  ▼
Gemini personalized ranking (based on user profile)
                  │
                  ▼
Gemini email introduction + HTML/Markdown formatting
                  │
                  ▼
Email delivery via SMTP
```

Each stage works only on records that still need processing, so re-running the pipeline never repeats finished work.

## Features

- **Multi-source collection:** YouTube channel feeds, OpenAI news RSS, and Anthropic news, research and engineering feeds.
- **Content enrichment:** fetches YouTube transcripts when available and converts Anthropic pages to Markdown with Docling.
- **Structured summaries:** Gemini produces a title and summary for each item, validated with Pydantic models.
- **Personalized ranking:** stories are scored on relevance, technical depth, novelty, practical value and fit with the user's expertise, with an explanation for each rank.
- **Email digest:** a generated introduction followed by the top-ranked stories, sent as HTML.
- **Incremental processing:** PostgreSQL tracks which records already have transcripts, Markdown or digests.

## Project Structure

```text
ai-news-aggregator/
├── main.py                  # CLI entry point
├── pyproject.toml
├── uv.lock
├── .env.example
├── docker/
│   └── docker-compose.yml   # local PostgreSQL
└── app/
    ├── config.py            # YouTube channels to follow
    ├── runner.py            # runs the scrapers
    ├── daily_runner.py      # orchestrates the full pipeline
    ├── agent/               # Gemini agents: digest, curator, email
    ├── database/            # connection, models, repository
    ├── profiles/            # user profile used for ranking
    ├── scrapers/            # YouTube, OpenAI, Anthropic
    └── services/            # processing steps and email delivery
```

## Getting Started

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Docker and Docker Compose
- A Google Gemini API key
- An email account with an app password for SMTP

### Setup

1. **Clone and install**

   ```bash
   git clone https://github.com/nand-ana-chandran/ai-news-aggregator.git
   cd ai-news-aggregator
   uv sync
   ```

2. **Configure environment variables**

   ```bash
   cp .env.example .env          # Windows PowerShell: Copy-Item .env.example .env
   ```

   Fill in `.env`:

   ```env
   MY_EMAIL=your_email@example.com
   APP_PASSWORD=your_email_app_password
   GEMINI_API_KEY=your_gemini_api_key

   # Optional: Webshare proxy for YouTube transcript retrieval
   PROXY_USERNAME=
   PROXY_PASSWORD=

   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=postgres
   POSTGRES_DB=ai_news_aggregator
   POSTGRES_HOST=localhost
   POSTGRES_PORT=5432
   ```

3. **Start PostgreSQL**

   ```bash
   docker compose --env-file .env -f docker/docker-compose.yml up -d
   ```

4. **Create the database tables**

   ```bash
   uv run python app/database/create_tables.py
   ```

## Usage

Run the full pipeline (last 24 hours, top 10 stories):

```bash
uv run python main.py
```

Or choose the time window and number of stories:

```bash
uv run python main.py <hours> <top_n>
uv run python main.py 48 15      # last 48 hours, top 15 stories
```

The pipeline runs five stages: scrape sources, convert Anthropic pages to Markdown, fetch YouTube transcripts, generate digests, then rank and send the email. It records timings, item counts, delivery status and any errors for each run.

## Customization

- **Interests and preferences:** edit `app/profiles/user_profile.py` to change what gets ranked highly.
- **YouTube channels:** add channel IDs to `app/config.py`.

## Security

All credentials are read from environment variables. `.env` is listed in `.gitignore` and must never be committed. Keep these values private: `GEMINI_API_KEY`, `APP_PASSWORD`, `PROXY_PASSWORD`, `POSTGRES_PASSWORD`.

## Scope and Future Work

The project covers aggregation, enrichment, summarization, ranking, email delivery and PostgreSQL persistence. It does not use a vector database, embeddings or RAG.

Possible next steps:

- More news and video sources
- A web interface for managing preferences
- Scheduled runs through a task scheduler
- Retry and backoff for external APIs
- Database migrations
- Automated tests
- Multiple user profiles

## Author

Built by **Nandana Chandran**, B.Tech Computer Science and Engineering.
