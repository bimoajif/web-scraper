import argparse

from sqlalchemy import select

from db import SessionLocal, Trend, init_db
from classifiers.topics import classify_topics


def update_topics(
    source=None,
    limit=None,
    batch_size=200,
    apply_changes=False
):
    """
    Reclassify existing MySQL articles.

    By default, this script only previews changes.
    Use --apply to save changes to MySQL.
    """

    init_db()

    last_id = 0

    total_processed = 0
    total_changed = 0
    total_unchanged = 0

    print("\n===================================")
    print(" INTERNET TRENDS TOPIC UPDATER")
    print("===================================")

    print(f"Source: {source or 'All sources'}")
    print(f"Mode: {'APPLY CHANGES' if apply_changes else 'DRY RUN'}")

    if limit:
        print(f"Limit: {limit}")

    print("-----------------------------------\n")

    while True:

        with SessionLocal() as session:

            query = (
                select(Trend)
                .where(Trend.id > last_id)
                .order_by(Trend.id)
                .limit(batch_size)
            )

            if source:
                query = query.where(
                    Trend.source == source
                )

            if limit:
                remaining = limit - total_processed

                if remaining <= 0:
                    break

                query = query.limit(
                    min(batch_size, remaining)
                )

            records = session.scalars(query).all()

            if not records:
                break

            for record in records:

                last_id = record.id
                total_processed += 1

                classification = classify_topics(
                    record.title or "",
                    record.content or ""
                )

                new_topic = classification["topic"]
                old_topic = record.topic or ""

                if old_topic != new_topic:

                    total_changed += 1

                    print(
                        f"[UPDATE] ID: {record.id} | "
                        f"{old_topic} -> {new_topic}"
                    )

                    if apply_changes:
                        record.topic = new_topic

                else:
                    total_unchanged += 1

                # Display additional classification information
                if total_processed <= 10:

                    print(
                        f"    Title: {record.title[:100]}"
                    )

                    print(
                        f"    Topics: {classification['topics']}"
                    )

                    print(
                        f"    Keywords: {classification['keywords']}"
                    )

                    print(
                        f"    Confidence: {classification['confidence']}"
                    )

            if apply_changes:
                session.commit()

        print(
            f"\nProgress: {total_processed} articles | "
            f"{total_changed} changed | "
            f"{total_unchanged} unchanged\n"
        )

    print("\n===================================")
    print(" UPDATE SUMMARY")
    print("===================================")

    print(f"Processed: {total_processed}")
    print(f"Changed: {total_changed}")
    print(f"Unchanged: {total_unchanged}")

    if apply_changes:
        print("\nMySQL changes have been committed.")
    else:
        print("\nDRY RUN: No database changes were made.")
        print("Run again with --apply to save changes.")

    print("===================================\n")


def main():

    parser = argparse.ArgumentParser(
        description="Update topics of existing MySQL articles"
    )

    parser.add_argument(
        "--source",
        type=str,
        default=None,
        help="Filter by source, e.g. suarakalbar"
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of articles to process"
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=200,
        help="Number of articles processed per batch"
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Save topic changes to MySQL"
    )

    args = parser.parse_args()

    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be greater than zero")

    if args.batch_size <= 0:
        parser.error("--batch-size must be greater than zero")

    update_topics(
        source=args.source,
        limit=args.limit,
        batch_size=args.batch_size,
        apply_changes=args.apply
    )


if __name__ == "__main__":
    main()
