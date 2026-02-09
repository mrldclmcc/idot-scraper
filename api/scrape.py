"""
IDOT Bid Letting Scraper - Serverless Function (Vercel-compatible version)
This version uses Vercel's native request/response format instead of BaseHTTPRequestHandler
"""

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
    A minimal HTML parser that extracts tables and links from IDOT pages.
    This works without external dependencies like BeautifulSoup.
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
    """Fetch a URL and return its HTML content"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        raise Exception(f"Failed to fetch {url}: {str(e)}")


def parse_repository_page(html_content, base_url):
    """Extract contract URLs from the repository page that match our filter criteria"""
    parser = SimpleHTMLParser()
    parser.feed(html_content)
    
    # Find contract detail URLs that contain "LbContractDetail"
    contract_urls = []
    for link in parser.links:
        if 'LbContractDetail' in link:
            full_url = urljoin(base_url, link)
            if full_url not in contract_urls:
                contract_urls.append(full_url)
    
    # Filter based on county and status by checking the table content
    filtered_urls = []
    for table in parser.tables:
        for row in table:
            if len(row) < 3:
                continue
            
            row_text = ' '.join(row).lower()
            has_valid_county = any(county in row_text for county in VALID_COUNTIES)
            has_valid_status = any(status in row_text for status in VALID_STATUSES)
            
            if has_valid_county and has_valid_status:
                # This row matches - find corresponding URL
                # We'll match URLs in order they appear
                if contract_urls:
                    url = contract_urls.pop(0)
                    if url not in filtered_urls:
                        filtered_urls.append(url)
    
    return filtered_urls


def scrape_contract_detail(html_content):
    """Extract bidder information from a contract detail page"""
    parser = SimpleHTMLParser()
    parser.feed(html_content)
    
    low_bidder = ''
    low_bid_amount = ''
    awardee = ''
    
    for table in parser.tables:
        for i, row in enumerate(table):
            row_text = ' '.join(row).lower()
            
            if 'low bid' in row_text or 'lowest bid' in row_text:
                for cell in row:
                    if '$' in cell:
                        low_bid_amount = cell.strip()
                    elif len(cell) > 10 and not cell.replace('.', '').replace(',', '').replace('$', '').replace(' ', '').isdigit():
                        low_bidder = cell.strip()
                
                if i + 1 < len(table):
                    next_row = table[i + 1]
                    for cell in next_row:
                        if '$' in cell and not low_bid_amount:
                            low_bid_amount = cell.strip()
                        elif len(cell) > 10 and not low_bidder:
                            low_bidder = cell.strip()
            
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
    """Main processing function that orchestrates the scraping workflow"""
    results = []
    
    # Fetch the repository page
    html = fetch_url(repo_url)
    
    # Extract contract URLs
    contract_urls = parse_repository_page(html, repo_url)
    
    if not contract_urls:
        raise Exception("No matching contracts found. Check the URL and filter criteria.")
    
    # Scrape each contract
    for contract_url in contract_urls:
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
            results.append({
                'contract_url': contract_url,
                'low_bidder': f'ERROR: {str(e)}',
                'low_bid_amount': '',
                'awardee': ''
            })
    
    # Convert to CSV
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=['contract_url', 'low_bidder', 'low_bid_amount', 'awardee'])
    writer.writeheader()
    writer.writerows(results)
    
    return output.getvalue()


# This is the Vercel serverless function entry point
# Vercel expects a function that takes (request) and returns a response
def handler(request):
    """
    Vercel serverless function handler.
    This function is called when a request comes to /api/scrape
    """
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type'
            },
            'body': ''
        }
    
    # Only accept POST requests
    if request.method != 'POST':
        return {
            'statusCode': 405,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Method not allowed'})
        }
    
    try:
        # Parse the request body
        if hasattr(request, 'body'):
            body = request.body
            if isinstance(body, bytes):
                body = body.decode('utf-8')
            data = json.loads(body)
        else:
            data = request.json if hasattr(request, 'json') else {}
        
        repo_url = data.get('repo_url', '').strip()
        
        if not repo_url:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'No repository URL provided'})
            }
        
        # Process the repository
        csv_content = process_repository(repo_url)
        
        # Return success response
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': True,
                'csv': csv_content,
                'message': f'Successfully scraped {csv_content.count(chr(10)) - 1} contracts'
            })
        }
        
    except Exception as e:
        # Return error response
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': str(e)})
        }
