import os
import time
import csv
import logging
import subprocess
import argparse
import sys

# offline parser for `--test-html` mode; reuse existing test module if available
try:
    from test_mock_extraction import CRMockParser
except Exception:
    CRMockParser = None

def parse_html_file(path):
    """Simple fallback HTML parser used when Selenium isn't required.

    The logic is essentially the same as the one defined in
    `test_mock_extraction.py`.  Importing CRMockParser avoids duplication
    but a minimal copy exists here if that module isn't importable.
    """

    if CRMockParser:
        parser = CRMockParser()
    else:
        # fallback lightweight implementation; only a subset of features needed
        from html.parser import HTMLParser

        class QuickParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.headers = []
                self.products = []
                self.curr = None
                self.in_header = False
                self.in_product = False
                self.in_cell = False
                self.cell_text = ""
                self.cell_score = None
                self.cell_index = 0
                self.stack = []

            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                cls = attrs.get('class','')
                self.stack.append(tag)
                if 'row-header' in cls:
                    self.in_header = True
                    self.cell_index = 0
                if 'row-product' in cls:
                    self.in_product = True
                    self.curr = {}
                    self.cell_index = 0
                if 'cell' in cls:
                    self.in_cell = True
                    self.cell_text = ''
                    self.cell_score = attrs.get('data-score')

            def handle_endtag(self, tag):
                if self.in_cell and not self.stack[-1] != tag:
                    if self.in_header:
                        self.headers.append(self.cell_text.strip())
                    elif self.in_product:
                        header = self.headers[self.cell_index] if self.cell_index < len(self.headers) else f"Col_{self.cell_index}"
                        val = self.cell_score or self.cell_text.strip()
                        self.curr[header] = val
                        self.cell_index += 1
                    self.in_cell = False
                if self.in_product and 'row-product' in self.stack and tag == 'div':
                    # end of product
                    self.products.append(self.curr)
                    self.in_product = False
                if self.in_header and 'row-header' in self.stack and tag == 'div':
                    self.in_header = False
                self.stack.pop()

            def handle_data(self, data):
                if self.in_cell:
                    self.cell_text += data

        parser = QuickParser()

    with open(path, 'r', encoding='utf-8') as f:
        parser.feed(f.read())
    return parser.headers, parser.products
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

def setup_driver(url=None, headless=False, profile_dir=None):
    """Configures and returns the Selenium Chrome driver using a fresh temporary profile."""
    chrome_options = Options()

    if headless:
        # newer versions of chrome support "--headless=new" which behaves more like a normal session
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
    
    # allow caller to specify a persistent profile (e.g. to reuse an already-logged-in session)
    if profile_dir:
        logger.info(f"Using provided Chrome user profile: {profile_dir}")
        chrome_options.add_argument(f"user-data-dir={profile_dir}")
    else:
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
    """Extracts all data from the expanded chart using pure JavaScript for maximum speed."""
    logger.info("Starting fast data extraction via JavaScript...")
    
    js_extract = """
    let all_data = [];
    let seen_products = new Set();
    let global_headers_info = [];
    let seen_names = new Set();
    
    // 1. Collect all visible wrappers
    let wrappers = Array.from(document.querySelectorAll('.chart-ratings-wrapper'))
                        .filter(w => w.offsetWidth > 0 && w.offsetHeight > 0);
    
    if (wrappers.length === 0) {
        // Fallback to any ratings wrapper if none are strictly "visible" by dimensions
        wrappers = Array.from(document.querySelectorAll('.chart-ratings-wrapper'));
    }
    
    if (wrappers.length === 0) return [[], []];

    // 2. Extract headers from the first valid wrapper to establish common columns
    wrappers.forEach(wrapper => {
        let header_row = wrapper.querySelector('.row-header') || document.querySelector('.row-header');
        if (!header_row) return;
        
        let header_cells = header_row.querySelectorAll('.cell');
        header_cells.forEach((cell, i) => {
            let h = cell.getAttribute('aria-label') || cell.innerText.trim();
            if (!h) {
                let tooltip = cell.querySelector('.icon__tooltip');
                if (tooltip) h = tooltip.getAttribute('aria-label') || tooltip.getAttribute('data-title');
            }
            if (!h || h === 'Add to Compare' || h.toLowerCase().includes('green choice')) return;
            h = h.replace(/\\n/g, ' ').trim();
            
            if (!seen_names.has(h)) {
                global_headers_info.push({name: h});
                seen_names.add(h);
            }
        });
    });

    let final_headers = global_headers_info.map(hi => hi.name);

    // 3. Iterate through ALL wrappers and collect products
    wrappers.forEach(wrapper => {
        // We need to re-map indices for each wrapper because columns might vary slightly or indices change
        let local_headers_info = [];
        let header_row = wrapper.querySelector('.row-header') || document.querySelector('.row-header');
        if (header_row) {
            let cells = header_row.querySelectorAll('.cell');
            cells.forEach((cell, i) => {
                let h = cell.getAttribute('aria-label') || cell.innerText.trim();
                if (!h) {
                    let tooltip = cell.querySelector('.icon__tooltip');
                    if (tooltip) h = tooltip.getAttribute('aria-label') || tooltip.getAttribute('data-title');
                }
                if (!h) return;
                h = h.replace(/\\n/g, ' ').trim();
                local_headers_info.push({index: i, name: h});
            });
        }

        let product_rows = wrapper.querySelectorAll('.row-product');
        product_rows.forEach(row => {
            let productId = row.getAttribute('data-id') || row.innerText.substring(0, 30);
            if (seen_products.has(productId)) return;
            seen_products.add(productId);
            
            let row_data = {};
            let cells = row.querySelectorAll('.cell');
            
            local_headers_info.forEach(lhi => {
                if (lhi.name === 'Add to Compare' || lhi.name.toLowerCase().includes('green choice')) return;
                if (lhi.index >= cells.length) return;
                
                let cell = cells[lhi.index];
                let header = lhi.name;
                let val = "";
                
                let data_score = cell.querySelector('[data-score]');
                if (data_score) {
                    val = data_score.getAttribute('data-score');
                } else {
                    let h4 = cell.querySelector('h4');
                    if (h4) {
                        val = h4.innerText.trim();
                    } else {
                        let label = cell.querySelector('label');
                        if (label && label.getAttribute('data-score')) {
                            val = label.getAttribute('data-score');
                        } else {
                            val = cell.innerText.trim().replace(/\\s+/g, ' ');
                        }
                    }
                }
                
                if (header === 'Price' && val.includes('Shop')) val = val.split('Shop')[0].trim();
                if (val.startsWith('/') && !isNaN(val.substring(1).trim())) val = cell.querySelector('.rating__progress')?.getAttribute('data-score') || val;

                row_data[header] = val;
            });
            
            if (Object.keys(row_data).length > 0) {
                all_data.push(row_data);
            }
        });
    });
    
    return [final_headers, all_data];
    """
    
    try:
        headers, all_data = driver.execute_script(js_extract)
        logger.info(f"Javascript extraction complete. Found {len(all_data)} products.")
        return headers, all_data
    except Exception as e:
        logger.error(f"Failed to extract via JS: {e}")
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

def parse_args():
    parser = argparse.ArgumentParser(
        description="Consumer Reports washer ratings crawler (specialized list)")
    parser.add_argument("--headless", action="store_true", help="run Chrome in headless mode")
    parser.add_argument("--profile", help="path to an existing Chrome user-data-dir to reuse login")
    parser.add_argument("--skip-login", action="store_true", help="do not pause for manual login")
    parser.add_argument("--output-dir", default=".", help="directory to write CSV files into")
    parser.add_argument("--categories", nargs="*",
                        help="optional list of URLs to crawl; if omitted the built-in washer categories are used")
    parser.add_argument("--test-html", help="path to a local HTML file to load for debugging extraction")
    return parser.parse_args()


def main():
    args = parse_args()

    # default list for washers; allow override via --categories
    default_categories = [
        {"name": "Front-Load Washers", "url": "https://www.consumerreports.org/appliances/washing-machines/front-load-washer/c28739/"},
        {"name": "Top-Load Agitator Washers", "url": "https://www.consumerreports.org/appliances/washing-machines/top-load-agitator-washer/c32002/"},
        {"name": "Top-Load HE Washers", "url": "https://www.consumerreports.org/appliances/washing-machines/top-load-he-washer/c37107/"},
        {"name": "Compact Washers", "url": "https://www.consumerreports.org/appliances/washing-machines/compact-washers/c37106/"}
    ]

    categories = []
    if args.categories:
        for u in args.categories:
            # try to derive a human-readable name from the URL path
            name = u.rstrip("/").split("/")[-2].replace('-', ' ').title()
            categories.append({"name": name, "url": u})
    else:
        categories = default_categories

    driver = None
    try:
        if args.test_html:
            # offline test mode: do not start a browser at all
            path = os.path.abspath(args.test_html)
            logger.info(f"Parsing local HTML file {path} without Selenium...")
            headers, data = parse_html_file(path)
            # mimic the post-processing (category header etc) to make behaviour predictable
            if data:
                logger.info(f"Parsed {len(data)} product rows; sample headers={headers}")
            else:
                logger.warning("No data parsed from test HTML.")
            return

        # Load the first URL to prompt for login
        first_url = categories[0]["url"]
        driver = setup_driver(first_url, headless=args.headless, profile_dir=args.profile)
        
        logger.info(f"Checking URL: {first_url}")
        
        # Check if we are still on the startup page and force it
        for i in range(3):
            curr_url = driver.current_url
            logger.info(f"Current URL: {curr_url}")
            if "chrome://" in curr_url or "about:blank" in curr_url or "newtab" in curr_url:
                logger.info(f"Redirection Attempt {i+1}...")
                try:
                    driver.execute_script(f"window.location.replace('{first_url}');")
                except Exception:
                    driver.get(first_url)
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
        
        if not args.skip_login and not os.environ.get('CR_SKIP_LOGIN'):
            input("로그인 완료 후 터미널 창에서 Enter키를 누르세요...")
        else:
            logger.info("Skipping manual login pause (skip-login or CR_SKIP_LOGIN set)")
        
        logger.info("Proceeding with automated crawling for all categories...")

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
                filename = os.path.join(args.output_dir, f"cr_ratings_{safe_name}.csv")
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
