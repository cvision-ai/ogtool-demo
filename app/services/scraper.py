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
    
    def _process_raw_content(self, raw_content: dict, base_url: str, content_type: ContentType) -> ContentItem:
        """Process raw content and create a ContentItem
        
        Args:
            raw_content (dict): Dictionary containing content, title, source_url, and author
            base_url (str): Base URL of the blog for fixing relative links
            
        Returns:
            ContentItem: Processed content item
        """
        content = raw_content['content']
        title = raw_content['title']
        source_url = raw_content['source_url']
        
        # Extract author name
        paragraphs = content.split('\n\n')
        author = None
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
                elif "nilmamano" in base_url:
                    author = "Nil Mamano"
                    break
                else:
                    author = None
        
        # Process and clean content
        cleaned_paragraphs = []
        first_h1 = True
        found_first_heading = False
        
        for paragraph in content.split('\n\n'):
            # Basic cleaning
            paragraph = paragraph.strip()
            if not paragraph:
                continue
                
            # Remove code block markers
            paragraph = paragraph.replace('```', '')
            
            # Check if this is a heading
            is_heading = paragraph.startswith('# ')
            
            # Skip content before first heading
            if not found_first_heading and not is_heading:
                continue
            
            # Handle H1 heading
            if is_heading and first_h1:
                title = paragraph.replace('# ', '')
                cleaned_paragraphs.append(f'# [{title}]({source_url})')
                first_h1 = False
                found_first_heading = True
            else:
                # Fix relative links
                if '](/' in paragraph:
                    paragraph = paragraph.replace('](/', f']({base_url}/')
                cleaned_paragraphs.append(paragraph)
                if is_heading:
                    found_first_heading = True
        
        # Join cleaned paragraphs with double newlines
        cleaned_content = '\n\n'.join(cleaned_paragraphs)
        
        return ContentItem(
            title=title,
            content=cleaned_content,
            content_type=ContentType.BLOG,
            source_url=source_url,
            author=author
        )

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
            
            # Process and create ContentItems
            items = []
            for raw_content in raw_contents:
                items.append(self._process_raw_content(raw_content, base_url, ContentType.BLOG))
            
            return items
            
        except Exception as e:
            raise Exception(f"Error scraping blog: {str(e)}")
    
    async def scrape_company_guides(self, url: str) -> List[ContentItem]:
        """Scrape company guides from interviewing.io"""
        base_url = self._get_base_url(url)
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
                            href = f"{base_url}{href}"
                        href = href.split('#')[0]
                        interview_links.append(href)
            
            if not interview_links:
                return []
            
            all_responses = []
            for i in range(0, len(interview_links), 20):
                batch = interview_links[i:i+20]
                extract_response = self.tavily_client.extract(
                    urls=batch,
                    extract_depth="advanced",
                    include_images=True
                )
                all_responses.extend(extract_response.get('results', []))
            # Process results into ContentItems
            items = []
            for result in all_responses:
                content = result.get('raw_content', '')
                title = result.get('title', '')
                source_url = result.get('url', '')
                
                # Clean and process the content
                cleaned_content = self._process_raw_content({
                    'content': content,
                    'title': title,
                    'source_url': source_url,
                    'author': None
                }, base_url, ContentType.OTHER)
                
                items.append(cleaned_content)
            
            return items
            
        except requests.RequestException as e:
            raise Exception(f"Error fetching company guides: {str(e)}")
        except Exception as e:
            raise Exception(f"Error processing company guides: {str(e)}")
    
    async def process_pdf(self, file_path: str) -> List[ContentItem]:
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