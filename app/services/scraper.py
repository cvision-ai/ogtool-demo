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
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

import time
from difflib import SequenceMatcher

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
            content_type=content_type,
            source_url=source_url,
            author=author
        )

    def _find_longest_common_substring(self, str1: str, str2: str) -> str:
        """Find the longest common substring between two strings."""
        seqMatch = SequenceMatcher(None, str1, str2)
        match = seqMatch.find_longest_match(0, len(str1), 0, len(str2))
        return str1[match.a: match.a + match.size]

    def _remove_similar_elements(self, elements: List[dict], min_overlap: int = 25) -> List[dict]:
        """Remove elements with significant text overlap."""
        unique_elements = []
        skip_indices = set()
        
        for i, elem1 in enumerate(elements):
            if i in skip_indices:
                continue
                
            text1 = elem1['text']
            is_unique = True
            
            for j, elem2 in enumerate(elements[i + 1:], start=i + 1):
                if j in skip_indices:
                    continue
                    
                text2 = elem2['text']
                common_substring = self._find_longest_common_substring(text1, text2)
                
                if len(common_substring) >= min_overlap:
                    if len(text2) > len(text1):
                        is_unique = False
                        break
                    else:
                        skip_indices.add(j)
            
            if is_unique:
                unique_elements.append(elem1)
        
        return unique_elements

    def _collect_urls_selenium(self, url: str) -> List[str]:
        """Collect unique URLs using Selenium."""
        options = webdriver.ChromeOptions()
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-software-rasterizer')
        options.add_argument('--window-size=1920,1080')
        
        selenium_host = os.getenv("SELENIUM_HOST", "selenium")
        selenium_port = os.getenv("SELENIUM_PORT", "4444")
        
        driver = webdriver.Remote(
            command_executor=f"http://{selenium_host}:{selenium_port}/wd/hub",
            options=options
        )
        unique_urls = set()
        
        try:
            driver.get(url)
            time.sleep(3)  # Wait for page to load
            
            # JavaScript to find all clickable elements
            js_script = """
            function getClickableElements() {
                const allElements = document.getElementsByTagName('*');
                const clickableElements = [];
                
                for (const element of allElements) {
                    let isClickable = false;
                    let text = element.textContent.trim();
                    
                    if (!text || text.length <= 25) continue;
                    
                    const style = window.getComputedStyle(element);
                    const href = element.getAttribute('href');
                    const role = element.getAttribute('role');
                    const hasOnClick = element.hasAttribute('onclick');
                    const isButton = element.tagName.toLowerCase() === 'button';
                    const isLink = element.tagName.toLowerCase() === 'a';
                    
                    isClickable = style.cursor === 'pointer' || 
                                 href || 
                                 role === 'button' || 
                                 role === 'link' ||
                                 role === 'article' ||
                                 hasOnClick ||
                                 isButton ||
                                 isLink;
                    
                    if (isClickable) {
                        function getElementPath(el) {
                            const path = [];
                            while (el && el.nodeType === Node.ELEMENT_NODE) {
                                let selector = el.nodeName.toLowerCase();
                                if (el.id) {
                                    selector += '#' + el.id;
                                } else {
                                    let nth = 1;
                                    let sib = el;
                                    while (sib.previousElementSibling) {
                                        sib = sib.previousElementSibling;
                                        if (sib.nodeName.toLowerCase() === selector) nth++;
                                    }
                                    if (nth !== 1) selector += ":nth-of-type("+nth+")";
                                }
                                path.unshift(selector);
                                el = el.parentNode;
                            }
                            return path.join(' > ');
                        }
                        
                        clickableElements.push({
                            tagName: element.tagName.toLowerCase(),
                            id: element.id,
                            classes: Array.from(element.classList),
                            href: href,
                            role: role,
                            hasOnClick: hasOnClick,
                            text: text,
                            textLength: text.length,
                            path: getElementPath(element)
                        });
                    }
                }
                return clickableElements;
            }
            return getClickableElements();
            """
            
            clickable_elements = driver.execute_script(js_script)
            unique_elements = self._remove_similar_elements(clickable_elements)
            
            # First add any direct hrefs
            for element in unique_elements:
                if element.get('href') and element['href'].startswith('http'):
                    unique_urls.add(element['href'])
            
            # Then try clicking elements
            for element in unique_elements:
                try:
                    if driver.current_url != url:
                        driver.get(url)
                        time.sleep(2)
                    
                    # Try to find and click the element
                    element_obj = None
                    try:
                        element_obj = driver.find_element(By.CSS_SELECTOR, element['path'])
                    except:
                        try:
                            if element.get('role'):
                                elements = driver.find_elements(By.XPATH, 
                                    f"//*[@role='{element['role']}'][contains(text(), '{element['text'][:50]}')]")
                                if elements:
                                    element_obj = elements[0]
                        except:
                            try:
                                elements = driver.find_elements(By.XPATH, f"//*[contains(text(), '{element['text'][:50]}')]")
                                if elements:
                                    element_obj = elements[0]
                            except:
                                continue
                    
                    if element_obj:
                        driver.execute_script("arguments[0].scrollIntoView(true);", element_obj)
                        time.sleep(1)
                        driver.execute_script("arguments[0].click();", element_obj)
                        time.sleep(2)
                        
                        new_url = driver.current_url
                        if new_url != url:
                            unique_urls.add(new_url)
                            
                except Exception:
                    continue
                    
        finally:
            driver.quit()
            
        return list(unique_urls)

    async def scrape_blog(self, url: str) -> List[ContentItem]:
        """Scrape blog content from a given URL"""
        try:
            # First try with Tavily
            response = self.tavily_client.crawl(
                url=url,
                instructions="Get all blog posts",
                exclude_paths=["^(?!/blog/[^/]+$|/blogs/[^/]+$).*"],
                include_images=True
            )
            
            base_url = self._get_base_url(url)
            
            # If Tavily results are empty, fallback to Selenium
            if not response.get('results', []):
                print(f"No results from Tavily for {url}, falling back to Selenium...")
                unique_urls = self._collect_urls_selenium(url)
                
                # Use Tavily extract for the collected URLs
                all_responses = []
                for i in range(0, len(unique_urls), 20):
                    batch = unique_urls[i:i+20]
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
                    }, base_url, ContentType.BLOG)
                    
                    items.append(cleaned_content)
            else:
                raw_contents = []
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
    
    async def scrape_guides(self, url: str) -> List[ContentItem]:
        """Scrape guides from interviewing.io"""
        base_url = self._get_base_url(url)
        try:
            response = requests.get(url)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            if "companies" in url:
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
            elif "interview-guides" in url:
                # Target class from the question
                target_class = "col-span-2 mb-14 mt-6 grid grid-cols-1 gap-2 sm:grid-cols-2 sm:gap-4 lg:grid-cols-2 lg:gap-6"

                # Find the target div
                target_div = soup.find("div", class_=target_class)

                # Extract all hrefs within that div
                interview_links = []
                if target_div:
                    for a_tag in target_div.find_all("a", href=True):
                        href = a_tag["href"]
                        if href.startswith('/'):
                            href = f"{base_url}{href}"
                        href = href.split('#')[0]
                        interview_links.append(href)
            
                if not interview_links:
                    return []
            else:
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
            raise Exception(f"Error fetching guides: {str(e)}")
        except Exception as e:
            raise Exception(f"Error processing guides: {str(e)}")
    
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
                author="GAYLE L. MCDOWELL, MIKE MROCZKA, ALINE LERNER, NIL MAMANO"
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