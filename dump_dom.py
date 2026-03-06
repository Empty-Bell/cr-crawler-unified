import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

def dump_dom():
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        html = driver.page_source
        save_path = r"C:\Users\JB\OneDrive\문서\Consumer Report\CR Score Crawling\current_dom_dump.html"
        
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(html)
            
        print(f"SUCCESS: DOM saved to {save_path}")
        
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    dump_dom()
