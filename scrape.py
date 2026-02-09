"""
IDOT Bid Letting Scraper - Serverless Function
This is the backend that runs on Vercel's servers and does all the actual web scraping.
When the frontend sends a request with an IDOT repository URL, this function fetches that page,
parses the HTML table, filters for relevant counties and statuses, extracts individual contract URLs,
scrapes each contract for bidder data, and returns a CSV file.
"""

from http.server import BaseHTTPRequestHandler
import json
import urllib.request
import urllib.error
from urllib.parse import urljoin
import csv
from io import StringIO
from html.parser import HTMLParser

# Counties we care about (Chicago metro area)
VALID_COUNTIES = {
    'boone', 'cook', 'grundy', 'dupage', 'kane', 
    'kendall', 'lake', 'mchenry', 'will', 'various'
}

# Contract statuses we want to include
VALID_STATUSES = {'active', 'executed', 'awarded'}


class SimpleHTMLParser(HTMLParser):
    """
    A minimal HTML parser that extracts data from IDOT pages without needing BeautifulSoup.
    This is necessary because serverless environments have limited dependencies.
    We're looking for tables and specific data patterns in the HTML structure.
    """
    def __init__(self):
        super().__init__()
        self.tables = []
        self.current_table = []
        self.current_row = []
        self.current_cell = ''
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.links = []
        
    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self.in_table = True
            self.current_table = []
        elif tag == 'tr' and self.in_table:
            self.in_row = True
            self.current_row = []
        elif tag in ['td', 'th'] and self.in_row:
            self.in_cell = True
            self.current_cell = ''
        elif tag == 'a' and self.in_cell:
            # Extract href links from table cells
            for attr_name, attr_value in attrs:
                if attr_name == 'href':
                    self.links.append(attr_value)
    
    def handle_endtag(self, tag):
        if tag == 'table':
            self.in_table = False
            if self.current_table:
                self.tables.append(self.current_table)
        elif tag == 'tr' and self.in_row:
            self.in_row = False
            if self.current_row:
                self.current_table.append(self.current_row)
        elif tag in ['td', 'th'] and self.in_cell:
            self.in_cell = False
            self.current_row.append(self.current_cell.strip())
    
    def handle_data(self, data):
        if self.in_cell:
            self.current_cell += data


def fetch_url(url):
    """
    Fetch a URL and return its HTML content.
    We're running this on a server, so there are no CORS restrictions.
    We add a user agent to be polite to the IDOT servers.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        raise Exception(f"HTTP Error {e.code}: {e.reason}")
    except urllib.error.URLError as e:
        raise Exception(f"URL Error: {e.reason}")
    except Exception as e:
        raise Exception(f"Fetch Error: {str(e)}")


def parse_repository_page(html_content, base_url):
    """
    Parse the IDOT repository page to extract contract URLs.
    The repository page contains a table with multiple contracts.
    We need to filter by county and status, then extract the detail page URLs.
    
    Returns a list of dictionaries with contract information.
    """
    parser = SimpleHTMLParser()
    parser.feed(html_content)
    
    contracts = []
    
    # IDOT pages typically have the main data table as the largest table
    # We'll look through all tables to find rows that match our criteria
    for table in parser.tables:
        for row in table:
            if len(row) < 3:  # Skip header rows or incomplete rows
                continue
            
            # Look for county and status in the row
            row_text = ' '.join(row).lower()
            
            # Check if any valid county is mentioned
            has_valid_county = any(county in row_text for county in VALID_COUNTIES)
            
            # Check if any valid status is mentioned
            has_valid_status = any(status in row_text for status in VALID_STATUSES)
            
            if has_valid_county and has_valid_status:
                # This row matches our criteria - it should contain a link to the contract detail page
                # We need to find the contract number or link in this row
                for cell in row:
                    # Look for contract detail links (they typically contain "LbContractDetail")
                    if 'contract' in cell.lower() or any(char.isdigit() for char in cell):
                        contracts.append({
                            'row_data': row,
                            'county': next((c for c in VALID_COUNTIES if c in row_text), 'unknown'),
                            'status': next((s for s in VALID_STATUSES if s in row_text), 'unknown')
                        })
                        break
    
    # Now we need to extract the actual URLs from the links found in the page
    # IDOT contract detail pages follow a pattern like: .../LbContractDetail/...
    contract_urls = []
    for link in parser.links:
        if 'LbContractDetail' in link:
            full_url = urljoin(base_url, link)
            contract_urls.append(full_url)
    
    return contract_urls


def scrape_contract_detail(html_content):
    """
    Extract low bidder and awardee information from a contract detail page.
    These pages contain tables with contractor names and bid amounts.
    We're looking for the "Low Bidder" row and extracting the company name and price.
    """
    parser = SimpleHTMLParser()
    parser.feed(html_content)
    
    low_bidder = ''
    low_bid_amount = ''
    awardee = ''
    
    # Search through all tables for bidder information
    for table in parser.tables:
        for i, row in enumerate(table):
            row_text = ' '.join(row).lower()
            
            # Look for "low bidder" or similar patterns
            if 'low bid' in row_text or 'lowest bid' in row_text:
                # The bidder name is usually in the next cell or next row
                for cell in row:
                    # Look for dollar amounts (bid amount)
                    if '$' in cell:
                        low_bid_amount = cell.strip()
                    # Look for company names (usually contain "Inc", "LLC", "Corp", or are longer text)
                    elif len(cell) > 10 and not cell.replace('.', '').replace(',', '').replace('$', '').replace(' ', '').isdigit():
                        low_bidder = cell.strip()
                
                # Sometimes the data is in the next row
                if i + 1 < len(table):
                    next_row = table[i + 1]
                    for cell in next_row:
                        if '$' in cell and not low_bid_amount:
                            low_bid_amount = cell.strip()
                        elif len(cell) > 10 and not low_bidder:
                            low_bidder = cell.strip()
            
            # Look for awardee information
            if 'award' in row_text and 'awardee' in row_text:
                for cell in row:
                    if len(cell) > 10 and not cell.replace('.', '').replace(',', '').replace('$', '').replace(' ', '').isdigit():
                        awardee = cell.strip()
    
    return {
        'low_bidder': low_bidder or 'Not Found',
        'low_bid_amount': low_bid_amount or 'Not Found',
        'awardee': awardee or 'Not Found'
    }


def process_repository(repo_url):
    """
    Main processing function that orchestrates the entire scraping workflow.
    
    Steps:
    1. Fetch the repository page (the table of contracts)
    2. Parse it and extract individual contract URLs that match our filters
    3. Fetch each contract detail page
    4. Extract bidder information from each page
    5. Compile everything into CSV format
    
    Returns a CSV string ready for download.
    """
    results = []
    
    # Step 1: Fetch the repository page
    try:
        html = fetch_url(repo_url)
    except Exception as e:
        raise Exception(f"Failed to fetch repository page: {str(e)}")
    
    # Step 2: Extract contract URLs from the repository page
    contract_urls = parse_repository_page(html, repo_url)
    
    if not contract_urls:
        raise Exception("No matching contracts found. Please check the URL and filter criteria.")
    
    # Step 3 & 4: Fetch and scrape each contract detail page
    for idx, contract_url in enumerate(contract_urls, 1):
        try:
            contract_html = fetch_url(contract_url)
            data = scrape_contract_detail(contract_html)
            
            results.append({
                'contract_url': contract_url,
                'low_bidder': data['low_bidder'],
                'low_bid_amount': data['low_bid_amount'],
                'awardee': data['awardee']
            })
        except Exception as e:
            # If a specific contract fails, record the error but continue with others
            results.append({
                'contract_url': contract_url,
                'low_bidder': f'ERROR: {str(e)}',
                'low_bid_amount': '',
                'awardee': ''
            })
    
    # Step 5: Convert results to CSV format
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=['contract_url', 'low_bidder', 'low_bid_amount', 'awardee'])
    writer.writeheader()
    writer.writerows(results)
    
    return output.getvalue()


class handler(BaseHTTPRequestHandler):
    """
    This is the entry point for Vercel serverless functions.
    When a request comes in from the frontend, this handler processes it.
    """
    
    def do_POST(self):
        """Handle POST requests from the frontend"""
        
        # Set CORS headers so the browser allows our frontend to call this function
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        
        try:
            # Read the request body (which contains the repository URL)
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            repo_url = data.get('repo_url', '').strip()
            
            if not repo_url:
                self.wfile.write(json.dumps({
                    'error': 'No repository URL provided'
                }).encode())
                return
            
            # Process the repository and generate CSV
            csv_content = process_repository(repo_url)
            
            # Return the CSV data to the frontend
            self.wfile.write(json.dumps({
                'success': True,
                'csv': csv_content,
                'message': f'Successfully scraped {csv_content.count(chr(10)) - 1} contracts'
            }).encode())
            
        except Exception as e:
            # If anything goes wrong, send the error back to the frontend
            self.wfile.write(json.dumps({
                'error': str(e)
            }).encode())
    
    def do_OPTIONS(self):
        """Handle OPTIONS requests for CORS preflight"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
