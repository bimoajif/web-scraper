
import os
from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Float,
    Index,
)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.engine import URL

load_dotenv()

# MySQL connection settings
DATABASE_URL = URL.create(
    drivername="mysql+pymysql",
    username=os.getenv("DB_USER", "trends_user"),
    password=os.getenv("DB_PASSWORD", ""),
    host=os.getenv("DB_HOST", "127.0.0.1"),
    port=int(os.getenv("DB_PORT", "3306")),
    database=os.getenv("DB_NAME", "internet_trends"),
    query={"charset": "utf8mb4"},
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)

Base = declarative_base()


class Trend(Base):
    __tablename__ = "trends"

    id = Column(Integer, primary_key=True, autoincrement=True)

    source = Column(String(100), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=True)
    url = Column(String(1000), nullable=True)

    topic = Column(String(255), nullable=True, index=True)
    category = Column(String(100), nullable=True, index=True)
    region = Column(String(150), nullable=True, index=True)

    trend_score = Column(Float, default=0)
    sentiment = Column(String(30), nullable=True)

    published_at = Column(DateTime, nullable=True)
    collected_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )

    __table_args__ = (
        Index("idx_topic_collected", "topic", "collected_at"),
    )


def init_db():
    """Create database tables if they do not exist."""
    Base.metadata.create_all(bind=engine)


def save_trend(data):
    """Save one trend record."""
    with SessionLocal() as session:
        trend = Trend(**data)
        session.add(trend)
        session.commit()
        session.refresh(trend)
        return trend.id


def save_trends(records):
    """Save multiple trend records, skipping URLs already in MySQL."""
    if not records:
        return 0

    with SessionLocal() as session:
        urls = list({
            record["url"]
            for record in records
            if record.get("url")
        })

        existing_urls = set()

        if urls:
            existing_urls = {
                url for (url,) in
                session.query(Trend.url)
                .filter(Trend.url.in_(urls))
                .all()
            }

        new_records = []
        seen_urls = set()

        for record in records:
            url = record.get("url")

            if url and (url in existing_urls or url in seen_urls):
                continue

            if url:
                seen_urls.add(url)

            new_records.append(Trend(**record))

        if not new_records:
            return 0

        session.add_all(new_records)
        session.commit()

        return len(new_records)


def get_trends(limit=1000):
    """Retrieve the latest trend records."""
    with SessionLocal() as session:
        return (
            session.query(Trend)
            .order_by(Trend.collected_at.desc())
            .limit(limit)
            .all()
        )


def get_trends_as_dict(limit=1000):
    """Retrieve trend records as dictionaries."""
    records = get_trends(limit)

    return [
        {
            "id": r.id,
            "source": r.source,
            "title": r.title,
            "content": r.content,
            "url": r.url,
            "topic": r.topic,
            "category": r.category,
            "region": r.region,
            "trend_score": r.trend_score,
            "sentiment": r.sentiment,
            "published_at": r.published_at,
            "collected_at": r.collected_at,
        }
        for r in records
    ]


def delete_old_trends(days=90):
    """Delete records older than the specified number of days."""
    from datetime import timedelta

    cutoff = datetime.now(datetime.timezone.utc) - timedelta(days=days)

    with SessionLocal() as session:
        deleted = (
            session.query(Trend)
            .filter(Trend.collected_at < cutoff)
            .delete(synchronize_session=False)
        )
        session.commit()
        return deleted


if __name__ == "__main__":
    init_db()
    print("MySQL database initialized successfully.")
