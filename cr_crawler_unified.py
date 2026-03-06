import os
import time
import csv
import logging
import random
import tempfile
import tempfile
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================================
# 모든 URL은 기존 개별 크롤러 py 파일에서 정상 동작 확인된 것만 사용
# ============================================================
SUPERCATEGORIES = {
    # --- cr_crawler_tvs.py ---
    "TVs": [
        {"name": "TVs", "url": "https://www.consumerreports.org/electronics-computers/tvs/c28700/"}
    ],
    # --- cr_crawler_refrigerators.py (lines 276-281) ---
    "Refrigerators": [
        {"name": "Top-Freezer Refrigerators", "url": "https://www.consumerreports.org/appliances/refrigerators/top-freezer-refrigerator/c28722/"},
        {"name": "Bottom-Freezer Refrigerators", "url": "https://www.consumerreports.org/appliances/refrigerators/bottom-freezer-refrigerator/c28719/"},
        {"name": "French-Door Refrigerators", "url": "https://www.consumerreports.org/appliances/refrigerators/french-door-refrigerator/c37162/"},
        {"name": "Side-by-Side Refrigerators", "url": "https://www.consumerreports.org/appliances/refrigerators/side-side-refrigerator/c28721/"},
        {"name": "Built-In Refrigerators", "url": "https://www.consumerreports.org/appliances/refrigerators/built-in-refrigerator/c28720/"},
        {"name": "Mini Fridges", "url": "https://www.consumerreports.org/appliances/refrigerators/mini-fridges/c200833/"}
    ],
    # --- cr_crawler_washer.py (lines 379-383) ---
    "Washing Machines": [
        {"name": "Front-Load Washers", "url": "https://www.consumerreports.org/appliances/washing-machines/front-load-washer/c28739/"},
        {"name": "Top-Load Agitator Washers", "url": "https://www.consumerreports.org/appliances/washing-machines/top-load-agitator-washer/c32002/"},
        {"name": "Top-Load HE Washers", "url": "https://www.consumerreports.org/appliances/washing-machines/top-load-he-washer/c37107/"},
        {"name": "Compact Washers", "url": "https://www.consumerreports.org/appliances/washing-machines/compact-washers/c37106/"}
    ],
    # --- cr_crawler_dryers.py (lines 258-261) ---
    "Clothes Dryers": [
        {"name": "Electric Dryers", "url": "https://www.consumerreports.org/appliances/clothes-dryers/electric-dryer/c30562/"},
        {"name": "Gas Dryers", "url": "https://www.consumerreports.org/appliances/clothes-dryers/gas-dryer/c30563/"},
        {"name": "Compact Dryers", "url": "https://www.consumerreports.org/appliances/clothes-dryers/compact-dryers/c37294/"}
    ],
    # --- cr_crawler_vacuums.py (lines 215-217) ---
    "Vacuums": [
        {"name": "Robotic Vacuums", "url": "https://www.consumerreports.org/appliances/vacuum-cleaners/robotic-vacuum/c35183/"},
        {"name": "Robotic Vacuum and Mop Combos", "url": "https://www.consumerreports.org/appliances/vacuum-cleaners/robotic-vacuum-and-mop-combos/c201152/"},
        {"name": "Cordless Stick Vacuums", "url": "https://www.consumerreports.org/appliances/vacuum-cleaners/cordless-stick-vacuums/c200448/"}
    ],
    # --- cr_crawler_cooktops.py (lines 214-217) ---
    "Cooktops": [
        {"name": "Electric Smoothtop Cooktops", "url": "https://www.consumerreports.org/appliances/cooktops/electric-smoothtop-cooktops/c28688/"},
        {"name": "Electric Induction Cooktops", "url": "https://www.consumerreports.org/appliances/cooktops/electric-induction-cooktops/c200764/"},
        {"name": "Gas Cooktops", "url": "https://www.consumerreports.org/appliances/cooktops/gas-cooktop/c28692/"}
    ],
    # --- cr_crawler_dishwashers.py (line 215) ---
    "Dishwashers": [
        {"name": "Dishwashers", "url": "https://www.consumerreports.org/appliances/dishwashers/c28687/"}
    ],
    # --- cr_crawler_microwaves.py (lines 214-216) ---
    "Microwave Ovens": [
        {"name": "Countertop Microwave Ovens", "url": "https://www.consumerreports.org/appliances/microwave-ovens/countertop-microwave-oven/c28706/"},
        {"name": "Over-the-Range Microwave Ovens", "url": "https://www.consumerreports.org/appliances/microwave-ovens/over-the-range-microwave-oven/c32000/"}
    ],
    # --- cr_crawler_wall_ovens.py (lines 215-216) ---
    "Wall Ovens": [
        {"name": "Electric Wall Ovens", "url": "https://www.consumerreports.org/appliances/wall-ovens/electric-wall-ovens/c28738/"},
        {"name": "Combo Wall Ovens", "url": "https://www.consumerreports.org/appliances/wall-ovens/combo-wall-ovens/c200768/"}
    ],
    # --- cr_crawler_ranges.py (lines 214-219) ---
    "Ranges": [
        {"name": "Electric Ranges", "url": "https://www.consumerreports.org/appliances/ranges/electric-range/c28689/"},
        {"name": "Electric Induction Ranges", "url": "https://www.consumerreports.org/appliances/ranges/electric-induction-ranges/c37181/"},
        {"name": "Electric Coil Ranges", "url": "https://www.consumerreports.org/appliances/ranges/electric-coil-ranges/c37179/"},
        {"name": "Gas Ranges", "url": "https://www.consumerreports.org/appliances/ranges/gas-range/c28694/"},
        {"name": "Pro-Style Ranges", "url": "https://www.consumerreports.org/appliances/ranges/pro-style-ranges/c36820/"}
    ],
    # --- cr_crawler_sound_bars.py (line 215) ---
    "Sound Bars": [
        {"name": "Sound Bars", "url": "https://www.consumerreports.org/electronics-computers/sound-bars/c28698/"}
    ],
    # --- cr_crawler_mobile_pc.py ---
    "Smartphones": [
        {"name": "Cell Phones", "url": "https://www.consumerreports.org/electronics-computers/cell-phones/c28726/"}
    ],
    "Smartwatches": [
        {"name": "Smartwatches and Fitness Trackers", "url": "https://www.consumerreports.org/electronics-computers/smartwatches-fitness-trackers/c201155/"}
    ],
    "Laptops": [
        {"name": "Laptops", "url": "https://www.consumerreports.org/electronics-computers/laptops-chromebooks/laptops/c28701/"}
    ]
}

FILE_PATH_ALL_DATA = "CR_All_Data_Latest.xlsx"
FILE_PATH_REPORT = "CR_Delta_Report.xlsx"

def get_timestamped_filename(base_name):
    """파일명 뒤에 _YYYYMMDDHHMM 형식을 붙입니다."""
    ts = datetime.now().strftime("%y%m%d%H%M")
    name, ext = os.path.splitext(base_name)
    return f"{name}_{ts}{ext}"

# ============================================================
# 드라이버 설정 (공유 프로필 사용하여 로그인 유지)
# ============================================================
def setup_driver(profile_path):
    chrome_options = Options()
    
    # 클라우드(GitHub Actions 등) 환경 대응: 헤드리스 모드 활성화
    if os.getenv("GITHUB_ACTIONS") == "true":
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        logger.info("클라우드 환경 감지: 헤드리스 모드로 실행합니다.")
    else:
        chrome_options.add_argument(f"user-data-dir={profile_path}")

    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("--start-maximized")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.execute_cdp_cmd('Network.setUserAgentOverride', {
        "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

# ============================================================
# 제품 목록 확장
# ============================================================
def expand_all_products(driver):
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
    time.sleep(1)
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(1)
    initial = len(driver.find_elements(By.CSS_SELECTOR, ".row-product"))
    js = """
    let c=0;
    ['.chart-ratings-wrapper .row-footer button','.chart-wrapper.is-collapsed .row-footer button','.row-footer button'].forEach(s=>{document.querySelectorAll(s).forEach(b=>{try{(b.querySelector('div')||b).click();c++}catch(e){b.click();c++}})});
    document.querySelectorAll('button.btn-expand-toggle, button').forEach(b=>{let t=b.innerText?b.innerText.toLowerCase():'';if(b.classList.contains('btn-expand-toggle')||t.includes('see all')||t.includes('view all')||t.includes('show more')){try{(b.querySelector('div')||b).click();c++}catch(e){b.click();c++}}});
    return c;
    """
    for _ in range(5):
        if driver.execute_script(js) == 0: break
        time.sleep(4)
    final = len(driver.find_elements(By.CSS_SELECTOR, ".row-product"))
    logger.info(f"Products expanded: {initial} → {final}")

def human_type(element, text):
    """실제 사람이 타이핑하는 것처럼 글자별로 약간의 지연을 줍니다."""
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.1, 0.3))

def auto_login(driver):
    """.env 파일의 정보를 바탕으로 자동 로그인을 시도합니다."""
    email = os.getenv("CR_EMAIL")
    password = os.getenv("CR_PASSWORD")
    
    if not email or not password:
        logger.warning("CR_EMAIL 또는 CR_PASSWORD 환경 변수가 설정되지 않았습니다.")
        return False

    login_url = "https://secure.consumerreports.org/ec/account/login"
    logger.info("자동 로그인 시도 중...")
    driver.get(login_url)
    
    try:
        wait = WebDriverWait(driver, 20)
        # 로그인 필드 대기
        username_field = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#username")))
        password_field = driver.find_element(By.CSS_SELECTOR, "#password")
        login_button = driver.find_element(By.CSS_SELECTOR, "button.qa-sign-in-button")
        
        # 사람처럼 타이핑
        human_type(username_field, email)
        time.sleep(random.uniform(0.5, 1.2))
        human_type(password_field, password)
        time.sleep(random.uniform(0.5, 1.2))
        
        # 로그인 버튼 클릭
        login_button.click()
        
        # 로그인 완료 대기 및 성공 여부 확인
        # 1. 충분한 대기 시간 부여
        time.sleep(8)
        
        # 2. 다양한 지표로 성공 여부 판단
        login_success = False
        
        # 지표 A: 'Sign In' 버튼(Label)이 사라졌는지 확인
        try:
            sign_in_elements = driver.find_elements(By.CSS_SELECTOR, "label#sign-in-label, .qa-sign-in-button")
            # 요소가 없거나, 있더라도 보이지 않으면 성공 가능성 높음
            if not sign_in_elements or not any(el.is_displayed() for el in sign_in_elements):
                logger.info("성공 지표 A 감지: 'Sign In' 버튼이 사라짐.")
                login_success = True
        except:
            pass

        # 지표 B: 사용자 프로필 아이콘 또는 멤버 전용 요소가 나타났는지 확인
        if not login_success:
            try:
                # 멤버 전용 클래스나 사용자 메뉴 아이콘 확인
                member_elements = driver.find_elements(By.CSS_SELECTOR, ".cda-gnav__member--shown, .cda-gnav__account-menu, [data-gn-signin='true']")
                if any(el.is_displayed() for el in member_elements):
                    logger.info("성공 지표 B 감지: 멤버 전용 UI 요소 확인됨.")
                    login_success = True
            except:
                pass

        # 지표 C: URL 확인 (보조 수단)
        if not login_success:
            curr_url = driver.current_url.lower()
            if "login" not in curr_url and "digital-login" not in curr_url:
                logger.info("성공 지표 C 감지: 로그인 관련 URL이 아님.")
                login_success = True

        if login_success:
            logger.info("자동 로그인 성공 확인 완료!")
            return True
        else:
            logger.warning(f"로그인 성공 여부를 확신할 수 없습니다. (현재 URL: {driver.current_url})")
            return False
            
    except Exception as e:
        logger.error(f"자동 로그인 도중 에러 발생: {e}")
        return False

# ============================================================
# 데이터 추출 (정상 동작 확인된 JS 그대로 사용)
# ============================================================
def extract_ratings(driver):
    js_extract = """
    let all_data = [];
    let seen_products = new Set();
    let global_headers_info = [];
    let seen_names = new Set();

    let wrappers = Array.from(document.querySelectorAll('.chart-ratings-wrapper'))
                        .filter(w => w.offsetWidth > 0 && w.offsetHeight > 0);
    if (wrappers.length === 0) wrappers = Array.from(document.querySelectorAll('.chart-ratings-wrapper'));
    if (wrappers.length === 0) return [[], []];

    wrappers.forEach(wrapper => {
        let header_row = wrapper.querySelector('.row-header') || document.querySelector('.row-header');
        if (!header_row) return;
        let header_cells = header_row.querySelectorAll('.cell');
        header_cells.forEach((cell, i) => {
            let h = cell.getAttribute('aria-label') || cell.innerText.trim();
            if (!h) { let t = cell.querySelector('.icon__tooltip'); if (t) h = t.getAttribute('aria-label') || t.getAttribute('data-title'); }
            if (!h || h === 'Add to Compare' || h.toLowerCase().includes('green choice')) return;
            h = h.replace(/\\n/g, ' ').trim();
            if (!seen_names.has(h)) { global_headers_info.push({name: h}); seen_names.add(h); }
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
                    if (!h) { let t = cell.querySelector('.icon__tooltip'); if (t) h = t.getAttribute('aria-label') || t.getAttribute('data-title'); }
                    if (!h) return;
                    h = h.replace(/\\n/g, ' ').trim();
                    local_headers_info.push({index: i, name: h});
                });
            }

            let product_rows = wrapper.querySelectorAll('.row-product');
            
            // 현재 섹션의 SubCategory 추출
            let subCatElem = wrapper.parentElement.querySelector('[id="chart-ratings__details"]') 
                          || wrapper.querySelector('[id="chart-ratings__details"]')
                          || document.getElementById('chart-ratings__details');
            let foundSubCat = subCatElem ? subCatElem.innerText.trim() : "";
            
            // SubCategory별로 랭킹 1위부터 시작
            let rank = 1;

            product_rows.forEach(row => {
                let pid = row.getAttribute('data-id') || row.innerText.substring(0, 30);
                if (seen_products.has(pid)) return;
                seen_products.add(pid);

                let rd = {
                    'Rank': rank++,
                    'SubCategory': foundSubCat
                };

            let cells = row.querySelectorAll('.cell');
            local_headers_info.forEach(lhi => {
                if (lhi.name === 'Add to Compare' || lhi.name.toLowerCase().includes('green choice')) return;
                if (lhi.index >= cells.length) return;
                let cell = cells[lhi.index];
                let val = "";
                let ds = cell.querySelector('[data-score]');
                if (ds) { val = ds.getAttribute('data-score'); }
                else {
                    let h4 = cell.querySelector('h4');
                    if (h4) { val = h4.innerText.trim(); }
                    else {
                        let lb = cell.querySelector('label');
                        if (lb && lb.getAttribute('data-score')) { val = lb.getAttribute('data-score'); }
                        else { val = cell.innerText.trim().replace(/\\s+/g, ' '); }
                    }
                }
                if (lhi.name === 'Price' && val.includes('Shop')) val = val.split('Shop')[0].trim();
                rd[lhi.name] = val;
            });
            if (Object.keys(rd).length > 1) all_data.push(rd);
        });
    });

    if (!final_headers.includes('SubCategory')) final_headers.unshift('SubCategory');
    if (!final_headers.includes('Rank')) final_headers.unshift('Rank');
    return [final_headers, all_data];
    """
    try:
        return driver.execute_script(js_extract)
    except Exception as e:
        logger.error(f"Extraction error: {e}")
        return [], []

# ============================================================
# Delta 비교 분석
# ============================================================
def generate_delta_report(old_df, new_df, supercat_name):
    changes = []
    pcol = 'Product' if 'Product' in new_df.columns else (new_df.columns[2] if len(new_df.columns) > 2 else None)
    if pcol is None: return changes

    old_m = old_df.drop_duplicates(subset=[pcol]).set_index(pcol) if not old_df.empty and pcol in old_df.columns else pd.DataFrame()
    new_m = new_df.drop_duplicates(subset=[pcol]).set_index(pcol) if not new_df.empty and pcol in new_df.columns else pd.DataFrame()

    skip = {'Extracted_At', 'Category', 'SuperCategory', 'Price', pcol}
    comp_cols = [c for c in new_df.columns if c not in skip]

    for model in new_m.index:
        cat = new_m.loc[model, 'Category']
        nt = new_m.loc[model, 'Extracted_At']
        if old_m.empty or model not in old_m.index:
            changes.append({"SuperCategory": supercat_name, "Category": cat, "Product": model,
                            "Attribute": "New Model", "Previous": "N/A", "New": "Added",
                            "Old Extracted_At": "N/A", "New Extracted_At": nt})
        else:
            ot = old_m.loc[model, 'Extracted_At']
            for col in comp_cols:
                if col in new_m.columns and col in old_m.columns:
                    val_new = new_m.loc[model, col]
                    val_old = old_m.loc[model, col]

                    vn = str(val_new).strip()
                    vo = str(val_old).strip()
                    
                    # 빈 값(결측치)들을 동일하게 취급 (예: 'nan', 'NA', 'None', '')
                    empty_vals = {"", "nan", "na", "none", "n/a", "-"}
                    if vn.lower() in empty_vals and vo.lower() in empty_vals:
                        continue
                    
                    # 소수점 표시 형식 차이로 인한 오탐지 방지 (예: 84.0과 84를 같게 취급)
                    if pd.notna(val_new) and pd.notna(val_old):
                        try:
                            if float(val_new) == float(val_old):
                                continue
                        except (ValueError, TypeError):
                            pass
                    
                    if vn != vo:
                        changes.append({"SuperCategory": supercat_name, "Category": cat, "Product": model,
                                        "Attribute": col, "Previous": vo, "New": vn,
                                        "Old Extracted_At": ot, "New Extracted_At": nt})
    return changes

# ============================================================
# 체크포인트 저장
# ============================================================
def save_checkpoint(data_dict, file_path, prev_data):
    try:
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            for sc, records in data_dict.items():
                if not records:
                    if prev_data and sc in prev_data:
                        prev_data[sc].to_excel(writer, sheet_name=sc, index=False)
                    continue
                df = pd.DataFrame(records)
                cols = list(df.columns)
                order = ['SuperCategory', 'Category', 'SubCategory', 'Rank', 'Brand', 'Product', 'Overall Score', 'Price', 'Extracted_At']
                final = [c for c in order if c in cols] + [c for c in cols if c not in order]
                df[final].to_excel(writer, sheet_name=sc, index=False)
    except Exception as e:
        logger.error(f"Checkpoint save error: {e}")

def send_email_report(all_data, changes, extract_time, data_file, report_file):
    """크롤링 결과를 이메일로 송부합니다."""
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_PASSWORD") # 앱 비밀번호 권장
    receiver_email = "jongbin.yun@samsung.com"

    if not sender_email or not sender_password:
        logger.warning("이메일 발신 정보(SENDER_EMAIL/PASSWORD)가 설정되지 않아 메일을 보낼 수 없습니다.")
        return

    # 요약 정보 계산
    total_categories = sum(len(v) for v in SUPERCATEGORIES.values())
    collected_count = sum(len(records) for records in all_data.values())
    success_count = sum(1 for sc in all_data.values() for _ in sc if _ ) # 실제 데이터가 있는 카테고리 수 등 필요시 수정
    
    # 델타 요약
    new_models = len([c for c in changes if c.get("Attribute") == "New Model"])
    updates = len(changes) - new_models
    
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = f"[CR Crawl] 결과 요약 ({extract_time})"

    body = f"""
    <h3>Consumer Report 크롤링 결과 요약</h3>
    <ul>
        <li><b>수행 일시:</b> {extract_time}</li>
        <li><b>수집 데이터양:</b> 총 {collected_count}개 모델</li>
        <li><b>성공률:</b> {collected_count}개 모델 수집됨 (대상 카테고리: {total_categories}개)</li>
    </ul>
    
    <h4>[델타 결과 요약]</h4>
    <ul>
        <li><b>신규 모델 추가:</b> {new_models}건</li>
        <li><b>기존 모델 변경:</b> {updates}건</li>
        <li><b>총 변경 사항:</b> {len(changes)}건</li>
    </ul>
    
    <p>상세 내용은 첨부된 파일을 확인해 주세요.</p>
    """
    msg.attach(MIMEText(body, 'html'))

    # 파일 첨부
    for f_path in [data_file, report_file]:
        if os.path.exists(f_path):
            with open(f_path, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename= {os.path.basename(f_path)}")
            msg.attach(part)

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        logger.info(f"이메일 리포트 발송 완료: {receiver_email}")
    except Exception as e:
        logger.error(f"이메일 발송 에러: {e}")

# ============================================================
# MAIN
# ============================================================
def main():
    profile_dir = tempfile.mkdtemp()
    logger.info(f"Persistent Session Profile: {profile_dir}")

    all_data = {sc: [] for sc in SUPERCATEGORIES}
    prev_data = {}
    if os.path.exists(FILE_PATH_ALL_DATA):
        logger.info(f"이전 데이터 발견: {FILE_PATH_ALL_DATA}")
        try:
            xl = pd.ExcelFile(FILE_PATH_ALL_DATA)
            for s in xl.sheet_names:
                prev_data[s] = xl.parse(s)
        except Exception as e:
            logger.error(f"이전 데이터 파싱 에러: {e}")

    extract_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Step 1: 로그인 세션 생성
    first_url = list(SUPERCATEGORIES.values())[0][0]["url"]
    driver = setup_driver(profile_dir)
    
    # 자동 로그인 시도
    login_success = auto_login(driver)
    
    if not login_success:
        logger.info("\n========================================================")
        logger.info("  [!] 자동 로그인 실패 또는 정보 없음. 수동 로그인이 필요합니다.")
        logger.info("  현재 브라우저에서 로그인 완료 후 터미널에서 [Enter]를 눌러주세요.")
        logger.info("========================================================\n")
        driver.get(first_url)
        input("로그인 완료 후 Enter키를 누르세요...")
    
    driver.quit()
    time.sleep(3)

    # Step 2: 슈퍼카테고리별 브라우저 세션 분리
    for sc_name, subcats in SUPERCATEGORIES.items():
        logger.info(f"\n{'='*50}")
        logger.info(f" [{sc_name}] 새 브라우저 세션 시작")
        logger.info(f"{'='*50}")

        driver = setup_driver(profile_dir)
        try:
            for cat in subcats:
                cn = cat["name"]
                cu = cat["url"]
                logger.info(f"\n--- {cn} ---")
                driver.get(cu)
                time.sleep(4)

                # URL 검증 (리다이렉트 방지)
                actual = driver.current_url.split('?')[0].rstrip('/')
                expected = cu.split('?')[0].rstrip('/')
                if actual != expected:
                    logger.warning(f"URL Mismatch! Expected: {expected}")
                    logger.warning(f"              Actual:   {actual}")
                    logger.warning("리다이렉트 감지됨. 이 카테고리를 건너뜁니다.")
                    continue

                try:
                    WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CLASS_NAME, "chart-wrapper")))
                except TimeoutException:
                    logger.warning(f"Timeout: {cn}. 건너뜁니다.")
                    continue

                expand_all_products(driver)
                headers, data = extract_ratings(driver)

                if data:
                    KNOWN_BRANDS = [
                        'Fisher & Paykel', 'Arctic King', 'Dirt Devil', 'Speed Queen',
                        'Magic Chef', 'Unique Appliances', 'Summit Appliances', 'Commercial Chef',
                        'GE Profile', 'GE Monogram', 'GE Café', 'GE Cafe',
                        'Kenmore Elite', 'Kenmore Pro', 'Harman Kardon', 'Open Box',
                        'Black+Decker', 'Sub-Zero'
                    ]

                    for row in data:
                        row["SuperCategory"] = sc_name
                        row["Category"] = cn
                        row["Extracted_At"] = extract_time
                        
                        if "Product" in row:
                            prod_name = str(row["Product"]).strip()
                            brand = None
                            model = None
                            
                            # 특별 케이스 처리 (LG Signature, LG Studio)
                            if prod_name.upper().startswith("LG SIGNATURE"):
                                brand = "LG"
                                model = prod_name[len("LG SIGNATURE"):].strip()
                            elif prod_name.upper().startswith("LG STUDIO"):
                                brand = "LG"
                                model = prod_name[len("LG STUDIO"):].strip()
                            else:
                                # 알려진 복합 명칭 브랜드 검색
                                for kb in KNOWN_BRANDS:
                                    if prod_name.upper().startswith(kb.upper()):
                                        brand = kb
                                        model = prod_name[len(kb):].strip()
                                        break
                                
                                # 매칭되는 게 없으면 첫 번째 단어를 띄어쓰기 기준으로 자르기
                                if not brand:
                                    brand = prod_name.split(' ')[0]
                                    model = prod_name[len(brand):].strip()
                            
                            row["Brand"] = brand
                            row["Product"] = model

                    all_data[sc_name].extend(data)
                    logger.info(f"✅ {cn}: {len(data)}개 수집 완료")
                else:
                    logger.warning(f"❌ {cn}: 데이터 없음")

                delay = random.uniform(8, 15)
                logger.info(f"대기 {delay:.1f}초...")
                time.sleep(delay)

            # 슈퍼카테고리 완료 → 체크포인트
            save_checkpoint(all_data, FILE_PATH_ALL_DATA, prev_data)
            logger.info(f"[{sc_name}] 체크포인트 저장 완료")

        except Exception as e:
            logger.error(f"[{sc_name}] 에러: {e}")
        finally:
            driver.quit()
            pause = random.uniform(8, 15)
            logger.info(f"브라우저 종료. {pause:.1f}초 대기 후 다음 세션...")
            time.sleep(pause)

    # Step 3: Delta Report
    logger.info("\nDelta 리포트 생성 중...")
    changes = []
    for sc, records in all_data.items():
        if not records: continue
        df_new = pd.DataFrame(records)
        df_old = prev_data.get(sc, pd.DataFrame())
        changes.extend(generate_delta_report(df_old, df_new, sc))

    # 파일명 생성 (타임스탬프 포함)
    ts_data_file = get_timestamped_filename(FILE_PATH_ALL_DATA)
    ts_report_file = get_timestamped_filename(FILE_PATH_REPORT)

    # 로컬 아카이빙 저장
    save_checkpoint(all_data, ts_data_file, prev_data)
    
    if changes:
        pd.DataFrame(changes).to_excel(ts_report_file, index=False)
        logger.info(f"변경사항 {len(changes)}건 → {ts_report_file}")
    else:
        pd.DataFrame([{"Message": "변경사항 없음", "Checked_At": extract_time}]).to_excel(ts_report_file, index=False)
        logger.info(f"변경사항 없음 → {ts_report_file}")

    # 이메일 발송
    send_email_report(all_data, changes, extract_time, ts_data_file, ts_report_file)

    logger.info("통합 크롤링 및 아카이빙 완료!")

if __name__ == "__main__":
    main()
