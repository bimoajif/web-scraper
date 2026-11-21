
from datetime import datetime

from sqlalchemy import select

from db import SessionLocal, Trend


def normalize_records(records):
    """
    Accept either:
    - pandas DataFrame
    - list of dictionaries
    """

    if records is None:
        return []

    if hasattr(records, "to_dict"):
        records = records.to_dict("records")

    if isinstance(records, dict):
        records = [records]

    if not isinstance(records, (list, tuple)):
        raise TypeError(
            "Collector must return a DataFrame, "
            "a list of dictionaries, or a dictionary."
        )

    return list(records)


def parse_datetime(value):
    """Convert ISO datetime strings to Python datetime."""

    if not value:
        return None

    if isinstance(value, datetime):
        return value

    if isinstance(value, str):
        try:
            return datetime.fromisoformat(
                value.replace("Z", "+00:00")
            ).replace(tzinfo=None)
        except ValueError:
            return None

    return None


def save_records(source, records):
    """Save records to MySQL, skipping existing articles."""

    records = normalize_records(records)

    if not records:
        return 0

    inserted = 0
    seen_urls = set()
    seen_titles = set()

    with SessionLocal() as session:

        urls = list({
            str(item.get("url")).strip()
            for item in records
            if item.get("url")
        })

        titles = list({
            str(item.get("title")).strip()
            for item in records
            if item.get("title")
        })

        existing_urls = set()
        existing_titles = set()

        if urls:
            existing_urls = set(
                session.scalars(
                    select(Trend.url).where(
                        Trend.source == source,
                        Trend.url.in_(urls)
                    )
                ).all()
            )

        if titles:
            existing_titles = set(
                session.scalars(
                    select(Trend.title).where(
                        Trend.source == source,
                        Trend.title.in_(titles)
                    )
                ).all()
            )

        for item in records:

            url = str(item.get("url") or "").strip()
            title = str(item.get("title") or "").strip()

            if not title:
                continue

            # Skip existing articles
            if url and url in existing_urls:
                continue

            if title in existing_titles:
                continue

            # Skip duplicates within the same crawl
            if url and url in seen_urls:
                continue

            if title in seen_titles:
                continue

            try:
                trend_score = float(
                    item.get("trend_score") or 0
                )
            except (TypeError, ValueError):
                trend_score = 0

            record = Trend(
                source=source,
                title=title[:500],
                content=str(
                    item.get("content")
                    or item.get("summary")
                    or ""
                ),
                url=url[:1000] if url else None,
                topic=str(
                    item.get("topic")
                    or title
                )[:255],
                category=str(
                    item.get("category") or ""
                )[:100],
                region=str(
                    item.get("region") or ""
                )[:150],
                trend_score=trend_score,
                sentiment=item.get("sentiment"),
                published_at=parse_datetime(
                    item.get("published_at")
                )
            )

            session.add(record)

            if url:
                seen_urls.add(url)

            seen_titles.add(title)
            inserted += 1

        session.commit()

    return inserted


def run_collector(source, collector_function):

    print(f"\nStarting collector: {source}")

    try:

        # Run scraper
        raw_records = collector_function()

        # Normalize returned data
        records = normalize_records(raw_records)

        # Save to MySQL
        inserted = save_records(
            source,
            records
        )

        message = (
            f"Fetched {len(records)} records; "
            f"inserted {inserted}; "
            f"skipped {len(records) - inserted}"
        )

        print(f"[{source}] {message}")

        return inserted, message

    except Exception as exc:

        message = str(exc)[:2000]

        print(f"[{source}] ERROR: {message}")

        return 0, message
