from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import json
import time
import os
import logging
from random import uniform
from webdriver_manager.chrome import ChromeDriverManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('crawler.log'),
        logging.StreamHandler()
    ]
)

BASE_URL = "https://www.renesas.com"
PROGRESS_FILE = 'progress.json'
OUTPUT_FILE = 'renesas_applications.json'

class ReneseaCrawler:
    def __init__(self):
        self.driver = self.setup_driver()
        self.data = self.load_progress()
        self.wait = WebDriverWait(self.driver, 20)

    def setup_driver(self):
        """Set up Chrome driver with appropriate options"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')  # Run in headless mode
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-notifications')
        chrome_options.add_argument('--disable-popup-blocking')
        
        # Add user agent
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver

    def wait_and_get_element(self, by, selector, timeout=20):
        """Wait for element to be present and return it"""
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, selector))
            )
            return element
        except TimeoutException:
            logging.warning(f"Timeout waiting for element: {selector}")
            return None

    def extract_main_categories(self):
        """Extract main categories from the applications page"""
        categories = []
        try:
            # Wait for the categories section to load
            section = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "section.rcards > div.rcards__content"))
            )
            
            # Find all category cards
            cards = section.find_elements(By.CSS_SELECTOR, "div.rcard.rcard--animated")
            
            for card in cards:
                try:
                    title_tag = card.find_element(By.CSS_SELECTOR, "a.rcard__title")
                    categories.append({
                        "title": title_tag.text.strip(),
                        "link": title_tag.get_attribute("href")
                    })
                except NoSuchElementException:
                    continue
                    
        except TimeoutException:
            logging.error("Timeout waiting for main categories")
            
        return categories

    def extract_subcategories(self):
        """Extract subcategories from a category page"""
        subcategories = []
        try:
            # Wait for the subcategories section to load
            section = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.rgrid.rgrid--col3"))
            )
            
            # Find all subcategory cards
            cards = section.find_elements(By.CSS_SELECTOR, "div.rcard.rcard--has-gradient")
            
            for card in cards:
                try:
                    title_tag = card.find_element(By.CSS_SELECTOR, "a.rcard__title")
                    subcategories.append({
                        "title": title_tag.text.strip(),
                        "link": title_tag.get_attribute("href")
                    })
                except NoSuchElementException:
                    continue
                    
        except TimeoutException:
            logging.error("Timeout waiting for subcategories")
            
        return subcategories

    def extract_applications(self):
        """Extract application links from subcategory page"""
        applications = []
        try:
            # Wait for the applications list to load
            app_list = self.wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, "application-category-list"))
            )
            
            # Find all application groups
            groups = app_list.find_elements(By.CLASS_NAME, "application-category-list__group")
            
            for group in groups:
                try:
                    group_name = group.find_element(
                        By.CLASS_NAME, "application-category-list__group-header"
                    ).text.strip()
                    
                    links = group.find_elements(By.CLASS_NAME, "application-category-list__link")
                    
                    for link in links:
                        applications.append({
                            "group": group_name,
                            "title": link.get_attribute("title") or link.text.strip(),
                            "link": link.get_attribute("href"),
                            "nid": link.get_attribute("data-nid"),
                            "uuid": link.get_attribute("data-uuid")
                        })
                except NoSuchElementException:
                    continue
                    
        except TimeoutException:
            logging.error("Timeout waiting for applications")
            
        return applications

    def save_progress(self):
        """Save current progress to file"""
        with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        logging.info(f"Progress saved to {PROGRESS_FILE}")

    def load_progress(self):
        """Load progress from file"""
        if os.path.exists(PROGRESS_FILE):
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                logging.info(f"Loaded progress from {PROGRESS_FILE}")
                return json.load(f)
        return {}

    def save_final_output(self):
        """Save final output to JSON file"""
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        logging.info(f"Final data saved to {OUTPUT_FILE}")

    def scroll_to_element(self, element):
        """Scroll element into view"""
        self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
        time.sleep(uniform(1, 2))  # Wait for scroll to complete

    def crawl(self):
        """Main crawling method"""
        try:
            main_url = f"{BASE_URL}/en/applications"
            logging.info(f"Starting crawl from {main_url}")
            
            # Load main page
            self.driver.get(main_url)
            time.sleep(5)  # Wait for page to load completely
            
            # Get main categories
            categories = self.extract_main_categories()
            logging.info(f"Found {len(categories)} main categories")

            for category in categories:
                category_title = category['title']
                logging.info(f"Processing category: {category_title}")
                
                # Skip if category already processed
                if category_title in self.data:
                    logging.info(f"Skipping already processed category: {category_title}")
                    continue
                    
                self.data[category_title] = {'subcategories': {}}
                
                # Load category page
                self.driver.get(category['link'])
                time.sleep(uniform(3, 5))
                
                # Get subcategories
                subcategories = self.extract_subcategories()
                logging.info(f"Found {len(subcategories)} subcategories in {category_title}")

                for subcategory in subcategories:
                    subcategory_title = subcategory['title']
                    logging.info(f"Processing subcategory: {subcategory_title}")
                    
                    # Skip if subcategory already processed
                    if subcategory_title in self.data[category_title]['subcategories']:
                        logging.info(f"Skipping already processed subcategory: {subcategory_title}")
                        continue
                    
                    # Load subcategory page
                    self.driver.get(subcategory['link'])
                    time.sleep(uniform(3, 5))
                    
                    # Get applications
                    applications = self.extract_applications()
                    logging.info(f"Found {len(applications)} applications in {subcategory_title}")
                    
                    self.data[category_title]['subcategories'][subcategory_title] = {
                        'link': subcategory['link'],
                        'applications': applications
                    }
                    
                    # Save progress after each subcategory
                    self.save_progress()
                    
                    # Random delay between subcategories
                    time.sleep(uniform(3, 6))
                
                # Random delay between categories
                time.sleep(uniform(5, 10))
            
            self.save_final_output()
            logging.info("Crawl completed successfully")
            
        except Exception as e:
            logging.error(f"Error during crawl: {str(e)}", exc_info=True)
            raise
        finally:
            self.driver.quit()

def main():
    try:
        crawler = ReneseaCrawler()
        crawler.crawl()
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    main()