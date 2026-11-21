import argparse

from dotenv import load_dotenv

load_dotenv()

from db import init_db
from collectors.common import run_collector
from collectors.suarakalbar import collect as suarakalbar


def main():

    parser = argparse.ArgumentParser(
        description="Internet Trends Data Collector"
    )

    parser.add_argument(
        "--source",
        choices=["all", "suarakalbar"],
        default="all"
    )

    args = parser.parse_args()

    init_db()

    jobs = {
        "suarakalbar": suarakalbar
    }

    selected = (
        jobs
        if args.source == "all"
        else {args.source: jobs[args.source]}
    )

    for name, collector in selected.items():

        count, message = run_collector(
            name,
            collector
        )

        print(f"{name}: {message}")


if __name__ == "__main__":
    main()
