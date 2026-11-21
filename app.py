
import io
from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from dotenv import load_dotenv
from sqlalchemy import select, desc, func, or_

from db import init_db, SessionLocal, Trend


# ==========================================
# CONFIGURATION
# ==========================================

load_dotenv()

st.set_page_config(
    page_title="Internet Trends Intelligence",
    page_icon="🌐",
    layout="wide"
)

init_db()


# ==========================================
# DATABASE FUNCTIONS
# ==========================================

def get_available_sources():
    """Get sources currently available in MySQL."""

    with SessionLocal() as session:
        sources = session.scalars(
            select(Trend.source)
            .distinct()
            .order_by(Trend.source)
        ).all()

    return sources


def get_total_records():
    """Get total number of records in the database."""

    with SessionLocal() as session:
        return session.scalar(
            select(func.count(Trend.id))
        ) or 0


def get_trends(days=7, sources=None, search=None):
    """Retrieve trends based on the selected filters."""

    cutoff = datetime.utcnow() - timedelta(days=days)

    with SessionLocal() as session:

        query = select(Trend).where(
            Trend.collected_at >= cutoff
        )

        if sources:
            query = query.where(
                Trend.source.in_(sources)
            )

        if search:
            keyword = f"%{search}%"

            query = query.where(
                or_(
                    Trend.topic.ilike(keyword),
                    Trend.title.ilike(keyword),
                    Trend.content.ilike(keyword),
                    Trend.region.ilike(keyword),
                    Trend.category.ilike(keyword)
                )
            )

        records = session.scalars(
            query.order_by(
                desc(Trend.collected_at)
            ).limit(10000)
        ).all()

        return [
            {
                "ID": r.id,
                "Source": r.source,
                "Topic": r.topic,
                "Title": r.title,
                "Content": r.content,
                "Category": r.category,
                "Region": r.region,
                "Trend Score": r.trend_score,
                "Sentiment": r.sentiment,
                "Published": r.published_at,
                "Collected": r.collected_at,
                "URL": r.url
            }
            for r in records
        ]


# ==========================================
# HEADER
# ==========================================

st.title("🌐 Internet Trends Intelligence")

st.caption(
    "Monitor internet trends from collected news and other online sources."
)


# ==========================================
# SIDEBAR FILTERS
# ==========================================

available_sources = get_available_sources()

with st.sidebar:

    st.header("Filters")

    days = st.selectbox(
        "Time range",
        [1, 7, 14, 30, 90],
        index=1
    )

    selected_sources = st.multiselect(
        "Sources",
        options=available_sources,
        default=available_sources,
        help="Leave empty to include all sources."
    )

    search = st.text_input(
        "Search topics, titles, or content",
        placeholder="e.g. Singkawang, pajak, bea cukai"
    )

    st.divider()

    st.caption(
        "Run python main.py --source suarakalbar "
        "to collect fresh data."
    )

    if st.button("Refresh dashboard", width='stretch'):
        st.rerun()


# ==========================================
# DATABASE QUERY
# ==========================================

total = get_total_records()

records = get_trends(
    days=days,
    sources=selected_sources,
    search=search
)

df = pd.DataFrame(records)


# ==========================================
# KPI CARDS
# ==========================================

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Total database records",
    f"{total:,}"
)

col2.metric(
    "Records in selected period",
    f"{len(df):,}"
)

col3.metric(
    "Sources active",
    df["Source"].nunique() if not df.empty else 0
)

col4.metric(
    "Selected period",
    f"{days} days"
)


# ==========================================
# TABS
# ==========================================

tab1, tab2, tab3 = st.tabs([
    "Overview",
    "Explore Data",
    "Collector Status"
])


# ==========================================
# OVERVIEW
# ==========================================

with tab1:

    if df.empty:

        st.info(
            "No records found. Run the Suara Kalbar collector "
            "or adjust your filters."
        )

    else:

        left, right = st.columns(2)

        # ----------------------------------
        # RECORDS BY SOURCE
        # ----------------------------------

        with left:

            st.subheader("Records by source")

            counts = (
                df.groupby("Source")
                .size()
                .reset_index(name="Records")
                .sort_values("Records", ascending=False)
            )

            fig = px.bar(
                counts,
                x="Source",
                y="Records",
                title="Data collection distribution"
            )

            st.plotly_chart(
                fig,
                width='stretch'
            )

        # ----------------------------------
        # TOP TOPICS
        # ----------------------------------

        with right:

            st.subheader("Most collected topics")

            top = (
                df.groupby("Topic")
                .size()
                .nlargest(15)
                .sort_values()
                .reset_index(name="Mentions")
            )

            fig = px.bar(
                top,
                x="Mentions",
                y="Topic",
                orientation="h",
                title="Top 15 topics"
            )

            st.plotly_chart(
                fig,
                width='stretch'
            )

        # ----------------------------------
        # RECORDS BY REGION
        # ----------------------------------

        if df["Region"].notna().any():

            st.subheader("Records by region")

            region_counts = (
                df.dropna(subset=["Region"])
                .groupby("Region")
                .size()
                .reset_index(name="Records")
                .sort_values("Records", ascending=False)
            )

            fig = px.bar(
                region_counts,
                x="Region",
                y="Records",
                title="Regional distribution"
            )

            st.plotly_chart(
                fig,
                width='stretch'
            )

        # ----------------------------------
        # LATEST RECORDS
        # ----------------------------------

        st.subheader("Latest collected signals")

        display_columns = [
            "Source",
            "Topic",
            "Title",
            "Category",
            "Region",
            "Collected",
            "URL"
        ]

        st.dataframe(
            df[display_columns].head(100),
            width='stretch',
            hide_index=True,
            column_config={
                "URL": st.column_config.LinkColumn(
                    "Source link"
                ),
                "Title": st.column_config.TextColumn(
                    "Title",
                    width="large"
                )
            }
        )


# ==========================================
# DATA EXPLORER
# ==========================================

with tab2:

    st.subheader("Collected records")

    if df.empty:

        st.info("No data matches the current filters.")

    else:

        st.caption(
            f"Showing {len(df):,} records. "
            "Maximum query result: 10,000 records."
        )

        st.dataframe(
            df,
            width='stretch',
            hide_index=True,
            column_config={
                "URL": st.column_config.LinkColumn(
                    "Source link"
                ),
                "Content": st.column_config.TextColumn(
                    "Content",
                    width="large"
                ),
                "Title": st.column_config.TextColumn(
                    "Title",
                    width="large"
                ),
                "Trend Score": st.column_config.NumberColumn(
                    "Trend Score",
                    format="%.2f"
                )
            }
        )

        # ----------------------------------
        # CSV EXPORT
        # ----------------------------------

        csv_data = df.to_csv(
            index=False
        ).encode("utf-8-sig")

        st.download_button(
            "Download CSV",
            data=csv_data,
            file_name="internet_trends.csv",
            mime="text/csv"
        )

        # ----------------------------------
        # EXCEL EXPORT
        # ----------------------------------

        buffer = io.BytesIO()

        with pd.ExcelWriter(
            buffer,
            engine="openpyxl"
        ) as writer:

            df.to_excel(
                writer,
                index=False,
                sheet_name="Internet Trends"
            )

        st.download_button(
            "Download Excel",
            data=buffer.getvalue(),
            file_name="internet_trends.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            )
        )


# ==========================================
# COLLECTOR STATUS
# ==========================================

with tab3:

    st.subheader("Collection overview")

    if df.empty:

        st.info("No collected records in the selected period.")

    else:

        # ----------------------------------
        # SOURCE SUMMARY
        # ----------------------------------

        source_summary = (
            df.groupby("Source")
            .agg(
                Records=("ID", "count"),
                Latest_Collection=("Collected", "max"),
                Regions=("Region", "nunique")
            )
            .reset_index()
            .sort_values("Records", ascending=False)
        )

        source_summary = source_summary.rename(
            columns={
                "Latest_Collection": "Latest collection",
                "Regions": "Regions covered"
            }
        )

        st.markdown("### Source summary")

        st.dataframe(
            source_summary,
            width='stretch',
            hide_index=True
        )

        # ----------------------------------
        # REGION SUMMARY
        # ----------------------------------

        st.markdown("### Regional coverage")

        region_summary = (
            df.groupby("Region", dropna=False)
            .agg(
                Records=("ID", "count"),
                Latest_Collection=("Collected", "max")
            )
            .reset_index()
            .rename(
                columns={
                    "Latest_Collection": "Latest collection"
                }
            )
            .sort_values("Records", ascending=False)
        )

        st.dataframe(
            region_summary,
            width='stretch',
            hide_index=True
        )

        st.caption(
            "This tab summarizes records in the selected period. "
            "It does not yet track individual collector executions."
        )


# ==========================================
# FOOTER
# ==========================================

st.divider()

st.caption(
    "Internet Trends Intelligence | "
    "MySQL Database | "
    "Current collector: Suara Kalbar"
)
