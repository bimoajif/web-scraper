
import os
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()


# =====================================================
# CONFIGURATION
# =====================================================

BEARER_TOKEN = os.getenv("X_BEARER_TOKEN")

SEARCH_ENDPOINT = os.getenv(
    "X_SEARCH_ENDPOINT",
    "https://api.x.com/2/tweets/search/recent"
)

DEFAULT_LIMIT = int(
    os.getenv("TWITTER_LIMIT", "500")
)

LANGUAGE = os.getenv("X_LANGUAGE", "id")

QUERIES = [
    q.strip()
    for q in os.getenv(
        "X_SEARCH_QUERIES", ""
    ).split(";")
    if q.strip()
]

MAX_RESULTS = 100
MAX_RETRIES = 3
REQUEST_TIMEOUT = 30
DELAY = 1.0

TWEET_FIELDS = [
    "created_at",
    "public_metrics",
    "author_id",
    "lang",
    "entities",
]

USER_FIELDS = [
    "username",
    "name",
]

EXPANSIONS = [
    "author_id"
]


# =====================================================
# API SESSION
# =====================================================

session = requests.Session()

session.headers.update({
    "Authorization": f"Bearer {BEARER_TOKEN}",
    "Content-Type": "application/json",
})


# =====================================================
# REGION DETECTION
# =====================================================

def detect_region(query):
    """
    Identify target region based on search query.
    """

    query = query.lower()

    if "singkawang" in query:
        return "Singkawang"

    if "sambas" in query:
        return "Sambas"

    if "bengkayang" in query:
        return "Bengkayang"

    return None


# =====================================================
# DATE FILTER
# =====================================================

def get_date_filters():

    start_date = os.getenv("X_START_DATE")
    end_date = os.getenv("X_END_DATE")

    filters = {}

    if start_date:
        start = datetime.strptime(
            start_date, "%Y-%m-%d"
        ).replace(tzinfo=timezone.utc)

        filters["start_time"] = (
            start.strftime("%Y-%m-%dT%H:%M:%SZ")
        )

    if end_date:
        end = datetime.strptime(
            end_date, "%Y-%m-%d"
        ).replace(tzinfo=timezone.utc)

        end += timedelta(days=1)

        filters["end_time"] = (
            end.strftime("%Y-%m-%dT%H:%M:%SZ")
        )

    return filters


# =====================================================
# QUERY HANDLING
# =====================================================

def prepare_query(query):

    query = query.strip()

    if LANGUAGE and f"lang:{LANGUAGE}" not in query:
        query += f" lang:{LANGUAGE}"

    if "-is:retweet" not in query:
        query += " -is:retweet"

    return query


# =====================================================
# API REQUEST
# =====================================================

def request_api(params):

    for attempt in range(MAX_RETRIES):

        try:

            response = session.get(
                SEARCH_ENDPOINT,
                params=params,
                timeout=REQUEST_TIMEOUT,
            )

            if response.status_code == 429:

                reset = response.headers.get(
                    "x-rate-limit-reset"
                )

                wait_time = (
                    max(
                        1,
                        int(reset) - int(time.time()) + 1
                    )
                    if reset
                    else 60
                )

                print(
                    f"[rate-limit] Waiting {wait_time} seconds"
                )

                time.sleep(wait_time)
                continue

            if response.status_code >= 500:
                response.raise_for_status()

            response.raise_for_status()

            return response.json()

        except requests.RequestException as error:

            if attempt == MAX_RETRIES - 1:
                raise RuntimeError(
                    f"X API request failed: {error}"
                ) from error

            wait_time = 2 ** (attempt + 1)

            print(
                f"[retry] {error} "
                f"({attempt + 1}/{MAX_RETRIES})"
            )

            time.sleep(wait_time)

    raise RuntimeError(
        "X API request failed after retries."
    )


# =====================================================
# DATETIME
# =====================================================

def parse_datetime(value):

    if not value:
        return None

    dt = datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )

    return (
        dt.astimezone(timezone.utc)
        .replace(tzinfo=None)
    )


# =====================================================
# TRANSFORM TWEET
# =====================================================

def transform_tweet(tweet, users, query):

    tweet_id = tweet["id"]

    content = tweet.get("text", "")

    author_id = tweet.get("author_id")

    user = users.get(author_id, {})

    username = user.get("username")

    if username:
        url = (
            f"https://x.com/{username}/status/{tweet_id}"
        )
    else:
        url = (
            f"https://x.com/i/web/status/{tweet_id}"
        )

    metrics = tweet.get(
        "public_metrics", {}
    )

    trend_score = (
        metrics.get("like_count", 0)
        + metrics.get("retweet_count", 0)
        + metrics.get("reply_count", 0)
        + metrics.get("quote_count", 0)
    )

    return {

        "source": "twitter",

        "title": content[:500] or f"Post {tweet_id}",

        "content": content,

        "url": url,

        "topic": "Perpajakan",

        "category": "Social Media",

        "region": detect_region(query),

        "trend_score": 0,

        "sentiment": None,

        "published_at": parse_datetime(
            tweet.get("created_at")
        ),

    }


# =====================================================
# FETCH TWEETS
# =====================================================

def fetch_tweets(query, limit):

    query = prepare_query(query)

    params = {
        "query": query,
        "max_results": min(MAX_RESULTS, 100),
        "tweet.fields": ",".join(TWEET_FIELDS),
        "expansions": ",".join(EXPANSIONS),
        "user.fields": ",".join(USER_FIELDS),
        "sort_order": "recency",
    }

    params.update(get_date_filters())

    tweets = []
    seen_ids = set()

    next_token = None

    print(f"\n[query] {query}")
    print(f"[target] {limit}")

    while len(tweets) < limit:

        if next_token:
            params["next_token"] = next_token
        else:
            params.pop("next_token", None)

        response = request_api(params)

        meta = response.get("meta", {})

        print("\n[API DEBUG]")
        print("Result count :", meta.get("result_count"))
        print("Oldest ID    :", meta.get("oldest_id"))
        print("Newest ID    :", meta.get("newest_id"))

        if response.get("errors"):
            print("[API ERRORS]", response["errors"])

        data = response.get("data", [])

        if not data:
            print("[info] API returned no tweets.")
            print("[debug] Full response:")
            print(response)
            break

        users = {
            user["id"]: user
            for user in response.get(
                "includes", {}
            ).get("users", [])
        }

        if not data:
            print("[info] No more tweets.")
            break

        for tweet in data:

            tweet_id = tweet["id"]

            if tweet_id in seen_ids:
                continue

            seen_ids.add(tweet_id)

            tweets.append(
                transform_tweet(
                    tweet,
                    users,
                    query
                )
            )

            if len(tweets) >= limit:
                break

        print(
            f"[progress] {len(tweets)}/{limit}"
        )

        next_token = response.get(
            "meta", {}
        ).get("next_token")

        if not next_token:
            break

        time.sleep(DELAY)

    return tweets


# =====================================================
# MAIN COLLECTOR
# =====================================================

def main(limit=DEFAULT_LIMIT):

    if not BEARER_TOKEN:
        raise ValueError(
            "X_BEARER_TOKEN belum dikonfigurasi di .env"
        )

    if not QUERIES:
        raise ValueError(
            "X_SEARCH_QUERIES belum dikonfigurasi di .env"
        )

    print("\n====================================")
    print("       TWITTER / X COLLECTOR")
    print("====================================")

    print(f"Target total : {limit}")
    print(f"Total query  : {len(QUERIES)}")

    all_tweets = []

    seen_ids = set()

    # Divide target evenly across regions
    base_quota = limit // len(QUERIES)
    remainder = limit % len(QUERIES)

    for index, query in enumerate(QUERIES):

        quota = base_quota + (
            1 if index < remainder else 0
        )

        print(
            f"\n[region] {detect_region(query)}"
        )

        try:

            tweets = fetch_tweets(
                query=query,
                limit=quota
            )

            for tweet in tweets:

                # Extract tweet ID from URL
                tweet_id = tweet["url"].rsplit(
                    "/", 1
                )[-1]

                if tweet_id in seen_ids:
                    continue

                seen_ids.add(tweet_id)
                all_tweets.append(tweet)

        except Exception as error:

            print(
                f"[error] Query failed: {query}"
            )

            print(f"[error] {error}")

        print(
            f"[total] {len(all_tweets)}/{limit}"
        )

    if not all_tweets:

        print("[info] No tweets collected.")

        return pd.DataFrame()

    final_df = (
        pd.DataFrame(all_tweets)
        .drop_duplicates(
            subset=["url"],
            keep="first"
        )
        .reset_index(drop=True)
    )

    print("\n========== COLLECTION SUMMARY ==========")
    print(f"Tweets collected : {len(final_df)}")

    print("\nDistribution by region:")

    print(
        final_df["region"]
        .value_counts(dropna=False)
        .to_string()
    )

    print("========================================")

    # IMPORTANT:
    # Do not save to database here.
    # common.py handles database insertion.

    return final_df


# =====================================================
# ENTRY POINT
# =====================================================

def collect():

    return main(limit=DEFAULT_LIMIT)


if __name__ == "__main__":

    df = main()

    if not df.empty:

        print("\nPreview:")

        print(
            df[
                [
                    "title",
                    "region",
                    "published_at",
                    "trend_score",
                    "url",
                ]
            ].head(10).to_string(index=False)
        )
