# Save Aline Assignment

**Hey, I'm [Ayesh](https://www.linkedin.com/in/ayesh-ahmad/), and I've saved Aline!**

_**Note**: Although my application was on behalf of CVision, do note that this assignment was solved by one individual only to keep submissions fair for other applicants. But we all do it this good ;)_

# 📝 Overview

This project solves a critical bottleneck in technical AI content generation. Aline, a technical thought leader, needs AI-generated Reddit comments that reflect her deep technical expertise. Current models excel with personal tone but fail on technical precision due to incomplete knowledgebases.

**Goal:**

Create a reusable, end-to-end tool that imports technical knowledge from multiple content types (blogs, guides, books) into a structured JSON format optimized for AI use.

# ✅ Features

* 🔗 Web Scraper: Crawls and extracts content from:
    * interviewing.io blog
    * Company Guides: interviewing.io/topics#companies
    * Interview Guides: interviewing.io/learn#interview-guides
    * Nil Mamano's DSA blog: nilmamano.com/blog/category/dsa
    * 🧠 Bonus: Substack support (e.g. Shreycation)
* 📄 PDF Extractor: Parses and converts book chapters (e.g., Beyond Cracking the Coding Interview) into markdown-rich knowledge items
* 🧱 Reusable Design: Easily extendable for other authors, domains, or content platforms (e.g., Quill, Medium, LinkedIn)
* ⚙️ Modular Architecture: Pluggable source scrapers → content cleaner → formatter → JSON exporter

# 🛠️ Tech Stack

* Python 3.11
* Tavily, BeautifulSoup4 & requests for web scraping
* Mistral AI OCR for PDF parsing

# 📥 Input Types

| Type | Example |
|------|---------|
| Blog | https://interviewing.io/blog |
| Guide | https://interviewing.io/topics#companies |
| PDF | Beyond Cracking the Coding Interview (Chapters 1–8) |
| Substack | https://shreycation.substack.com |

# 📤 Output Format

```json
{
  "team_id": "aline123",
  "items": [
    {
      "title": "Item Title",
      "content": "Markdown content",
      "content_type": "blog|book|other",
      "source_url": "optional-url",
      "author": "",
      "user_id": ""
    }
  ]
}
```

# 🧩 Architecture

/ogtool-demo
│
├── scrapers/
│   ├── base_scraper.py
│   ├── interviewing_io.py
│   ├── nil_dsa.py
│   ├── substack.py
│   └── pdf_parser.py
│
├── formatters/
│   └── markdown_cleaner.py
│
├── utils/
│   └── json_exporter.py
│
├── main.py
└── README.md

▶️ How to Run

git clone https://github.com/yourusername/aline-scraper.git
cd aline-scraper

# Set up your environment
pip install -r requirements.txt

# Run main script
python main.py --source "interviewing.io" --team_id "aline123"
To process PDFs:

python main.py --pdf "path/to/book.pdf" --team_id "aline123"

# Content Scraper API

A FastAPI-based service for scraping and processing content from various sources, including blogs, company guides, and PDFs.

## Features

- Blog content scraping (e.g., interviewing.io blog)
- Company guide scraping (e.g., interviewing.io company guides)
- PDF processing with OCR (e.g., book chapters)
- Support for multiple content types
- Scalable and reusable architecture

## Setup

1. Create a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file with your API keys:
```
TAVILY_API_KEY=your_tavily_api_key
MISTRAL_API_KEY=your_mistral_api_key
```

## Running the Server

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

## API Endpoints

### 1. Scrape Blog Content
```http
POST /api/v1/scrape/blog
Content-Type: application/json

{
    "url": "https://interviewing.io/blog",
    "team_id": "your_team_id",
    "user_id": "optional_user_id"
}
```

### 2. Scrape Company Guides
```http
POST /api/v1/scrape/company-guides
Content-Type: application/json

{
    "url": "https://interviewing.io/topics#companies",
    "team_id": "your_team_id",
    "user_id": "optional_user_id"
}
```

### 3. Process PDF
```http
POST /api/v1/process/pdf
Content-Type: multipart/form-data

file: <pdf_file>
team_id: your_team_id
user_id: optional_user_id
```

## Response Format

All endpoints return data in the following format:
```json
{
    "team_id": "your_team_id",
    "items": [
        {
            "title": "Item Title",
            "content": "Markdown content",
            "content_type": "blog|podcast_transcript|call_transcript|linkedin_post|reddit_comment|book|other",
            "source_url": "optional-url",
            "author": "",
            "user_id": ""
        }
    ]
}
```

## Development

The project structure is organized as follows:
```
app/
├── api/
│   └── routes.py
├── core/
│   └── config.py
├── models/
│   └── content.py
├── services/
│   └── scraper.py
└── main.py
```

## Error Handling

The API includes comprehensive error handling for:
- Invalid URLs
- Missing API keys
- File processing errors
- Network issues
- Invalid request formats

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request