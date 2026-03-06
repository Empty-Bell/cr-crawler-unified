import os
import csv
import logging
from html.parser import HTMLParser

# Basic setup for logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CRMockParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.headers = []
        self.products = []
        self.current_product = {}
        self.in_header = False
        self.in_product = False
        self.in_cell = False
        self.current_cell_data = ""
        self.current_attr_score = None
        self.cell_index = 0
        self.depth = 0
        self.header_depth = -1
        self.product_depth = -1
        self.cell_depth = -1

    def handle_starttag(self, tag, attrs):
        self.depth += 1
        attrs_dict = dict(attrs)
        class_name = attrs_dict.get('class', '')

        # Detect Headers
        if 'row-header' in class_name:
            self.in_header = True
            self.header_depth = self.depth
        
        # Detect Products
        if 'row-product' in class_name:
            self.in_product = True
            self.product_depth = self.depth
            self.current_product = {}
            self.cell_index = 0

        # Detect Cells
        if 'cell' in class_name:
            self.in_cell = True
            self.cell_depth = self.depth
            self.current_cell_data = ""
            # Check for data attributes
            self.current_attr_score = attrs_dict.get('data-score') or attrs_dict.get('aria-label')

        # Specific data points
        if tag == 'h4':
            pass # Name is usually here

    def handle_endtag(self, tag):
        if self.in_cell and self.depth == self.cell_depth:
            if self.in_header:
                self.headers.append(self.current_cell_data.strip() or f"Col_{len(self.headers)}")
            elif self.in_product:
                header = self.headers[self.cell_index] if self.cell_index < len(self.headers) else f"Col_{self.cell_index}"
                val = self.current_attr_score or self.current_cell_data.strip()
                self.current_product[header] = val
                self.cell_index += 1
            
            self.in_cell = False
            self.cell_depth = -1
            self.current_attr_score = None

        if self.in_header and self.depth == self.header_depth:
            self.in_header = False
            self.header_depth = -1

        if self.in_product and self.depth == self.product_depth:
            self.products.append(self.current_product)
            self.in_product = False
            self.product_depth = -1

        self.depth -= 1

    def handle_data(self, data):
        if self.in_cell:
            self.current_cell_data += data

def extract_from_snippet(file_path):
    logger.info(f"Extracting data from {os.path.basename(file_path)}...")
    with open(file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    parser = CRMockParser()
    parser.feed(html_content)
    return parser.headers, parser.products

def test():
    files = [
        r"c:\Users\JB\OneDrive\문서\Consumer Report\CR Score Crawling\div class=chart-wrapper is-collapse1.txt",
        r"c:\Users\JB\OneDrive\문서\Consumer Report\CR Score Crawling\div class=chart-wrapper is-collapse2.txt"
    ]
    
    all_results = []
    final_headers = []
    
    for f in files:
        if os.path.exists(f):
            headers, data = extract_from_snippet(f)
            if not final_headers: final_headers = headers
            all_results.extend(data)
    
    # Save to a test file
    test_output = r"c:\Users\JB\OneDrive\문서\Consumer Report\CR Score Crawling\test_extraction_result.csv"
    with open(test_output, 'w', encoding='utf-8-sig', newline='') as f:
        if all_results:
            writer = csv.DictWriter(f, fieldnames=final_headers)
            writer.writeheader()
            writer.writerows(all_results)
    
    logger.info(f"Verification complete. Total products extracted: {len(all_results)}")
    logger.info(f"Check results at: {test_output}")

if __name__ == "__main__":
    test()
