import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
import json
import time
import os
import requests
from random import uniform
import logging
import hashlib
from urllib.parse import urljoin

class RenesasScraper:
    def __init__(self, base_url="https://www.renesas.com"):
        self.driver = self.setup_driver()
        self.wait = WebDriverWait(self.driver, 20)
        self.base_url = base_url
        self.setup_logging()
        
    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('scraper.log'),
                logging.StreamHandler()
            ]
        )

    def setup_driver(self):
        options = uc.ChromeOptions()
        options.add_argument('--no-sandbox')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-gpu')
        options.add_argument('--headless')
        
        driver = uc.Chrome(options=options)
        driver.implicitly_wait(10)
        return driver


    def scrape_subcategory_overview(self, soup, folder_path):
        """Extract overview content from subcategory page"""
        overview_data = {
            'main_text': [],
            'sections': [],
            'images': []
        }
        
        # Find the main content div - try both selectors
        content_div = soup.select_one('.rgrid-wrapper.rsection.wysiwyg.field--name-body') or \
                    soup.select_one('.wysiwyg.field--name-body')
        
        if not content_div:
            return overview_data

        # Get initial paragraphs (main text)
        for p in content_div.find_all('p', recursive=False):
            text = p.get_text(strip=True)
            if text:
                overview_data['main_text'].append(text)

        # Handle any images in main content
        for img in content_div.find_all('img', recursive=False):
            src = img.get('src')
            if src:
                local_path = self.download_image(src, folder_path, 'overview')
                if local_path:
                    overview_data['images'].append({
                        'src': src,
                        'local_path': local_path,
                        'alt': img.get('alt', ''),
                        'type': 'main_content'
                    })

        # Handle the readmore section which contains most content
        readmore_div = content_div.select_one('.readmore.collapsible-enhanced')
        if readmore_div:
            expanded_content = readmore_div.select_one('.readmore__content')
            if expanded_content:
                current_section = None
                for element in expanded_content.select('h2, h3, p, div.rmedia'):
                    if element.name == 'h2':
                        if current_section:
                            overview_data['sections'].append(current_section)
                        current_section = {
                            'title': element.get_text(strip=True),
                            'content': [],
                            'subsections': [],
                            'images': []
                        }
                    elif element.name == 'h3' and current_section:
                        current_section['subsections'].append({
                            'title': element.get_text(strip=True),
                            'content': []
                        })
                    elif element.name == 'p':
                        text = element.get_text(strip=True)
                        if text and current_section:
                            if current_section['subsections']:
                                current_section['subsections'][-1]['content'].append(text)
                            else:
                                current_section['content'].append(text)
                    elif element.name == 'div' and 'rmedia' in element.get('class', []):
                        if current_section:
                            img = element.select_one('img')
                            if img:
                                src = img.get('src')
                                if src:
                                    local_path = self.download_image(src, folder_path, f"section_{self.clean_filename(current_section['title'])}")
                                    if local_path:
                                        img_data = {
                                            'src': src,
                                            'local_path': local_path,
                                            'alt': img.get('alt', ''),
                                            'caption': ''
                                        }
                                        caption = element.select_one('.video-description')
                                        if caption:
                                            img_data['caption'] = caption.get_text(strip=True)
                                        current_section['images'].append(img_data)

                # Add the last section
                if current_section:
                    overview_data['sections'].append(current_section)
        
        return overview_data

    def download_image(self, url, folder_path, prefix='img'):
        """Download image and return local path"""
        if not url:
            return None
            
        try:
            # Make URL absolute if relative
            if url.startswith('/'):
                url = urljoin(self.base_url, url)
                
            # Create hash of URL for filename
            filename = hashlib.md5(url.encode()).hexdigest()
            
            # Determine file extension
            if 'svg' in url:
                ext = '.svg'
            else:
                ext = os.path.splitext(url)[1]
                if not ext:
                    ext = '.jpg'
                    
            local_filename = f"{prefix}_{filename}{ext}"
            local_path = os.path.join(folder_path, local_filename)
            
            # Skip if already downloaded
            if os.path.exists(local_path):
                return local_path
                
            # Download file
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
            return local_path
            
        except Exception as e:
            logging.error(f"Error downloading image {url}: {str(e)}")
            return None

    def scrape_application_overview(self, soup, folder_path):
        """Extract overview content from application page with image downloads"""
        overview_data = {
            'description': {
                'main_text': [],
                'benefits': []
            },
            'applications': [],
            'images': [],
            'comparison': None
        }
        
        # Click tabs and wait for content
        tabs = ['#tab-description', '#tab-comparison', '#tab-applications']
        for tab in tabs:
            try:
                tab_element = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, f'a[href="{tab}"]')))
                self.driver.execute_script("arguments[0].click();", tab_element)
                time.sleep(1)
            except:
                continue

        # Get Description content
        desc_div = soup.select_one('#tab-description .wysiwyg.field--name-body')
        if desc_div:
            in_benefits = False
            for element in desc_div.find_all(['p', 'ul', 'img']):
                if element.name == 'p':
                    text = element.get_text(strip=True)
                    if text:
                        if 'Benefits' in text:
                            in_benefits = True
                        elif not in_benefits:
                            overview_data['description']['main_text'].append(text)
                            
                elif element.name == 'ul' and in_benefits:
                    for li in element.find_all('li'):
                        text = li.get_text(strip=True)
                        if text:
                            overview_data['description']['benefits'].append(text)
                            
                elif element.name == 'img':
                    src = element.get('src')
                    if src:
                        local_path = self.download_image(src, folder_path)
                        if local_path:
                            overview_data['images'].append({
                                'src': src,
                                'local_path': local_path,
                                'alt': element.get('alt', ''),
                                'type': 'content'
                            })

        # Get Applications content
        apps_div = soup.select_one('#tab-applications .field-applications')
        if apps_div:
            for li in apps_div.find_all('li'):
                text = li.get_text(strip=True)
                if text:
                    overview_data['applications'].append(text)

        return overview_data

    def scrape_block_diagram(self, soup, folder_path):
        """Extract SVG diagram and associated product data"""
        diagram_data = {
            'svg': None,
            'svg_path': None,
            'blocks': {}
        }
        
        # Get SVG content
        diagram_div = soup.select_one('div.diagram-section-media')
        if diagram_div:
            svg = diagram_div.select_one('svg')
            if svg:
                # Store full SVG content
                diagram_data['svg'] = str(svg)
                
                # Save SVG to file
                svg_path = os.path.join(folder_path, 'block_diagram.svg')
                try:
                    with open(svg_path, 'w', encoding='utf-8') as f:
                        # Add XML declaration and DOCTYPE if missing
                        if not str(svg).startswith('<?xml'):
                            f.write('<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n')
                        if not str(svg).startswith('<!DOCTYPE'):
                            f.write('<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">\n')
                        f.write(str(svg))
                    diagram_data['svg_path'] = svg_path
                except Exception as e:
                    logging.error(f"Error saving SVG: {str(e)}")
        
        # Extract functional blocks
        block_items = soup.select('.functional-block-items .functional-block-item')
        for block in block_items:
            block_id = block.get('id', '')
            if not block_id:
                continue
            
            block_data = {
                'label': '',
                'categories': []
            }
            
            # Get block label
            label_elem = block.select_one('.functional-block-label')
            if label_elem:
                block_data['label'] = label_elem.get_text(strip=True)
            
            # Get product categories
            for category in block.select('.related-product-category'):
                cat_data = {
                    'title': '',
                    'products': []
                }
                
                title_elem = category.select_one('.related-product-category-title')
                if title_elem:
                    cat_data['title'] = title_elem.get_text(strip=True)
                
                # Get products
                for product in category.select('.related-product-item'):
                    prod_data = self.extract_product_details(product, folder_path)
                    if prod_data:
                        cat_data['products'].append(prod_data)
                
                if cat_data['products']:
                    block_data['categories'].append(cat_data)
            
            if block_data['label'] or block_data['categories']:
                diagram_data['blocks'][block_id] = block_data
        
        return diagram_data


    def extract_product_details(self, product_elem, folder_path):
        """Extract product details including images"""
        try:
            product_data = {
                'title': '',
                'product_id': '',
                'description': '',
                'documentation': [],
                'images': [],
                'buy_sample_link': ''
            }
            
            # Title and ID
            title_elem = product_elem.select_one('.product-title-data a')
            if title_elem:
                product_data['product_id'] = title_elem.get_text(strip=True)
                product_data['title'] = title_elem.get('title', '')
            
            # Description
            desc_elem = product_elem.select_one('.product-description')
            if desc_elem:
                product_data['description'] = desc_elem.get_text(strip=True)
            
            # Product images
            for img in product_elem.select('img'):
                src = img.get('src')
                if src:
                    local_path = self.download_image(src, folder_path, 'product')
                    if local_path:
                        product_data['images'].append({
                            'src': src,
                            'local_path': local_path,
                            'alt': img.get('alt', '')
                        })
            
            # Documentation
            for doc in product_elem.select('.featured-document a'):
                doc_data = {
                    'title': doc.get_text(strip=True),
                    'url': doc.get('href', ''),
                    'doc_id': doc.get('data-doc', ''),
                    'language': doc.get('data-doc-lang', ''),
                    'external': doc.get('data-external-doc', '') == 'true'
                }
                product_data['documentation'].append(doc_data)
            
            # Buy/Sample link
            buy_link = product_elem.select_one('.buy-sample a')
            if buy_link:
                product_data['buy_sample_link'] = buy_link.get('href', '')
            
            return product_data
            
        except Exception as e:
            logging.error(f"Error extracting product details: {str(e)}")
            return None

    def scrape_page(self, url, output_dir):
        """Scrape a page and save all content including images"""
        try:
            logging.info(f"Scraping page: {url}")
            self.driver.get(url)
            time.sleep(uniform(3, 5))
            
            # Create page-specific output directory
            os.makedirs(output_dir, exist_ok=True)
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # Get page content
            content = {
                'overview': self.scrape_application_overview(soup, output_dir),
                'block_diagram': self.scrape_block_diagram(soup, output_dir)
            }
            
            # Save JSON data
            with open(os.path.join(output_dir, 'content.json'), 'w', encoding='utf-8') as f:
                json.dump(content, f, indent=2, ensure_ascii=False)
            
            return content
            
        except Exception as e:
            logging.error(f"Error scraping page {url}: {str(e)}")
            return None

    def clean_filename(self, filename):
        """Clean string for filename"""
        cleaned = filename.replace('/', ' ').replace('\\', ' ')
        cleaned = ''.join(char for char in cleaned if char.isalnum() or char in (' ', '-', '_'))
        return ' '.join(cleaned.split())

    def main(self, urls_file, output_base_dir='scraped_data'):
        """Main execution method"""
        try:
            # Load URLs
            with open(urls_file, 'r') as f:
                urls_data = json.load(f)
            
            # Create base output directory
            os.makedirs(output_base_dir, exist_ok=True)
            
            # Process URLs
            for category, category_data in urls_data.items():
                category_dir = os.path.join(output_base_dir, self.clean_filename(category))
                
                for subcategory, subcat_data in category_data['subcategories'].items():
                    subcat_dir = os.path.join(category_dir, self.clean_filename(subcategory))
                    
                    for app in subcat_data['applications']:
                        app_dir = os.path.join(subcat_dir, self.clean_filename(app['title']))
                        self.scrape_page(app['link'], app_dir)
                        time.sleep(uniform(2, 4))
                    
                    time.sleep(uniform(3, 5))
            
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}", exc_info=True)
            raise
        
        finally:
            self.driver.quit()

if __name__ == "__main__":
    scraper = RenesasScraper()
    scraper.main('renesas_applications.json')