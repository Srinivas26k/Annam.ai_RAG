import os
import time
import random
import re
import requests
import trafilatura
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from duckduckgo_search import DDGS
from bs4 import BeautifulSoup

def setup_selenium_driver():
    """
    Set up and return a Selenium WebDriver with headless Chrome.
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    # Initialize the driver
    driver = webdriver.Chrome(options=chrome_options)
    return driver

def search_agriculture_info(query, num_results=5):
    """
    Search for agriculture information using DuckDuckGo with improved fallback options.
    
    Args:
        query (str): Search query
        num_results (int): Number of results to return
        
    Returns:
        list: List of dictionaries containing search results with title and URL
    """
    # Ensure the query is related to Indian agriculture
    if "india" not in query.lower() and "indian" not in query.lower():
        query = f"indian agriculture {query}"
    else:
        query = f"agriculture {query}"
    
    print(f"Searching for: {query}")
    search_results = []
    
    # List of reliable Indian agriculture websites to prioritize
    agriculture_domains = [
        'agricoop.nic.in', 'farmer.gov.in', 'agritech.tnau.ac.in', 'iari.res.in',
        'icar.org.in', 'agmarknet.gov.in', 'krishijagran.com', 'agriculture.gov.in',
        'nabard.org', 'farmech.dac.gov.in', 'agrionline.nic.in', 'vikaspedia.in',
        'agrifarming.in', 'nbpgr.ernet.in', 'manage.gov.in', 'nfsm.gov.in'
    ]
    
    # Try DuckDuckGo first
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=num_results*3))  # Get more results to filter
            
            # Expand agriculture keywords list
            agriculture_keywords = [
                'agriculture', 'farming', 'crop', 'farmer', 'soil', 'harvest', 
                'cultivation', 'irrigation', 'seed', 'fertilizer', 'pesticide', 'kisan', 
                'organic farming', 'agronomy', 'horticulture', 'livestock', 'dairy',
                'agricultural', 'farm', 'agri', 'rural', 'india', 'indian', 'krishi',
                'mandi', 'yield', 'monsoon', 'rabi', 'kharif', 'agribusiness', 'fpo',
                'agrarian', 'pesticide', 'herbicide', 'agroforestry', 'agroecology'
            ]
            
            if results:
                print(f"Found {len(results)} initial results from DuckDuckGo")
                
                # First priority: domains from our reliable list
                for result in results:
                    url = result.get('href', '')
                    if any(domain in url for domain in agriculture_domains) and len(search_results) < num_results:
                        search_results.append({
                            'title': result.get('title', ''),
                            'url': url
                        })
                
                # Second priority: relevance based on keywords
                if len(search_results) < num_results:
                    for result in results:
                        if result.get('href', '') not in [r['url'] for r in search_results]:  # Avoid duplicates
                            combined_text = (result.get('title', '') + ' ' + result.get('body', '')).lower()
                            relevance_score = sum(1 for keyword in agriculture_keywords if keyword in combined_text)
                            
                            if relevance_score >= 2 and len(search_results) < num_results:
                                search_results.append({
                                    'title': result.get('title', ''),
                                    'url': result.get('href', '')
                                })
            else:
                print("DuckDuckGo returned no results")
    except Exception as e:
        print(f"Error searching DuckDuckGo: {e}")
    
    # If we still need more results, try Google as fallback
    if len(search_results) < num_results:
        try:
            print("Attempting Google search fallback")
            driver = setup_selenium_driver()
            driver.get(f"https://www.google.com/search?q={query}")
            time.sleep(3)  # Allow page to load
            
            search_elements = driver.find_elements(By.CSS_SELECTOR, "div.g")
            
            if search_elements:
                for element in search_elements:
                    if len(search_results) >= num_results:
                        break
                    
                    try:
                        title_elem = element.find_element(By.CSS_SELECTOR, "h3")
                        link_elem = element.find_element(By.CSS_SELECTOR, "a")
                        title = title_elem.text
                        url = link_elem.get_attribute("href")
                        
                        # Avoid duplicate URLs
                        if title and url and url not in [r['url'] for r in search_results]:
                            search_results.append({
                                'title': title,
                                'url': url
                            })
                    except Exception as inner_e:
                        print(f"Error extracting Google search result: {inner_e}")
            else:
                print("No Google search elements found")
            
            driver.quit()
        except Exception as fallback_e:
            print(f"Google fallback search method failed: {fallback_e}")
    
    # If we still have no results, add some reliable agriculture websites directly
    if not search_results:
        print("No search results found, adding reliable agriculture websites directly")
        default_websites = [
            {'title': 'Indian Ministry of Agriculture & Farmers Welfare', 'url': 'https://agricoop.nic.in/'},
            {'title': 'Indian Council of Agricultural Research', 'url': 'https://icar.org.in/'},
            {'title': 'Farmers Portal of India', 'url': 'https://farmer.gov.in/'},
            {'title': 'Tamil Nadu Agricultural University', 'url': 'https://agritech.tnau.ac.in/'},
            {'title': 'Krishi Jagran - Agriculture Information Portal', 'url': 'https://krishijagran.com/'}
        ]
        
        # Add as many as needed to meet the requested number
        search_results.extend(default_websites[:min(num_results, len(default_websites))])
    
    print(f"Returning {len(search_results)} search results")
    return search_results

def scrape_url(url):
    """
    Scrape content from a URL using both Trafilatura and Selenium as fallback.
    
    Args:
        url (str): URL to scrape
        
    Returns:
        str: Extracted content from the URL
    """
    # Validate URL
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    # Try with Trafilatura first (faster and cleaner extraction)
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            content = trafilatura.extract(downloaded, include_links=True, include_formatting=True, include_tables=True)
            if content and len(content) > 100:  # Ensure we got meaningful content
                print(f"Successfully extracted content with Trafilatura from {url}")
                return content
    except Exception as e:
        print(f"Trafilatura extraction failed for {url}: {e}")
    
    # Fallback to Selenium if Trafilatura fails
    try:
        print(f"Attempting Selenium extraction for {url}")
        driver = setup_selenium_driver()
        driver.get(url)
        
        # Wait for page to load
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # Scroll down to load dynamic content
        for i in range(5):  # Increased scroll attempts
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/5*{});".format(i+1))
            time.sleep(1.5)  # Longer wait time
        
        # Get the page source and parse with BeautifulSoup
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Remove unwanted elements
        for unwanted in soup.select('script, style, nav, footer, header, aside, iframe, noscript'):
            unwanted.extract()
        
        # Try multiple content extraction strategies
        content = ""
        
        # Strategy 1: Look for common article containers
        main_content = soup.select_one('article, main, .content, .main-content, .post-content, .article-content, .entry-content, .page-content, #content, #main-content')
        
        if main_content:
            paragraphs = main_content.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'td', 'th', 'div.text'])
            content = '\n\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
        
        # Strategy 2: If we couldn't find a container or got little content, try all paragraphs
        if not content or len(content) < 200:
            paragraphs = soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            content = '\n\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True) and len(p.get_text(strip=True)) > 20])
        
        # Strategy 3: If still not much content, use divs with substantial text
        if not content or len(content) < 200:
            text_divs = [div.get_text(strip=True) for div in soup.find_all('div') if len(div.get_text(strip=True)) > 100]
            content = '\n\n'.join(text_divs)
        
        driver.quit()
        
        if content and len(content) > 100:
            print(f"Successfully extracted content with Selenium from {url}")
            return content
        else:
            # Last effort - try requests + BeautifulSoup
            try:
                print(f"Attempting direct requests extraction for {url}")
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                }
                response = requests.get(url, headers=headers, timeout=15)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                for unwanted in soup.select('script, style, nav, footer, header, aside'):
                    unwanted.extract()
                
                paragraphs = soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li'])
                content = '\n\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
                
                if content and len(content) > 100:
                    print(f"Successfully extracted content with direct requests from {url}")
                    return content
            except Exception as req_e:
                print(f"Direct requests extraction failed for {url}: {req_e}")
            
            print(f"Failed to extract meaningful content from {url}")
            return None
    except Exception as e:
        print(f"Selenium extraction failed for {url}: {e}")
        return None

def is_agriculture_content(text):
    """
    Determine if the content is related to agriculture.
    
    Args:
        text (str): Text content to analyze
        
    Returns:
        bool: True if content is related to agriculture, False otherwise
    """
    # List of agriculture-related keywords
    agriculture_keywords = [
        'agriculture', 'farming', 'crop', 'farmer', 'soil', 'harvest', 
        'cultivation', 'irrigation', 'seed', 'fertilizer', 'pesticide', 
        'organic farming', 'agronomy', 'horticulture', 'livestock', 
        'agricultural', 'farm', 'agri', 'rural', 'india', 'indian'
    ]
    
    # Check if any agriculture keywords are present in the text
    text_lower = text.lower()
    keyword_count = sum(1 for keyword in agriculture_keywords if keyword in text_lower)
    
    # Consider it agriculture-related if at least 2 keywords are present
    return keyword_count >= 2
