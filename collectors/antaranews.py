import time
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup
from lxml import html

from db import init_db, save_trends


BASE_URL = "https://kalbar.antaranews.com"

INDEX_URLS = [
    f"{BASE_URL}/kalbar/kota-singkawang",
    f"{BASE_URL}/kalbar/kabupaten-sambas",
    f"{BASE_URL}/kalbar/kabupaten-bengkayang",
]

# Map category URLs to their respective regions
REGION_MAP = {
    "singkawang": "Singkawang",
    "sambas": "Sambas",
    "bengkayang": "Bengkayang",
}

DELAY = 1.5

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
}

session = requests.Session()
session.headers.update(HEADERS)


def get_links(url, retries=3):
    for attempt in range(retries):
        try:
            resp = session.get(url, timeout=15)
            resp.raise_for_status()

            tree = html.fromstring(resp.content)

            links = tree.xpath(
                '//div[contains(@class, "card__post-list")]'
                '//h2[contains(@class, "post_title")]/a/@href'
            )

            return list(dict.fromkeys(
                urljoin(url, link) for link in links
            ))

        except requests.RequestException as e:
            print(
                f"[warn] {url} failed ({e}), "
                f"retry {attempt + 1}/{retries}"
            )
            time.sleep(2 * (attempt + 1))

    return []


def get_soup(url, retries=3):
    for attempt in range(retries):
        try:
            resp = session.get(url, timeout=15)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "lxml")

            title = (
                soup.title.get_text(strip=True)
                .rsplit("- ANTARA News Kalimantan Barat", 1)[0].strip()
                if soup.title else None
            )

            # Extract article paragraphs
            content_section = soup.select_one(
                ".wrap__article-detail-content.post-content"
            )

            paragraphs = (
                content_section.find_all("p")
                if content_section else soup.find_all("p")
            )

            content = "\n".join(
                text for p in paragraphs
                if (text := p.get_text(" ", strip=True))
                and len(text) > 30
            )

            if title and content:
                return {
                    "url": url,
                    "title": title,
                    "content": content,
                }

            print(f"[skip] No title/content: {url}")
            return None

        except requests.RequestException as e:
            print(
                f"[warn] {url} failed ({e}), "
                f"retry {attempt + 1}/{retries}"
            )
            time.sleep(2 * (attempt + 1))

    return None


def get_region(index_url):
    """Determine region from the category URL."""
    for keyword, region in REGION_MAP.items():
        if keyword in index_url.lower():
            return region

    return "West Kalimantan"


def main(limit=100, pages_per_index=3):
    articles = []

    # Initialize MySQL tables
    init_db()

    print("Starting Antara News crawler...")
    print(f"Article limit: {limit}")

    for index_url in INDEX_URLS:

        for page in range(1, pages_per_index + 1):

            url = index_url if page == 1 else f"{index_url}/{page}"

            print(f"\n[page] {url}")

            links = get_links(url)

            print(f"[found] {len(links)} article links on page {page}")

            for link in links:

                if len(articles) >= limit:
                    break

                print(f"[{len(articles) + 1}/{limit}] {link}")

                article = get_soup(link)

                if article:
                    # Add database metadata
                    article.update({
                        "source": "antaranews",
                        "topic": None,
                        "category": "Regional",
                        "region": get_region(index_url),
                        "trend_score": 0,
                        "sentiment": None,
                    })

                    articles.append(article)

                time.sleep(DELAY)

    if not articles:
        print("No articles collected.")
        return pd.DataFrame()

    # Remove duplicate URLs within this scraping session
    final_df = (
        pd.DataFrame(articles)
        .drop_duplicates(subset=["url"], keep="first")
        .reset_index(drop=True)
    )

    # Save articles to MySQL
    records = final_df.to_dict(orient="records")

    saved_count = save_trends(records)

    skipped_count = len(records) - saved_count

    print("\n========== SCRAPING SUMMARY ==========")
    print(f"Articles collected : {len(records)}")
    print(f"New articles saved : {saved_count}")
    print(f"Already in database: {skipped_count}")
    print("======================================")

    return final_df

def collect():
    """
    Entry point used by collect.py.
    Returns the scraped DataFrame.
    """
    return main(limit=1000, pages_per_index=3)

if __name__ == "__main__":
    df = main(limit=500)

    if not df.empty:
        print("\nScraping preview:")
        print(df[["title", "region", "url"]].head(10))
