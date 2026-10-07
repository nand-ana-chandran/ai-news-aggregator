# AI News Aggregator

A portfolio-ready academic project that demonstrates an end-to-end AI news aggregation pipeline. The system collects AI-related content from multiple sources, enriches it with transcripts and documents, ranks stories using a user profile, and delivers a personalized digest via email.

This project is suitable for public GitHub sharing and resume use, especially for showcasing skills in Python development, LLM integration, data pipelines, PostgreSQL, and automation.

> Independent academic and portfolio project developed by Nandana Chandran.

## Overview

The **AI News Aggregator** is an end-to-end GenAI application designed to automate the process of discovering, processing, summarizing, and prioritizing AI news.

The system collects recent content from **YouTube, OpenAI, and Anthropic-related sources**, stores the content in PostgreSQL, enriches available content using YouTube transcripts and document conversion, and uses **Google Gemini** to generate structured summaries and personalized relevance rankings.

The final ranked stories are formatted into an HTML email digest and delivered through SMTP.

### Pipeline

```text
Content Sources
     │
     ├── YouTube
     ├── OpenAI News
     └── Anthropic News / Research / Engineering
     │
     ▼
Source Scrapers
     │
     ▼
PostgreSQL Database
     │
     ├── YouTube Transcript Enrichment
     └── Anthropic Document → Markdown Enrichment
     │
     ▼
Gemini Digest Generation
     │
     ▼
Personalized Relevance Ranking
     │
     ▼
Gemini Email Introduction + Email Formatting
     │
     ▼
HTML / Markdown Email Digest
     │
     ▼
User's Email
```

## Key Features

- **Multi-source AI news aggregation**
  - Collects recent YouTube videos.
  - Collects OpenAI news through RSS.
  - Collects Anthropic-related news, research, and engineering content.

- **Incremental content processing**
  - Newly collected content is stored in PostgreSQL.
  - Previously processed records are not repeatedly processed.
  - Missing transcripts, document content, and summaries are processed separately.

- **YouTube transcript enrichment**
  - Retrieves available YouTube transcripts.
  - Stores transcript text for subsequent AI summarization.
  - Handles videos where transcripts are unavailable.

- **Document enrichment**
  - Uses Docling to convert supported Anthropic source pages into Markdown.
  - Stores the enriched content in PostgreSQL.

- **Gemini-powered summarization**
  - Generates structured article digests using Google Gemini.
  - Produces concise titles and summaries.
  - Uses Pydantic models for structured AI output.

- **Personalized article ranking**
  - Ranks stories according to a configurable user profile.
  - Considers relevance, technical depth, novelty, expertise alignment, and practical value.
  - Allows preferences such as technical depth, practical applications, research developments, and avoiding marketing-heavy content.

- **Automated email delivery**
  - Generates a personalized introduction.
  - Selects the highest-ranked articles.
  - Converts the digest into HTML and Markdown.
  - Sends the final digest through SMTP.

- **Persistent storage**
  - PostgreSQL database stores source content, enriched content, and generated digests.
  - SQLAlchemy provides database interaction.

- **Docker-based database setup**
  - Docker Compose provides a local PostgreSQL instance with persistent storage.

## Technology Stack

| Technology | Purpose |
|---|---|
| Python 3.12+ | Application development |
| Google Gemini | AI summarization, ranking, and email introduction |
| PostgreSQL | Persistent data storage |
| SQLAlchemy | Database ORM |
| Pydantic | Data validation and structured AI responses |
| Feedparser | RSS feed processing |
| YouTube Transcript API | YouTube transcript retrieval |
| Docling | Document/page conversion to Markdown |
| Python-dotenv | Environment variable management |
| SMTP | Email delivery |
| Docker Compose | Local PostgreSQL infrastructure |
| uv | Python dependency and environment management |

## Project Structure

```text
ai-news-aggregator/
│
├── README.md
├── LICENSE
├── main.py
├── pyproject.toml
├── uv.lock
├── .env.example
├── .gitignore
├── .python-version
├── .dockerignore
├── .gitattributes
│
├── docker/
│   └── docker-compose.yml
│
└── app/
    │
    ├── __init__.py
    ├── config.py
    ├── runner.py
    ├── daily_runner.py
    │
    ├── agent/
    │   ├── __init__.py
    │   ├── curator_agent.py
    │   ├── digest_agent.py
    │   └── email_agent.py
    │
    ├── database/
    │   ├── __init__.py
    │   ├── connection.py
    │   ├── create_tables.py
    │   ├── models.py
    │   └── repository.py
    │
    ├── profiles/
    │   ├── __init__.py
    │   └── user_profile.py
    │
    ├── scrapers/
    │   ├── __init__.py
    │   ├── anthropic.py
    │   ├── openai.py
    │   └── youtube.py
    │
    └── services/
        ├── __init__.py
        ├── email.py
        ├── process_anthropic.py
        ├── process_curator.py
        ├── process_digest.py
        ├── process_email.py
        └── process_youtube.py
```

## System Architecture

### 1. Source Collection

The scraper layer collects recent content from configured sources.

**YouTube**

- Reads channel RSS feeds.
- Extracts video metadata such as title, URL, video ID, description, and publication time.
- YouTube transcripts are retrieved in a separate processing stage.

**OpenAI**

- Reads OpenAI's news RSS feed.
- Stores article metadata and descriptions.

**Anthropic**

- Reads configured Anthropic-related RSS feeds.
- Stores article metadata.
- Source pages can subsequently be converted into Markdown using Docling.

---

### 2. Database Layer

PostgreSQL is used as the persistent storage layer.

The database contains separate tables for:

- YouTube videos
- OpenAI articles
- Anthropic articles
- Generated digests

The repository layer provides operations for:

- Creating source records
- Avoiding duplicate records
- Finding records requiring enrichment
- Updating transcripts and Markdown content
- Finding articles requiring summaries
- Creating and retrieving generated digests

This allows the pipeline to process only the content that still requires work.

---

### 3. Content Enrichment

After source ingestion, additional information is collected where available.

For YouTube content:

```text
YouTube Video
      ↓
Transcript API
      ↓
Transcript Text
      ↓
Database
```

For Anthropic content:

```text
Article URL
      ↓
Docling
      ↓
Markdown Content
      ↓
Database
```

This separates relatively lightweight source collection from more expensive content processing.

---

### 4. AI Digest Generation

The `DigestAgent` uses **Google Gemini** to generate structured summaries.

The model receives the available article content and produces:

```text
Title
Summary
```

The response is validated using a Pydantic model before being stored in PostgreSQL.

The summarization prompt is designed to produce concise, technically useful summaries without unnecessary marketing language.

---

### 5. Personalized Ranking

After summaries have been generated, the `CuratorAgent` ranks the available stories according to a user profile.

The ranking considers factors such as:

- Relevance to the user's interests
- Technical depth
- Practical value
- Novelty and significance
- Alignment with the user's expertise
- Real-world applicability

Each ranked article contains:

```text
Digest ID
Relevance Score
Rank
Reasoning
```

This means the final email is not simply a chronological list of collected articles; the stories are prioritized according to the configured profile.

---

### 6. Email Generation and Delivery

The email stage combines the ranked stories with a generated introduction.

The `EmailAgent` creates the personalized introduction and email content, while the email service handles formatting and delivery.

The final workflow is:

```text
Ranked Digests
     ↓
Email Agent
     ↓
Personalized Introduction
     ↓
Selected Articles
     ↓
Markdown / HTML Formatting
     ↓
SMTP
     ↓
Email Inbox
```

## Daily Pipeline

The main daily pipeline is orchestrated by `app/daily_runner.py`.

It performs five major stages:

```text
1. Scrape Sources
       ↓
2. Process Anthropic Markdown
       ↓
3. Process YouTube Transcripts
       ↓
4. Generate AI Digests
       ↓
5. Generate and Send Email
```

The pipeline also records:

- Start time
- End time
- Execution duration
- Number of items collected
- Number of items processed
- Digest generation results
- Email delivery status
- Errors encountered during execution

## Configuration

The application uses environment variables for credentials and database configuration.

Create a local `.env` file from the example template:

```bash
cp .env.example .env
```

On Windows PowerShell, use:

```powershell
Copy-Item .env.example .env
```

Then populate it with your own values:

```env
MY_EMAIL=your_email@example.com
APP_PASSWORD=your_email_app_password
GEMINI_API_KEY=your_gemini_api_key
PROXY_USERNAME=
PROXY_PASSWORD=

POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=ai_news_aggregator
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

`PROXY_USERNAME` and `PROXY_PASSWORD` are optional and only needed if you use a Webshare proxy for YouTube transcript retrieval.

**Do not commit `.env` to GitHub.**

The `.env` file should remain in `.gitignore`.

## Prerequisites

Before running the project, make sure you have:

- Python 3.12 or later
- Docker and Docker Compose
- `uv`
- A Google Gemini API key
- An email account configured for SMTP/app-password authentication

## Installation

### 1. Clone the repository

```bash
git clone <your-repository-url>
cd ai-news-aggregator
```

### 2. Install dependencies

This project uses `uv` for dependency management.

```bash
uv sync
```

### 3. Configure environment variables

Copy the example file and add your credentials:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Example values:

```env
MY_EMAIL=
APP_PASSWORD=
GEMINI_API_KEY=
PROXY_USERNAME=
PROXY_PASSWORD=

POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=ai_news_aggregator
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

### 4. Start PostgreSQL

The project provides Docker Compose configuration for PostgreSQL. Use the project root `.env` file explicitly to ensure values are loaded correctly:

```bash
docker compose --env-file .env -f docker/docker-compose.yml up -d
```

Check the running container with:

```bash
docker ps
```

### 5. Create database tables

Run:

```bash
uv run python app/database/create_tables.py
```

You should see:

```text
Tables created successfully
```

## Running the Application

Run the complete daily pipeline with:

```bash
uv run python main.py
```

By default, the application processes content from the previous **24 hours** and selects the top **10** articles for the email digest.

You can also specify these values from the command line:

```bash
uv run python main.py <hours> <top_n>
```

For example:

```bash
uv run python main.py 48 15
```

This processes content from the previous 48 hours and generates an email containing up to 15 ranked articles.

## Processing Strategy

The application separates ingestion, enrichment, summarization, ranking, and delivery instead of performing everything in one step.

```text
              ┌──────────────────┐
              │   Source RSS     │
              │     Feeds        │
              └────────┬─────────┘
                       │
                       ▼
              ┌──────────────────┐
              │    Scrapers      │
              └────────┬─────────┘
                       │
                       ▼
              ┌──────────────────┐
              │   PostgreSQL     │
              └────────┬─────────┘
                       │
             ┌─────────┴─────────┐
             ▼                   ▼
      ┌─────────────┐     ┌─────────────┐
      │   YouTube   │     │  Anthropic  │
      │ Transcripts │     │  Markdown   │
      └──────┬──────┘     └──────┬──────┘
             │                   │
             └─────────┬─────────┘
                       ▼
              ┌──────────────────┐
              │  Gemini Digest   │
              │    Generation    │
              └────────┬─────────┘
                       │
                       ▼
              ┌──────────────────┐
              │ Gemini Curator   │
              │ Personalized     │
              │ Ranking          │
              └────────┬─────────┘
                       │
                       ▼
              ┌──────────────────┐
              │   Email Agent    │
              └────────┬─────────┘
                       │
                       ▼
                  📧 Email
```

## Design Highlights

### Structured GenAI Outputs

Pydantic models are used to validate AI-generated responses rather than relying entirely on free-form text.

This is used for:

- Article digests
- Ranked article results
- Email generation

### Incremental Processing

The database keeps track of which records have already been enriched or summarized.

For example:

```text
New Article
    ↓
Stored in Database
    ↓
No Markdown? → Process
    ↓
No Digest? → Summarize
    ↓
Digest Exists → Skip
```

This prevents unnecessary repeated processing.

### Separation of Responsibilities

The project separates different responsibilities into dedicated components:

```text
Scrapers       → Collect content
Database       → Store and retrieve content
Services       → Orchestrate processing
Agents         → Perform GenAI tasks
Profile        → Define personalization
Email Service  → Format and deliver output
```

This makes the application easier to maintain and extend.

## Security

Credentials are loaded through environment variables rather than being hard-coded into the application.

The following values should never be committed to the repository:

```text
GEMINI_API_KEY
APP_PASSWORD
```

Make sure `.env` remains listed in `.gitignore`.

## Current Scope

The current implementation focuses on:

- AI news aggregation
- Content enrichment
- AI summarization
- Personalized ranking
- Automated email delivery
- PostgreSQL persistence

The project does **not** currently implement a vector database, embeddings-based retrieval, or a Retrieval-Augmented Generation (RAG) pipeline.

## Future Improvements

Potential future improvements include:

- Supporting additional news and video sources
- Making the user profile fully configurable
- Adding a web interface for managing preferences
- Adding scheduled execution through a task scheduler
- Adding retry and backoff mechanisms for external APIs
- Adding database migrations
- Adding automated tests
- Adding monitoring and execution metrics
- Supporting multiple user profiles and personalized digests

## Author

**Nandana Chandran**

B.Tech Computer Science and Engineering

This project was developed independently for academic and portfolio purposes.

---

## License

This project is distributed under the [MIT License](LICENSE) for academic, portfolio, and personal use.
