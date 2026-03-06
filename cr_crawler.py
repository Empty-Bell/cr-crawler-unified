import os
import time
import csv
import logging
import subprocess
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from webdriver_manager.chrome import ChromeDriverManager

# Basic setup for logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def kill_chrome():
    """Forces all chrome processes to close to prevent profile locking."""
    logger.info("Closing all background Chrome processes...")
    try:
        subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe', '/T'], capture_output=True)
        time.sleep(2)
    except Exception:
        pass

def setup_driver(url=None):
    """Configures and returns the Selenium Chrome driver using a fresh temporary profile."""
    chrome_options = Options()
    
    # Use a completely fresh temporary directory to avoid ANY profile locks
    import tempfile
    temp_dir = tempfile.mkdtemp()
    
    logger.info(f"Using fresh temporary profile at: {temp_dir}")
    chrome_options.add_argument(f"user-data-dir={temp_dir}")
    
    # Standard anti-bot and stability flags
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("--start-maximized")
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Apply stealth via CDP
        driver.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        return driver
    except Exception as e:
        logger.error(f"Failed to launch Chrome: {str(e)}")
        raise e

def expand_all_products(driver):
    """Finds and clicks all 'Show More' buttons using pure JavaScript."""
    logger.info("Starting to expand product list...")
    
    # Check current product count
    initial_products = len(driver.find_elements(By.CSS_SELECTOR, ".row-product"))
    logger.info(f"Initial row count: {initial_products}")

    # Pure JS to click all varieties of expansion buttons
    js_script = """
    let clickedCount = 0;
    let buttons = Array.from(document.querySelectorAll('button')).filter(b => {
        let txt = b.innerText ? b.innerText.toLowerCase() : '';
        return b.classList.contains('btn-expand-toggle') || 
               b.classList.contains('btn-expand') || 
               txt.includes('see all') || 
               txt.includes('view all') || 
               txt.includes('show more') || 
               txt.includes('load more');
    });
    
    buttons.forEach(b => {
        try {
            b.click();
            clickedCount++;
        } catch(e) {}
    });
    return clickedCount;
    """
    
    try:
        # Loop multiple times for lazy loading
        for i in range(4):
            clicked = driver.execute_script(js_script)
            logger.info(f"Expansion pass {i+1}: Clicked {clicked} buttons.")
            if clicked == 0:
                break
            time.sleep(5) # Wait for content to load
    except Exception as e:
        logger.error(f"Expansion error: {e}")

    final_products = len(driver.find_elements(By.CSS_SELECTOR, ".row-product"))
    logger.info(f"Final row count: {final_products}")
    
    if final_products <= initial_products:
        logger.warning("No new products loaded after expansion attempts.")
        try:
            with open("debug_dom_dump.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
        except: pass

def extract_ratings(driver):
    """Extracts data with final robust selector logic based on actual DOM inspection."""
    logger.info("Extracting data via final high-precision JS...")
    
    # Wait for the chart elements to be fully rendered
    time.sleep(3)
    
    js_extract = """
    let all_data = [];
    
    // 1. Get ALL headers from the header row
    let headerRow = document.querySelector('.row-header');
    if (!headerRow) {
        console.error("Header row NOT found.");
        return [[], []];
    }
    
    let headerCells = Array.from(headerRow.querySelectorAll('.cell, div[role="columnheader"]'));
    let headerNames = headerCells.map(c => {
        let name = c.innerText.trim() || c.getAttribute('aria-label') || "";
        if (!name) {
            let tooltip = c.querySelector('.icon__tooltip, [aria-label], [data-title]');
            if (tooltip) name = tooltip.getAttribute('aria-label') || tooltip.getAttribute('data-title');
        }
        return name.replace(/\\n/g, ' ').replace(/\\s+/g, ' ').trim();
    }).filter(n => n && n !== 'Add to Compare' && !n.toLowerCase().includes('green choice'));

    // 2. Row Detection
    let rows = Array.from(document.querySelectorAll('.row-product'));
    if (rows.length === 0) {
        return [headerNames, []];
    }

    rows.forEach(row => {
        let rowObj = {};
        // Get only the primary cells for this row
        let cells = Array.from(row.children).filter(child => child.classList.contains('cell') || child.getAttribute('role') === 'gridcell');
        
        // Match by index but verify content
        headerNames.forEach((h, idx) => {
            let val = "";
            let lowH = h.toLowerCase();
            
            // Consumer Reports header mapping:
            // 0: Add to Compare (Filtered out)
            // 1: Overall Score -> maps to idx 1 in cells (or 0 if h[0] is filtered)
            // But we can be smarter: Find the cell that has data-score OR specific product classes
            
            let cell = null;
            if (lowH.includes('score')) {
                cell = row.querySelector('.cell.overall-score, [data-smoketest*="overall-score"]');
            } else if (lowH === 'product' || lowH.includes('model')) {
                cell = row.querySelector('.cell.product, [data-smoketest*="product"]');
            } else if (lowH === 'price') {
                cell = row.querySelector('.cell.price, [data-smoketest*="price"]');
            } else {
                // For ratings, find by index offset (usually overall score starts at index 1)
                // We'll use the raw cells array
                cell = cells.find(c => (c.getAttribute('aria-label') || "").includes(h)) || cells[idx + 1];
            }

            if (cell) {
                let scoreElem = cell.querySelector('[data-score]');
                if (scoreElem) {
                    val = scoreElem.getAttribute('data-score');
                } else {
                    let nameElem = cell.querySelector('.product__info-display, .product__name, a');
                    if (nameElem && (lowH === 'product' || lowH.includes('model'))) {
                        val = nameElem.innerText.split('\\n')[0].trim();
                    } else {
                        val = cell.innerText.trim();
                    }
                }
                
                if (val === "" && cell.querySelector('a[href*="join"]')) val = "Locked";
                if (lowH.includes('price')) val = val.split('Shop')[0].trim();
                
                rowObj[h] = val.replace(/\\s+/g, ' ').trim();
            }
        });

        if (Object.keys(rowObj).length > 0 && rowObj[headerNames.find(h => h.toLowerCase().includes('product'))]) {
            all_data.push(rowObj);
        }
    });

    return [headerNames, all_data];
    """
    
    try:
        headers, data = driver.execute_script(js_extract)
        logger.info(f"Extraction yield: {len(data)} products, {len(headers)} columns.")
        
        # Deduplication
        unique_data = []
        seen = set()
        pk = next((h for h in headers if "Product" in h.lower()), headers[0])
        for item in data:
            name = item.get(pk)
            if name and name not in seen:
                unique_data.append(item)
                seen.add(name)
        
        return headers, unique_data
    except Exception as e:
        logger.error(f"JS extraction failed: {e}")
        return [], []

def save_to_csv(headers, data, filename="cr_ratings.csv"):
    """Saves the extracted data to a CSV file."""
    if not data:
        logger.warning(f"No data found to save to {filename}.")
        return
        
    with open(filename, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(data)
    logger.info(f"Data saved to {filename} (Total: {len(data)})")

def main():
    print("========================================================")
    print(" Consumer Reports Universal Dynamic Crawler")
    print("========================================================")
    print("원하는 카테고리의 첫 번째 (시작) URL을 입력해 주세요.")
    print("예: https://www.consumerreports.org/appliances/washing-machines/front-load-washer/c28739/")
    
    start_url = input("시작 URL 입력: ").strip()
    if not start_url:
        logger.error("URL이 입력되지 않았습니다. 종료합니다.")
        return
        
    driver = None
    try:
        driver = setup_driver(start_url)
        
        logger.info(f"Checking URL: {start_url}")
        
        # Check if we are still on the startup page and force it
        for i in range(3):
            curr_url = driver.current_url
            logger.info(f"Current URL: {curr_url}")
            if "chrome://" in curr_url or "about:blank" in curr_url or "newtab" in curr_url:
                logger.info(f"Redirection Attempt {i+1}...")
                try:
                    driver.execute_script(f"window.location.replace('{start_url}');")
                except Exception:
                    driver.get(start_url)
                time.sleep(5)
            else:
                break
        
        # --- MANUAL LOGIN PAUSE ---
        logger.info("\n========================================================")
        logger.info("  [!] 사용자 로그인 대기 중...")
        logger.info("  새로 열린 크롬 창에서 로그인을 직접 완료해 주세요.")
        logger.info("  로그인이 완료되고 타겟 페이지가 보이면 터미널에서")
        logger.info("  [Enter] 키를 눌러 크롤링을 시작하세요.")
        logger.info("========================================================\n")
        
        input("로그인 완료 후 터미널 창에서 Enter키를 누르세요...")
        
        logger.info("Proceeding with automated crawling...")

        # Find all category links dynamically
        logger.info("Discovering categories from the top navigation...")
        try:
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".type-nav .nav-btn__wrapper a")))
            nav_links = driver.find_elements(By.CSS_SELECTOR, ".type-nav .nav-btn__wrapper a")
            
            categories = []
            for link in nav_links:
                url = link.get_attribute('href')
                name_elem = link.find_elements(By.CSS_SELECTOR, ".btn-label")
                name = name_elem[0].text.strip() if name_elem else "Unknown"
                if url:
                    categories.append({"name": name, "url": url})
                    
            logger.info(f"Found {len(categories)} categories dynamically: {[c['name'] for c in categories]}")
        except Exception as e:
            logger.warning("No dynamic '.type-nav' categories found. Falling back to single input URL.")
            try:
                # Deduce category name from URL
                cat_id = start_url.rstrip('/').split('/')[-2]
                cat_name = cat_id.replace('-', ' ').title()
            except Exception:
                cat_name = "Single_Category"
            
            categories = [{"name": cat_name, "url": start_url}]

        # Iterate through categories
        for category in categories:
            cat_name = category["name"]
            cat_url = category["url"]
            
            # Skip Washer/Dryer Pairs as requested by USER (different structure)
            if "pair" in cat_name.lower() or "washer-dryer-pairs" in cat_url.lower():
                logger.info(f"Skipping specialized category: {cat_name}")
                continue

            logger.info(f"\n--- Processing Category: {cat_name} ---")
            
            if driver.current_url != cat_url:
                logger.info(f"Navigating to {cat_url}")
                driver.get(cat_url)
                time.sleep(3) # Give it a moment to load
            
            # Wait for chart
            logger.info(f"Waiting for chart to load for {cat_name}...")
            try:
                WebDriverWait(driver, 40).until(EC.presence_of_element_located((By.CLASS_NAME, "chart-wrapper")))
            except TimeoutException:
                logger.warning(f"Timeout waiting for chart on {cat_name}. Skipping to next...")
                continue
            
            # Expand and Crawl
            expand_all_products(driver)
            headers, data = extract_ratings(driver)
            
            if data:
                # Add Category column
                for row in data:
                    row["Category"] = cat_name
                
                if "Category" not in headers:
                    headers.insert(0, "Category")
                
                # File name generation
                safe_name = cat_name.replace(' ', '_').replace('-', '_').replace('/', '_').lower()
                filename = f"cr_ratings_{safe_name}.csv"
                save_to_csv(headers, data, filename=filename)
            else:
                logger.warning(f"No data extracted for {cat_name}.")
            
            logger.info(f"Done with '{cat_name}'. Cooldown before next category...")
            time.sleep(5)

    except Exception as e:
        logger.error(f"오류 발생: {str(e)}")
    finally:
        if driver:
            logger.info("Closing browser...")
            driver.quit()

if __name__ == "__main__":
    main()
