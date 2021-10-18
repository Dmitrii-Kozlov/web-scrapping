import csv
import datetime
import re
import requests
import os.path
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from collections import Counter
from stop_words import get_stop_words

saved_domain = {
    'tim.blog': {
        'tag': 'div',
        'class': 'content-area',
        'regex': r'^/(?P<year>\d+){4}/(?P<month>\d+){2}/(?P<day>\d+){2}/(?P<slug>[\w-]+)/$'
    },
}


def clean_word(word):
    word = word.replace("!", "")
    word = word.replace("?", "")
    word = word.replace(".", "")
    word = word.replace(",", "")
    word = word.replace(":", "")
    word = word.replace(";", "")
    word = word.replace("(", "")
    word = word.replace(")", "")
    return word

def clean_up_words(words):
    new_words = []
    stop_words = get_stop_words('en')
    for word in words:
        word = word.lower()
        cleaned_word = clean_word(word)
        if cleaned_word in stop_words:
            pass
        else:
            new_words.append(cleaned_word)
    return new_words

def fetch_url(url):
    response = requests.Response()
    try:
        response = requests.get(url)
    except requests.exceptions.ConnectionError:
        print("Could not connect to the url. Please, try again.")
    return response

def valid_url(url):
    http_regex = r'^https?://'
    pattern = re.compile(http_regex)
    is_match = pattern.match(url)
    if is_match is None:
        raise ValueError("This url does not start with http:// or https://")
    return url

def end_program():
    raise KeyboardInterrupt("Program forced to quit.")

def append_http(url):
    if not url.startswith('http'):
        url = f'http://{url}'
    return url

def get_input():
    url = input("Enter url you want to parse: ")
    if url == 'q':
        end_program()
    url = append_http(url)
    try:
        valid_url(url)
    except ValueError as err:
        print(err)
        return get_input()
    return url

def soupify(html):
    soup = BeautifulSoup(html, 'html.parser')
    return soup

def get_domain_name(url):
    return urlparse(url).netloc

def get_path_name(url):
    return urlparse(url).path

def get_url_lookup_class(url):
    domain_name = get_domain_name(url)
    lookup_class = {}
    if domain_name in saved_domain:
        lookup_class = saved_domain[domain_name]
    return lookup_class

def get_content_data(soup, url):
    lookup_dict = get_url_lookup_class(url)
    if lookup_dict is None or 'tag' not in lookup_dict:
        return soup.find('body')
    return soup.find(lookup_dict['tag'], {'class': lookup_dict['class']})

def parse_links(soup):
    a_tags = soup.find_all("a", href=True)
    links = []
    for a in a_tags:
        link = a['href']
        links.append(link)
    return links

def get_local_paths(soup, url):
    links = parse_links(soup)
    local_paths = []
    domain_name = get_domain_name(url)
    for link in links:
        link_domain = get_domain_name(link)
        if link_domain == domain_name:
            path = get_path_name(link)
            local_paths.append(path)
        elif link.startswith("/"):
            local_paths.append(link)
    return list(set(local_paths))


def get_regex_pattern(root_domain):
    pattern = r"^/(?P<slug>[\w-]+)$"
    if root_domain in saved_domain:
        regex = saved_domain[root_domain].get("regex")
        if regex is not None:
            pattern = regex
    return pattern

def match_regex(string, regex):
    pattern = re.compile(regex)
    is_a_match = pattern.match(string) # regex match or None
    if is_a_match is None:
        return False
    return True

def get_regex_local_paths(soup, url):
    links = parse_links(soup)
    local_paths = []
    domain_name = get_domain_name(url)
    regex = get_regex_pattern(domain_name)
    for link in links:
        link_domain = get_domain_name(link)
        if link_domain == domain_name:
            path = get_path_name(link)
            is_match = match_regex(path, regex)
            if is_match:
                local_paths.append(path)
        elif link.startswith("/"):
            is_match = match_regex(link, regex)
            if is_match:
                local_paths.append(path)
    return list(set(local_paths))

def parse_blog_post(path, url):
    domain_name = get_domain_name(url)
    lookup_url = f"http://{domain_name}{path}"
    lookup_response = fetch_url(lookup_url)
    if lookup_response.status_code in range(200, 299):
        lookup_soup = soupify(lookup_response.text)
        lookup_html_soup = get_content_data(lookup_soup, lookup_url)
        words = lookup_html_soup.text.split()
        clean_words = clean_up_words(words)
        #print(clean_words)
    return clean_words

def main():
    url = get_input()
    response = fetch_url(url)
    if response.status_code not in range(200, 299):
        print(f'Invalid request, you cannot view this. Status code is {response.status_code}')
        return None
    response_html = response.text
    soup = soupify(response_html)
    html_soup = get_content_data(soup, url)
    # print(html_soup)
    paths = get_regex_local_paths(html_soup, url)
    # print(paths)
    words = []
    for path in paths:
        print(path)
        clean_words = parse_blog_post(path, url)
        words += clean_words
    print(Counter(words).most_common(50))
# main()



def fetch_links_words(url):
    print(url, "scraping...")
    response = fetch_url(url)
    soup = soupify(response.text)
    html_soup = get_content_data(soup, url)
    local_paths = get_regex_local_paths(html_soup, url)
    domain_name = get_domain_name(url)
    to_scrape = [f"http://{domain_name}{path}" for path in local_paths]
    words = []
    if html_soup:
        words = html_soup.text.split()
    clean_words = clean_up_words(words)
    return set(to_scrape), clean_words

def scrape_links(to_scrape, scraped, current_depth=0, max_depth=3, words=[]):
    if current_depth < max_depth:
        new_set_to_scrape = set()
        while to_scrape:
            item = to_scrape.pop()
            if item not in scraped:
                new_path, new_words = fetch_links_words(item)
                words += new_words
                new_set_to_scrape = (new_set_to_scrape | new_path)
            scraped.add(item)
        current_depth += 1
        return scrape_links(to_scrape=new_set_to_scrape, scraped=scraped, current_depth=current_depth,
                            max_depth=max_depth, words=words)
    return scraped, words

def main_with_depth():
    url = get_input() #'http://tim.blog'
    to_scrape, new_words = fetch_links_words(url)
    scraped = set([url])
    final_scraped_items, final_scraped_words = scrape_links(to_scrape, scraped, current_depth=0, max_depth=2, words=new_words)
    print(final_scraped_items)

main_with_depth()
