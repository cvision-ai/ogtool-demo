from typing import List
import requests
from bs4 import BeautifulSoup
from tavily import TavilyClient
from app.core.config import settings
from app.models.content import ContentItem, ContentType
from mistralai import Mistral
from mistralai.models import OCRResponse, DocumentURLChunk
import os
from urllib.parse import urlparse

class ContentScraper:
    def __init__(self):
        self.tavily_client = TavilyClient(settings.TAVILY_API_KEY)
        
    def _get_base_url(self, url: str) -> str:
        """Extract base URL from any given URL"""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"
    
    async def scrape_blog(self, url: str) -> List[ContentItem]:
        """Scrape blog content from a given URL"""
        try:
            response = self.tavily_client.crawl(
                url=url,
                instructions="Get all blog posts",
                exclude_paths=["^(?!/blog/[^/]+$|/blogs/[^/]+$).*"],
                include_images=True
            )
            
            base_url = self._get_base_url(url)
            raw_contents = []
            
            # First pass - collect all raw content
            for result in response.get('results', []):
                content = result.get('raw_content', '')
                title = result.get('title', '')
                source_url = result.get('url', '')
                author = result.get('author', '')
                raw_contents.append({
                    'content': content,
                    'title': title,
                    'source_url': source_url,
                    'author': author
                })
            
            # Process all content at once
            seen_paragraphs = set()
            paragraph_counts = {}
            
            # First pass - collect all cleaned paragraphs
            for raw_content in raw_contents:
                paragraphs = raw_content['content'].split('\n\n')
                for paragraph in paragraphs:
                    cleaned = ''.join(paragraph.split())
                    if cleaned:
                        seen_paragraphs.add(cleaned)
            
            # Second pass - count paragraph occurrences
            for raw_content in raw_contents:
                paragraphs = raw_content['content'].split('\n\n')
                for paragraph in paragraphs:
                    cleaned = ''.join(paragraph.split())
                    if cleaned:
                        paragraph_counts[cleaned] = paragraph_counts.get(cleaned, 0) + 1
            
            # Process and create ContentItems
            items = []
            for raw_content in raw_contents:
                content = raw_content['content']
                title = raw_content['title']
                source_url = raw_content['source_url']
                
                # Extract author name
                paragraphs = content.split('\n\n')
                for paragraph in paragraphs:
                    if paragraph.strip().startswith('By '):
                        # Extract the name after "By " and before any separator
                        name = paragraph.strip()[3:].strip()
                        # Split by common separators and take the first part
                        name = name.split('|')[0].split('-')[0].split('•')[0].strip()
                        # Check if it matches the pattern of having at least two words with first letters capitalized
                        words = name.split()
                        if len(words) >= 2 and all(word[0].isupper() for word in words):
                            author = name
                            break
                
                # Process and clean content
                cleaned_paragraphs = []
                first_h1 = True
                first_paragraph = True
                
                for paragraph in content.split('\n\n'):
                    # Remove code block markers
                    paragraph = paragraph.replace('```', '')
                    cleaned = ''.join(paragraph.split())
                    
                    # Skip if paragraph is empty or not unique
                    if not cleaned or cleaned not in paragraph_counts or paragraph_counts[cleaned] != 1:
                        continue
                    
                    # Handle first paragraph and H1 heading
                    if first_paragraph:
                        first_paragraph = False
                        continue
                        
                    if paragraph.strip().startswith('# ') and first_h1:
                        title = paragraph.strip().replace('# ', '')
                        cleaned_paragraphs.append(f'# [{title}]({source_url})')
                        first_h1 = False
                    else:
                        # Fix relative links
                        if '](/' in paragraph:
                            # Use the base URL for relative links
                            paragraph = paragraph.replace('](/', f']({base_url}/')
                        cleaned_paragraphs.append(paragraph.strip())
                
                # Join cleaned paragraphs with double newlines
                cleaned_content = '\n\n'.join(cleaned_paragraphs)
                
                items.append(ContentItem(
                    title=title,
                    content=cleaned_content,
                    content_type=ContentType.BLOG,
                    source_url=source_url,
                    author=author
                ))
            
            return items
            
        except Exception as e:
            raise Exception(f"Error scraping blog: {str(e)}")
    
    async def scrape_company_guides(self, url: str, team_id: str, user_id: str = None) -> List[ContentItem]:
        """Scrape company guides from interviewing.io"""
        try:
            response = requests.get(url)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find all links containing "Interview process & questions"
            interview_links = []
            for link in soup.find_all('a'):
                if "Interview process & questions" in link.text:
                    href = link.get('href')
                    if href:
                        if href.startswith('/'):
                            href = f"https://interviewing.io{href}"
                        interview_links.append(href)
            
            items = []
            for link in interview_links:
                extract_response = self.tavily_client.extract(
                    urls=[link],
                    extract_depth="advanced",
                    include_images=True
                )
                
                for result in extract_response.get('results', []):
                    content = result.get('raw_content', '')
                    title = result.get('title', '')
                    
                    items.append(ContentItem(
                        title=title,
                        content=content,
                        content_type=ContentType.OTHER,
                        source_url=link,
                        user_id=user_id
                    ))
            
            return items
            
        except Exception as e:
            raise Exception(f"Error scraping company guides: {str(e)}")
    
    async def process_pdf(self, file_path: str, team_id: str, user_id: str = None) -> List[ContentItem]:
        """Process PDF content using Mistral OCR"""
        try:
            client = Mistral(api_key=settings.MISTRAL_API_KEY)
            
            with open(file_path, "rb") as f:
                pdf_bytes = f.read()
            
            uploaded_file = client.files.upload(
                file={
                    "file_name": os.path.basename(file_path),
                    "content": pdf_bytes,
                },
                purpose="ocr"
            )
            
            signed_url = client.files.get_signed_url(file_id=uploaded_file.id, expiry=1)
            
            ocr_response = client.ocr.process(
                document=DocumentURLChunk(document_url=signed_url.url),
                model="mistral-ocr-latest",
                include_image_base64=True
            )
            
            # Process OCR response into markdown
            markdown_content = self._process_ocr_response(ocr_response)
            
            return [ContentItem(
                title=os.path.basename(file_path),
                content=markdown_content,
                content_type=ContentType.BOOK,
                user_id=user_id
            )]
            
        except Exception as e:
            raise Exception(f"Error processing PDF: {str(e)}")
    
    def _process_ocr_response(self, ocr_response: OCRResponse) -> str:
        """Process OCR response into markdown format"""
        markdowns = []
        for page in ocr_response.pages:
            image_data = {}
            for img in page.images:
                image_data[img.id] = img.image_base64
            
            # Replace base64 images with markdown image links
            markdown = page.markdown
            for img_id, base64_str in image_data.items():
                markdown = markdown.replace(
                    f"![{img_id}]({img_id})",
                    f"![{img_id}]({base64_str})"
                )
            markdowns.append(markdown)
        
        return "\n\n".join(markdowns) 