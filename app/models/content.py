from pydantic import BaseModel, HttpUrl
from typing import List, Optional
from enum import Enum

class ContentType(str, Enum):
    BLOG = "blog"
    PODCAST_TRANSCRIPT = "podcast_transcript"
    CALL_TRANSCRIPT = "call_transcript"
    LINKEDIN_POST = "linkedin_post"
    REDDIT_COMMENT = "reddit_comment"
    BOOK = "book"
    OTHER = "other"

class ContentItem(BaseModel):
    title: str
    content: str
    content_type: ContentType
    source_url: Optional[HttpUrl] = None
    author: Optional[str] = None
    user_id: Optional[str] = None

class ContentResponse(BaseModel):
    team_id: str
    items: List[ContentItem]

class ScrapeRequest(BaseModel):
    url: HttpUrl

class PDFUploadRequest(BaseModel):
    team_id: str
    user_id: Optional[str] = None 