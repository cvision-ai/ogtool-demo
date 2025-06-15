from fastapi import APIRouter, UploadFile, File, HTTPException
from app.models.content import ScrapeRequest, ContentResponse
from app.services.scraper import ContentScraper
import os
from app.core.config import settings
from pathlib import Path

router = APIRouter()
scraper = ContentScraper()

@router.post("/scrape/blog", response_model=ContentResponse)
async def scrape_blog(request: ScrapeRequest):
    """Scrape blog content from a given URL"""
    try:
        items = await scraper.scrape_blog(
            url=str(request.url)
        )
        return ContentResponse(team_id="aline123", items=items)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/scrape/guides", response_model=ContentResponse)
async def scrape_guides(request: ScrapeRequest):
    """Scrape guides from interviewing.io"""
    try:
        items = await scraper.scrape_guides(
            url=str(request.url)
        )
        return ContentResponse(team_id="aline123", items=items)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process/pdf", response_model=ContentResponse)
async def process_pdf(file: UploadFile = File(...)):
    """Process PDF content using Mistral OCR"""
    try:
        # Create upload directory if it doesn't exist
        upload_dir = Path(settings.UPLOAD_DIR)
        upload_dir.mkdir(exist_ok=True)
        
        # Save uploaded file
        file_path = upload_dir / file.filename
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Process PDF
        items = await scraper.process_pdf(
            file_path=str(file_path)
        )
        
        # Clean up
        os.remove(file_path)
        
        return ContentResponse(team_id="aline123", items=items)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 