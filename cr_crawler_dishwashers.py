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
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def setup_driver():
    chrome_options = Options()
    import tempfile
    temp_dir = tempfile.mkdtemp()
    logger.info(f"Using fresh temporary profile at: {temp_dir}")
    chrome_options.add_argument(f"user-data-dir={temp_dir}")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("--start-maximized")
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver
    except Exception as e:
        logger.error(f"Failed to launch Chrome: {str(e)}")
        raise e

def expand_all_products(driver):
    logger.info("Starting to expand all product lists using JavaScript...")
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
    time.sleep(1)
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(1)

    initial_products = len(driver.find_elements(By.CSS_SELECTOR, ".row-product"))
    logger.info(f"Products BEFORE expansion: {initial_products}")

    js_script = """
    let clickedCount = 0;
    let user_selectors = [
        '.chart-ratings-wrapper .row-footer button',
        '.chart-wrapper.is-collapsed .row-footer button',
        '.row-footer button'
    ];
    let buttons = [];
    user_selectors.forEach(sel => {
        document.querySelectorAll(sel).forEach(b => buttons.push(b));
    });
    document.querySelectorAll('button.btn-expand-toggle, button').forEach(b => {
        let text = b.innerText ? b.innerText.toLowerCase() : '';
        if (b.classList.contains('btn-expand-toggle') || text.includes('see all') || text.includes('view all') || text.includes('show more')) {
            buttons.push(b);
        }
    });
    let uniqueButtons = [...new Set(buttons)];
    uniqueButtons.forEach(b => {
        let target = b.querySelector('div') || b;
        try { target.click(); clickedCount++; } catch(e) { b.click(); clickedCount++; }
    });
    return clickedCount;
    """
    try:
        for i in range(5):
            clicked = driver.execute_script(js_script)
            logger.info(f"JS Click pass {i+1}: Clicked {clicked} buttons.")
            if clicked == 0:
                break
            time.sleep(4)
    except Exception as e:
        logger.error(f"Error during JS expansion: {e}")

    final_products = len(driver.find_elements(By.CSS_SELECTOR, ".row-product"))
    logger.info(f"Products AFTER expansion: {final_products}")
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
    logger.info("Starting fast data extraction via JavaScript...")
    js_extract = """
    let all_data = [];
    let seen_products = new Set();
    let global_headers_info = [];
    let seen_names = new Set();

    let wrappers = Array.from(document.querySelectorAll('.chart-ratings-wrapper'))
                        .filter(w => w.offsetWidth > 0 && w.offsetHeight > 0);
    if (wrappers.length === 0) {
        wrappers = Array.from(document.querySelectorAll('.chart-ratings-wrapper'));
    }
    if (wrappers.length === 0) return [[], []];

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

    wrappers.forEach(wrapper => {
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
    if not data:
        logger.warning(f"No data found to save to {filename}.")
        return
    with open(filename, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(data)
    logger.info(f"Data saved to {filename} (Total: {len(data)})")

def main():
    categories = [
        {"name": "Dishwashers", "url": "https://www.consumerreports.org/appliances/dishwashers/c28687/"},
    ]

    driver = None
    try:
        first_url = categories[0]["url"]
        driver = setup_driver()

        logger.info(f"Checking URL: {first_url}")
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

        logger.info("\n========================================================")
        logger.info("  [!] 사용자 로그인 대기 중...")
        logger.info("  새로 열린 크롬 창에서 로그인을 직접 완료해 주세요.")
        logger.info("  로그인이 완료되고 타겟 페이지가 보이면 터미널에서")
        logger.info("  [Enter] 키를 눌러 크롤링을 시작하세요.")
        logger.info("========================================================\n")
        input("로그인 완료 후 터미널 창에서 Enter키를 누르세요...")

        logger.info("Proceeding with automated crawling for all categories...")

        for category in categories:
            cat_name = category["name"]
            cat_url = category["url"]
            logger.info(f"\n--- Processing Category: {cat_name} ---")

            if driver.current_url != cat_url:
                logger.info(f"Navigating to {cat_url}")
                driver.get(cat_url)
                time.sleep(3)

            logger.info(f"Waiting for chart to load for {cat_name}...")
            try:
                WebDriverWait(driver, 40).until(EC.presence_of_element_located((By.CLASS_NAME, "chart-wrapper")))
            except TimeoutException:
                logger.warning(f"Timeout waiting for chart on {cat_name}. Skipping to next...")
                continue

            expand_all_products(driver)
            headers, data = extract_ratings(driver)

            if data:
                for row in data:
                    row["Category"] = cat_name
                if "Category" not in headers:
                    headers.insert(0, "Category")
                safe_name = cat_name.replace(' ', '_').replace('-', '_').lower()
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
