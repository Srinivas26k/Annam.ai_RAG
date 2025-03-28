import os
import re
import requests
import zipfile
import shutil
import base64
import traceback
from io import BytesIO
from bs4 import BeautifulSoup
import logging
from urllib.parse import urljoin, urlparse
import pandas as pd
import PyPDF2
from PIL import Image, ImageFile
ImageFile.LOAD_TRUNCATED_IMAGES = True

class AdvancedScraper:
    def __init__(self, base_url, output_dir='scraped_data', max_pages=50):
        """
        Initialize an advanced web scraper that handles text, tables, images, and PDFs

        Args:
            base_url (str): Starting URL to scrape
            output_dir (str): Directory to save scraped content
            max_pages (int): Maximum number of pages to scrape
        """
        # Setup logging
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s - %(levelname)s: %(message)s')
        self.logger = logging.getLogger(__name__)

        # Configuration
        self.base_url = base_url
        self.main_output_dir = output_dir
        self.output_dir = os.path.join(output_dir, 'content')
        self.max_pages = max_pages
        
        # Set up dynamic directories
        self.images_dir = None
        self.tables_dir = None
        self.pdfs_dir = None
        
        # Flags for content types
        self.has_images = False
        self.has_tables = False
        self.has_pdfs = False

        # Create main output directory
        os.makedirs(self.output_dir, exist_ok=True)

        # Tracking
        self.visited_urls = set()
        self.image_count = 0
        self.table_count = 0
        self.pdf_count = 0
        self.text_count = 0
        
        # Headers for requests
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def clean_text(self, text):
        """
        Clean and normalize extracted text

        Args:
            text (str): Raw text to clean

        Returns:
            str: Cleaned text
        """
        # Remove extra whitespaces, normalize line breaks
        if text:
            text = re.sub(r'\s+', ' ', text).strip()
        return text

    def is_valid_url(self, url):
        """
        Validate if URL should be scraped

        Args:
            url (str): URL to validate

        Returns:
            bool: Whether URL is valid for scraping
        """
        try:
            parsed = urlparse(url)
            base_netloc = urlparse(self.base_url).netloc
            
            # PDF URLs are valid for download but not for scraping content
            if url.lower().endswith('.pdf'):
                return True
                
            return (
                parsed.scheme in ['http', 'https'] and
                parsed.netloc == base_netloc and
                url not in self.visited_urls and
                not any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif'])
            )
        except Exception as e:
            self.logger.warning(f"URL validation error: {e}")
            return False

    def extract_tables(self, soup, url):
        """
        Extract tables from HTML and save as CSV

        Args:
            soup (BeautifulSoup): Parsed HTML
            url (str): Source URL

        Returns:
            list: List of table info dictionaries
        """
        tables_info = []
        tables = soup.find_all('table')
        
        # Only proceed if tables are found
        if not tables:
            return tables_info
            
        # Create tables directory if this is the first table found
        if not self.has_tables:
            self.tables_dir = os.path.join(self.main_output_dir, 'tables')
            os.makedirs(self.tables_dir, exist_ok=True)
            self.has_tables = True
        
        for i, table in enumerate(tables):
            try:
                # Convert table to pandas dataframe
                dfs = pd.read_html(str(table))
                
                if dfs and len(dfs) > 0:
                    df = dfs[0]
                    
                    # Skip very small tables (likely navigation or layout tables)
                    if len(df) <= 1 and len(df.columns) <= 1:
                        continue
                    
                    # Generate filename
                    table_filename = f"table_{self.table_count}_{i}.csv"
                    table_path = os.path.join(self.tables_dir, table_filename)
                    
                    # Save as CSV
                    df.to_csv(table_path, index=False)
                    
                    # Get table caption if exists
                    caption = table.find('caption')
                    caption_text = caption.get_text() if caption else f"Table {i+1}"
                    
                    tables_info.append({
                        'filename': table_filename,
                        'path': table_path,
                        'caption': self.clean_text(caption_text),
                        'rows': len(df),
                        'columns': len(df.columns)
                    })
                    
                    self.table_count += 1
                    self.logger.info(f"Saved table: {table_path}")
            
            except Exception as e:
                self.logger.warning(f"Error processing table {i} from {url}: {e}")
        
        return tables_info

    def extract_images(self, soup, url):
        """
        Extract images from HTML and save them

        Args:
            soup (BeautifulSoup): Parsed HTML
            url (str): Source URL

        Returns:
            list: List of image info dictionaries
        """
        images_info = []
        img_tags = soup.find_all('img')
        
        # Skip if no images found
        if not img_tags:
            return images_info
        
        # For image processing
        valid_images = []
        for i, img in enumerate(img_tags):
            try:
                img_url = img.get('src', '')
                if not img_url:
                    continue
                
                # Get absolute URL
                img_url = urljoin(url, img_url)
                
                # Skip small icons, spacers, etc.
                if any(skip in img_url.lower() for skip in ['icon', 'logo', 'spacer', 'button']):
                    continue
                    
                # Add to valid images for processing
                valid_images.append((i, img, img_url))
            except Exception as e:
                self.logger.warning(f"Error processing image URL {i} from {url}: {e}")
        
        # If no valid images after filtering, return empty list
        if not valid_images:
            return images_info
            
        # Create images directory if this is the first valid image found
        if not self.has_images:
            self.images_dir = os.path.join(self.main_output_dir, 'images')
            os.makedirs(self.images_dir, exist_ok=True)
            self.has_images = True
        
        # Process valid images
        for i, img, img_url in valid_images:
            try:
                # Download image
                img_response = requests.get(img_url, headers=self.headers, timeout=10)
                img_response.raise_for_status()
                
                # Check if image is too small (likely an icon)
                if int(img_response.headers.get('Content-Length', '0')) < 5000:  # Skip images less than 5KB
                    continue
                
                # Determine image format and create filename
                content_type = img_response.headers.get('Content-Type', '')
                ext = 'jpg'  # Default extension
                
                if 'png' in content_type.lower():
                    ext = 'png'
                elif 'gif' in content_type.lower():
                    ext = 'gif'
                elif 'jpeg' in content_type.lower() or 'jpg' in content_type.lower():
                    ext = 'jpg'
                
                img_filename = f"image_{self.image_count}.{ext}"
                img_path = os.path.join(self.images_dir, img_filename)
                
                # Save image
                with open(img_path, 'wb') as f:
                    f.write(img_response.content)
                
                # Get alt text and nearby captions
                alt_text = img.get('alt', '')
                nearby_caption = None
                
                # Look for nearby figcaption
                parent_fig = img.find_parent('figure')
                if parent_fig:
                    figcaption = parent_fig.find('figcaption')
                    if figcaption:
                        nearby_caption = self.clean_text(figcaption.get_text())
                
                # If no figcaption, check for title attribute
                if not nearby_caption:
                    nearby_caption = img.get('title', '')
                
                images_info.append({
                    'filename': img_filename,
                    'path': img_path,
                    'url': img_url,
                    'alt_text': self.clean_text(alt_text),
                    'caption': self.clean_text(nearby_caption)
                })
                
                self.image_count += 1
                self.logger.info(f"Saved image: {img_path}")
            
            except Exception as e:
                self.logger.warning(f"Error downloading image {i} from {url}: {e}")
        
        return images_info

    def download_pdf(self, url):
        """
        Download and extract text from PDF

        Args:
            url (str): URL of PDF to download

        Returns:
            dict: PDF info dictionary
        """
        try:
            # Download PDF
            response = requests.get(url, headers=self.headers, timeout=20)
            response.raise_for_status()
            
            # Create PDFs directory if this is the first PDF
            if not self.has_pdfs:
                self.pdfs_dir = os.path.join(self.main_output_dir, 'pdfs')
                os.makedirs(self.pdfs_dir, exist_ok=True)
                self.has_pdfs = True
            
            # Generate filename
            pdf_filename = f"document_{self.pdf_count}.pdf"
            pdf_path = os.path.join(self.pdfs_dir, pdf_filename)
            
            # Save PDF
            with open(pdf_path, 'wb') as f:
                f.write(response.content)
            
            # Extract text from PDF
            text = ""
            with open(pdf_path, 'rb') as f:
                try:
                    pdf_reader = PyPDF2.PdfReader(f)
                    for page_num in range(len(pdf_reader.pages)):
                        text += pdf_reader.pages[page_num].extract_text() + "\n\n"
                except Exception as e:
                    self.logger.warning(f"Error extracting text from PDF {url}: {e}")
            
            # Save text in separate file
            text_filename = f"document_{self.pdf_count}_text.txt"
            text_path = os.path.join(self.pdfs_dir, text_filename)
            
            with open(text_path, 'w', encoding='utf-8') as f:
                f.write(text)
            
            pdf_info = {
                'filename': pdf_filename,
                'path': pdf_path,
                'url': url,
                'text_filename': text_filename,
                'text_path': text_path,
                'extracted_text': text
            }
            
            self.pdf_count += 1
            self.logger.info(f"Saved PDF: {pdf_path}")
            
            return pdf_info
        
        except Exception as e:
            self.logger.error(f"Error downloading PDF {url}: {e}")
            return None

    def extract_page_content(self, url):
        """
        Extract content from a single page including text, tables, and images

        Args:
            url (str): URL to scrape

        Returns:
            dict: Dictionary with all extracted content
        """
        page_content = {
            'url': url,
            'text': "",
            'tables': [],
            'images': [],
            'pdf': None,
            'headers': []
        }
        
        try:
            # Handle PDF files
            if url.lower().endswith('.pdf'):
                pdf_info = self.download_pdf(url)
                if pdf_info:
                    page_content['pdf'] = pdf_info
                return page_content
            
            # Use requests with timeout and user agent
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()

            # Parse with BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract page title
            title = soup.title.string if soup.title else "Untitled Page"
            page_content['title'] = self.clean_text(title)
            
            # Extract tables before removing elements
            page_content['tables'] = self.extract_tables(soup, url)
            
            # Extract images
            page_content['images'] = self.extract_images(soup, url)
            
            # Remove script, style, navigation elements for better text extraction
            for script in soup(['script', 'style', 'nav', 'header', 'footer']):
                script.decompose()

            # Extract headings for structure
            headings = []
            for h_level in range(1, 7):
                for heading in soup.find_all(f'h{h_level}'):
                    headings.append({
                        'level': h_level,
                        'text': self.clean_text(heading.get_text())
                    })
            page_content['headers'] = headings

            # Extract text from paragraphs and other elements
            texts = []
            
            # Extract from different text-containing elements
            text_elements = ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'span', 'div', 'article']
            for element in text_elements:
                elements = soup.find_all(element)
                for elem in elements:
                    # Skip empty elements or those already included in other elements
                    if not elem.get_text().strip() or elem.parent.name in text_elements:
                        continue
                    texts.append(self.clean_text(elem.get_text()))

            # Join and clean text
            content = '\n\n'.join(texts)
            page_content['text'] = content

            return page_content

        except requests.RequestException as e:
            self.logger.error(f"Error scraping {url}: {e}")
            return page_content

    def save_content_to_file(self, page_content):
        """
        Save all extracted content to files

        Args:
            page_content (dict): Dictionary with all content

        Returns:
            dict: Paths to saved files
        """
        url = page_content['url']
        safe_url = re.sub(r'[^\w\-_\. ]', '_', url)[:50]
        
        # Generate filenames
        text_filename = f"text_{self.text_count}_{safe_url}.txt"
        text_path = os.path.join(self.output_dir, text_filename)
        
        # Save text content
        with open(text_path, 'w', encoding='utf-8') as f:
            f.write(f"SOURCE URL: {url}\n")
            f.write(f"TITLE: {page_content.get('title', 'No Title')}\n\n")
            
            # Write headings for structure
            f.write("DOCUMENT STRUCTURE:\n")
            for header in page_content['headers']:
                indent = '  ' * (header['level'] - 1)
                f.write(f"{indent}- {header['text']}\n")
            f.write("\n")
            
            # Write main content
            f.write("CONTENT:\n")
            f.write(page_content['text'])
            f.write("\n\n")
            
            # Add references to tables
            if page_content['tables']:
                f.write("TABLES:\n")
                for i, table in enumerate(page_content['tables']):
                    f.write(f"{i+1}. {table['caption']} - {table['rows']}x{table['columns']} - {table['filename']}\n")
                f.write("\n")
            
            # Add references to images
            if page_content['images']:
                f.write("IMAGES:\n")
                for i, image in enumerate(page_content['images']):
                    caption = image['caption'] or image['alt_text'] or f"Image {i+1}"
                    f.write(f"{i+1}. {caption} - {image['filename']}\n")
                f.write("\n")
            
            # Add reference to PDF if exists
            if page_content['pdf']:
                f.write("PDF DOCUMENT:\n")
                f.write(f"File: {page_content['pdf']['filename']}\n")
                f.write(f"Text extract: {page_content['pdf']['text_filename']}\n")
        
        self.text_count += 1
        self.logger.info(f"Saved text: {text_path}")
        
        return {
            'text_path': text_path,
            'tables_paths': [t['path'] for t in page_content['tables']],
            'images_paths': [i['path'] for i in page_content['images']],
            'pdf_path': page_content['pdf']['path'] if page_content['pdf'] else None
        }

    def create_zip_archive(self):
        """
        Create a zip archive of all scraped content

        Returns:
            str: Path to the zip file
        """
        zip_path = os.path.join(os.path.dirname(self.main_output_dir), f"{os.path.basename(self.main_output_dir)}.zip")
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(self.main_output_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, os.path.dirname(self.main_output_dir))
                    zipf.write(file_path, arcname)
        
        self.logger.info(f"Created ZIP archive: {zip_path}")
        return zip_path

    def get_zip_as_base64(self):
        """
        Get the zip archive as base64 for browser download

        Returns:
            str: Base64 encoded zip data
        """
        zip_path = self.create_zip_archive()
        
        with open(zip_path, 'rb') as f:
            data = f.read()
            return base64.b64encode(data).decode('utf-8')

    def scrape(self):
        """
        Main scraping method that performs the recursive crawl

        Returns:
            dict: Summary of scraped content
        """
        all_saved_paths = []
        
        def recursive_scrape(url, depth=0):
            # Prevent infinite recursion and respect max pages
            if depth >= 3 or len(self.visited_urls) >= self.max_pages:
                return

            # Skip already visited URLs
            if url in self.visited_urls:
                return
                
            # Validate URL
            if not self.is_valid_url(url):
                return

            self.visited_urls.add(url)
            self.logger.info(f"Scraping: {url}")

            # Extract and save content
            page_content = self.extract_page_content(url)
            
            if page_content['text'] or page_content['tables'] or page_content['images'] or page_content['pdf']:
                saved_paths = self.save_content_to_file(page_content)
                all_saved_paths.append(saved_paths)

            # Find and process links (skip for PDFs)
            if not url.lower().endswith('.pdf'):
                try:
                    response = requests.get(url, headers=self.headers, timeout=10)
                    soup = BeautifulSoup(response.text, 'html.parser')
                    links = [urljoin(url, link.get('href')) for link in soup.find_all('a', href=True)]

                    # Recursively scrape found links
                    for link in links:
                        recursive_scrape(link, depth + 1)

                except Exception as e:
                    self.logger.warning(f"Error finding links: {e}")
                    traceback.print_exc()

        # Start scraping from base URL
        try:
            recursive_scrape(self.base_url)
        except Exception as e:
            self.logger.error(f"Scraping error: {e}")
            traceback.print_exc()

        # Create summary file
        summary_path = os.path.join(self.main_output_dir, 'scraping_summary.txt')
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(f"SCRAPING SUMMARY\n")
            f.write(f"===============\n\n")
            f.write(f"Base URL: {self.base_url}\n")
            f.write(f"Pages scraped: {len(self.visited_urls)}\n")
            f.write(f"Text files saved: {self.text_count}\n")
            f.write(f"Tables extracted: {self.table_count}\n")
            f.write(f"Images downloaded: {self.image_count}\n")
            f.write(f"PDFs downloaded: {self.pdf_count}\n\n")
            
            f.write(f"Visited URLs:\n")
            for url in self.visited_urls:
                f.write(f"- {url}\n")

        # Create zip file
        zip_path = self.create_zip_archive()
        
        # Log summary
        self.logger.info(f"Scraping completed.")
        self.logger.info(f"Text files saved: {self.text_count}")
        self.logger.info(f"Tables extracted: {self.table_count}")
        self.logger.info(f"Images downloaded: {self.image_count}")
        self.logger.info(f"PDFs downloaded: {self.pdf_count}")
        self.logger.info(f"ZIP archive created: {zip_path}")
        
        return {
            'pages_scraped': len(self.visited_urls),
            'text_files': self.text_count,
            'tables': self.table_count,
            'images': self.image_count,
            'pdfs': self.pdf_count,
            'zip_path': zip_path,
            'visited_urls': list(self.visited_urls)
        }
        
    def cleanup(self):
        """
        Clean up temporary files after creating zip
        """
        try:
            shutil.rmtree(self.main_output_dir)
            self.logger.info(f"Cleaned up temporary files in {self.main_output_dir}")
        except Exception as e:
            self.logger.warning(f"Error cleaning up: {e}")


def main(url, max_pages=50):
    """
    Main execution function

    Args:
        url (str): URL to scrape
        max_pages (int): Maximum number of pages to scrape
        
    Returns:
        dict: Summary of scraping results
    """
    try:
        output_dir = os.path.join('scraped_content', 'temp_data')
        scraper = AdvancedScraper(
            base_url=url,
            output_dir=output_dir,
            max_pages=max_pages
        )
        summary = scraper.scrape()
        
        # Return the scraping results
        return {
            'success': True,
            'summary': summary,
            'zip_path': summary['zip_path'],
            'message': f"Successfully scraped {summary['pages_scraped']} pages."
        }
        
    except Exception as e:
        traceback.print_exc()
        return {
            'success': False,
            'message': f"Scraping failed: {str(e)}",
            'error': traceback.format_exc()
        }


if __name__ == "__main__":
    # Example usage
    result = main("https://www.kaggle.com/datasets/mateibejan/15000-gutenberg-books")
    print(result)