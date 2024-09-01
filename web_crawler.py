import argparse
import requests
from bs4 import BeautifulSoup
import re
import json
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor
from urllib.robotparser import RobotFileParser

MAX_THREADS = 10

def fetch_url(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.content
        else:
            print(f"Error: Failed to fetch {url}, status code {response.status_code}")
            return None
    except Exception as e:
        print(f"Error fetching URL {url}: {str(e)}")
        return None

def extract_parameters(content, base_url):
    soup = BeautifulSoup(content, 'html.parser')
    params = {}

    # Extract parameters from anchor tags
    for link in soup.find_all('a', href=True):
        full_url = urlparse(requests.compat.urljoin(base_url, link['href']))
        query_params = parse_qs(full_url.query)
        if query_params:
            params[full_url.geturl()] = query_params

    # Extract parameters from forms
    for form in soup.find_all('form'):
        action = form.get('action')
        full_url = urlparse(requests.compat.urljoin(base_url, action))
        form_params = {input_tag.get('name'): input_tag.get('value') for input_tag in form.find_all('input') if input_tag.get('name')}
        if form_params:
            params[full_url.geturl()] = form_params

    return params

def save_results(params, output_file):
    try:
        with open(output_file, 'w') as file:
            json.dump(params, file, indent=4)
        print(f"Results saved to {output_file}")
    except Exception as e:
        print(f"Error saving results: {str(e)}")

def handle_robots_txt(base_url):
    robots_url = requests.compat.urljoin(base_url, '/robots.txt')
    rp = RobotFileParser()
    try:
        rp.set_url(robots_url)
        rp.read()
        return rp
    except Exception as e:
        print(f"Error reading robots.txt at {robots_url}: {str(e)}")
        return None

def crawl(url, rp=None):
    if rp and not rp.can_fetch("*", url):
        print(f"Skipping {url} due to robots.txt restrictions.")
        return {}

    content = fetch_url(url)
    if content:
        return extract_parameters(content, url)
    return {}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Web Crawler for extracting URL parameters.")
    parser.add_argument("url", help="Target URL to crawl")
    parser.add_argument("output", help="File to save the extracted parameters")
    parser.add_argument("--threads", help="Number of threads to use", type=int, default=MAX_THREADS)

    args = parser.parse_args()
    url = args.url
    output_file = args.output
    max_threads = args.threads

    print(f"Crawling {url} with {max_threads} threads...")

    # Handle robots.txt
    rp = handle_robots_txt(url)

    # Extract initial parameters from the base URL
    params = crawl(url, rp)

    # Extract further URLs from the base URL to crawl concurrently
    content = fetch_url(url)
    if content:
        soup = BeautifulSoup(content, 'html.parser')
        urls_to_crawl = [requests.compat.urljoin(url, link['href']) for link in soup.find_all('a', href=True)]

        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            results = executor.map(lambda u: crawl(u, rp), urls_to_crawl)

        for result in results:
            params.update(result)

    if params:
        save_results(params, output_file)
    else:
        print("No parameters found.")
