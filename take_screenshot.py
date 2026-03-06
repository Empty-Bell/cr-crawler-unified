import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

def take_screenshot():
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Save screenshot
        save_path = r"C:\Users\JB\.gemini\antigravity\brain\2cb70d67-cbe8-4843-bafa-a7b42d69c408\cr_debug_page.png"
        driver.save_screenshot(save_path)
        print(f"Screenshot saved to {save_path}")
        
        # Output current URL
        print(f"Current URL: {driver.current_url}")
        
        # Find all buttons to debug their text and state
        print("--- Finding potential expansion buttons ---")
        buttons = driver.find_elements("xpath", "//button | //a | //div[contains(@class, 'button')] | //span[contains(@class, 'button')]")
        found = 0
        for b in buttons:
            try:
                text = b.text.strip()
                t_lower = text.lower()
                if "more" in t_lower or "view" in t_lower or "all" in t_lower or "expand" in t_lower:
                    found += 1
                    print(f"Button: text='{text}', displayed={b.is_displayed()}, enabled={b.is_enabled()}, class='{b.get_attribute('class')}', tag='{b.tag_name}'")
            except Exception:
                pass
        
        if found == 0:
            print("No buttons matching 'more/view/all/expand' were found in the DOM.")
            
    except Exception as e:
        print(f"Error connecting to Chrome: {e}")

if __name__ == "__main__":
    take_screenshot()
