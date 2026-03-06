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
    logger.info("Starting to expand all product lists using JavaScript...")
    
    # Scroll a bit to trigger lazy loading if any
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
    time.sleep(1)
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(1)
    
    # Check how many products we start with
    initial_products = len(driver.find_elements(By.CSS_SELECTOR, ".row-product"))
    logger.info(f"Products BEFORE expansion: {initial_products}")

    # Use a pure JS approach to find and click ALL matching buttons instantly
    js_script = """
    let clickedCount = 0;
    
    // 1. First, try the exact selector path patterns provided by the user
    let user_selectors = [
        '.chart-ratings-wrapper .row-footer button',
        '.chart-wrapper.is-collapsed .row-footer button',
        '.row-footer button'
    ];
    let buttons = [];
    user_selectors.forEach(sel => {
        document.querySelectorAll(sel).forEach(b => buttons.push(b));
    });
    
    // 2. Fallback: find buttons through class or text just in case
    document.querySelectorAll('button.btn-expand-toggle, button').forEach(b => {
        let text = b.innerText ? b.innerText.toLowerCase() : '';
        if (b.classList.contains('btn-expand-toggle') || text.includes('see all') || text.includes('view all') || text.includes('show more')) {
            buttons.push(b);
        }
    });

    // Deduplicate array of buttons
    let uniqueButtons = [...new Set(buttons)];
    
    uniqueButtons.forEach(b => {
        // Try to click the inner div if it exists (like the user selector ends with button > div), else the button
        let target = b.querySelector('div') || b;
        try {
            target.click();
            clickedCount++;
        } catch(e) {
            b.click();
            clickedCount++;
        }
    });
    return clickedCount;
    """
    
    try:
        # Run it a few times to ensure nested/lazy loaded buttons are caught
        for i in range(5):
            clicked = driver.execute_script(js_script)
            logger.info(f"JS Click pass {i+1}: Clicked {clicked} buttons.")
            if clicked == 0:
                break
            time.sleep(4) # Wait for network requests
            
    except Exception as e:
        logger.error(f"Error during JS expansion: {e}")
        
    final_products = len(driver.find_elements(By.CSS_SELECTOR, ".row-product"))
    logger.info(f"Products AFTER expansion: {final_products}")
    
    # Failsafe: If no new products appeared, dump the DOM for debugging
    if final_products <= initial_products:
        logger.warning("No new products loaded after attempting expansion!")
        dump_path = os.path.join(os.getcwd(), "debug_dom_dump.html")
        try:
            with open(dump_path, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            logger.info(f"Saved DOM to {dump_path} for your inspection.")
        except Exception as e:
            logger.error(f"Failed to save DOM dump: {e}")


def extract_ratings(driver):
    """Extracts all data using a high-stability index-based mapping, 
    customized for the unique nested row structure of Consumer Reports."""
    logger.info("Extracting data via high-stability scraper...")
    
    # Critical: Wait for Vue components to fully settle
    time.sleep(5)
    
    js_extract = """
    let all_data = [];
    
    // 1. Identify the Main Header Row
    // We look for the one with actual text content to avoid pinned empty headers
    let headerRows = Array.from(document.querySelectorAll('.row-header, [role="rowheader"]'));
    let headerRow = headerRows.find(r => r.innerText.includes('Product') && r.innerText.includes('Overall Score')) || headerRows[0];
    
    if (!headerRow) {
        console.error("Header row not found.");
        return [[], []];
    }
    
    let headerCells = Array.from(headerRow.querySelectorAll('.cell, div[role="columnheader"]'));
    let headers = headerCells.map(cell => {
        let text = cell.getAttribute('aria-label') || cell.innerText.trim();
        if (!text) {
             let tooltip = cell.querySelector('.icon__tooltip, [data-title], [aria-label]');
             if (tooltip) text = tooltip.getAttribute('aria-label') || tooltip.getAttribute('data-title');
        }
        return text ? text.replace(/\\n/g, ' ').replace(/\\s+/g, ' ').trim() : "";
    });

    // Determine key column indices for special handling
    let productIdx = headers.findIndex(h => h.toLowerCase() === 'product');
    let priceIdx = headers.findIndex(h => h.toLowerCase().includes('price'));
    let overallScoreIdx = headers.findIndex(h => h.toLowerCase().includes('overall score'));

    // 2. Identify Product Rows
    // We look for containers that have a data-id or class row-product
    let rows = Array.from(document.querySelectorAll('.row-product')).filter(r => r.offsetHeight > 0);
    
    rows.forEach(row => {
        let rowObj = {};
        let cells = Array.from(row.querySelectorAll('.cell, div[role="gridcell"]'));
        
        // If the row structure is deeply nested, cells might be empty. 
        // We ensure we match the count to the headers.
        headers.forEach((h, idx) => {
            if (!h || h === 'Add to Compare' || h.toLowerCase().includes('green choice')) return;
            
            if (idx < cells.length) {
                let cell = cells[idx];
                let val = "";
                
                // Extraction Priority:
                // 1. data-score attribute (Ratings, Reliability)
                let scoreElem = cell.querySelector('[data-score]');
                if (scoreElem) {
                    val = scoreElem.getAttribute('data-score');
                } else {
                    // 2. Special handling for Price (use data-price attribute)
                    if (idx === priceIdx) {
                        let priceLabel = cell.querySelector('label[data-price]');
                        val = priceLabel ? priceLabel.getAttribute('data-price') : cell.innerText.split('Shop')[0].trim();
                    } 
                    // 3. Special handling for Product Name
                    else if (idx === productIdx) {
                        let nameLink = cell.querySelector('.product__info-display, .product__name, h4, a');
                        val = nameLink ? nameLink.innerText.trim() : cell.innerText.trim();
                    }
                    // 4. Fallback to generic text
                    else {
                        val = cell.innerText.trim();
                    }
                }
                
                // Handle hidden/locked content
                if (val === "" && cell.querySelector('a[href*="join"], .ratings-unlock')) {
                    val = "Locked";
                }
                
                rowObj[h] = val.replace(/\\s+/g, ' ').trim();
            }
        });
        
        // Final sanity check: Must have at least a product name and overall score/reliability
        if (Object.keys(rowObj).length > 0 && rowObj[headers[productIdx]]) {
            all_data.push(rowObj);
        }
    });

    let final_headers = headers.filter(h => h && h !== 'Add to Compare' && !h.toLowerCase().includes('green choice'));
    return [final_headers, all_data];
    """
    
    try:
        headers, data = driver.execute_script(js_extract)
        logger.info(f"Extraction result: {len(data)} products, {len(headers)} columns.")
        
        # Deduplication based on Product name
        seen = set()
        unique_data = []
        pk = next((h for h in headers if "Product" in h.lower()), None)
        
        for item in data:
            if pk:
                id_val = item.get(pk)
                if id_val and id_val not in seen:
                    unique_data.append(item)
                    seen.add(id_val)
            else:
                unique_data.append(item)
                
        return headers, unique_data
    except Exception as e:
        logger.error(f"Scraper execution failed: {e}")
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
    start_url = "https://www.consumerreports.org/appliances/washing-machines/front-load-washer/c28739/"
    
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
        
        logger.info("Proceeding with automated crawling for Washers...")

        # Find all category links dynamically
        logger.info("Discovering washer categories from the top navigation...")
        try:
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".type-nav .nav-btn__wrapper a")))
            nav_links = driver.find_elements(By.CSS_SELECTOR, ".type-nav .nav-btn__wrapper a")
            
            categories = []
            for link in nav_links:
                url = link.get_attribute('href')
                name_elem = link.find_elements(By.CSS_SELECTOR, ".btn-label")
                name = name_elem[0].text.strip() if name_elem else "Unknown"
                
                # Force skip Washer/Dryer Pairs
                if "Washer/Dryer Pairs" in name or (url and "washer-dryer-pairs" in url):
                    logger.info(f"Skipping specialized category from discovery: {name}")
                    continue
                    
                if url:
                    categories.append({"name": name, "url": url})
                    
            logger.info(f"Found {len(categories)} categories: {[c['name'] for c in categories]}")
        except Exception as e:
            logger.error(f"Failed to find category links: {e}")
            logger.info("Falling back to hardcoded standard Washer categories.")
            categories = [
                {"name": "Front-Load Washers", "url": start_url}
            ]

        # Iterate through categories
        for category in categories:
            cat_name = category["name"]
            cat_url = category["url"]
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
