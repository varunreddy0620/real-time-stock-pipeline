"""Streamlit dashboard for live OHLCV, indicators, and pipeline health."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from sqlalchemy import create_engine, text

from src.config import get_settings
from src.processing.cleaner import latest_contiguous_segment
from src.processing.indicators import enrich
from src.processing.signals import sma_crossover
from src.utils.health_check import overall_health
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

st.set_page_config(
    page_title="Pulse Pipeline · Live Market Lab",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource
def engine():
    return create_engine(get_settings().postgres_dsn, pool_pre_ping=True)


def load_bars(ticker: str, limit: int = 400) -> pd.DataFrame:
    query = text(
        """
        SELECT timestamp, ticker, open, high, low, close, volume, source
        FROM raw_ohlcv
        WHERE ticker = :ticker
        ORDER BY timestamp DESC
        LIMIT :limit
        """
    )
    try:
        with engine().connect() as conn:
            frame = pd.read_sql(query, conn, params={"ticker": ticker, "limit": limit})
    except Exception as exc:
        logger.warning("Unable to load bars from PostgreSQL", extra={"error": str(exc)})
        frame = pd.DataFrame()
    if frame.empty:
        # Fall back to the sample CSV, but only ever return rows that
        # genuinely belong to the requested ticker. Never substitute a
        # different ticker's data silently under this ticker's name.
        sample = pd.read_csv("data/sample/ohlcv_sample.csv", parse_dates=["timestamp"])
        frame = sample[sample["ticker"] == ticker].copy()
        frame["source"] = "sample"
        frame.attrs["source"] = "sample"
    else:
        frame.attrs["source"] = "postgres"
    return frame.sort_values("timestamp")


def analyze_trend(frame: pd.DataFrame) -> dict[str, str | float]:
    """Summarize price direction, momentum, and recent trading levels."""
    last = frame.iloc[-1]
    recent = frame.tail(min(20, len(frame)))
    support = float(recent["low"].min())
    resistance = float(recent["high"].max())

    sma20 = last.get("sma_20")
    sma50 = last.get("sma_50")
    if pd.notna(sma20) and pd.notna(sma50):
        if last["close"] > sma20 > sma50:
            direction = "Bullish"
            explanation = "Price is above SMA 20, and SMA 20 is above SMA 50."
        elif last["close"] < sma20 < sma50:
            direction = "Bearish"
            explanation = "Price is below SMA 20, and SMA 20 is below SMA 50."
        else:
            direction = "Mixed"
            explanation = "Price and moving averages are not aligned in one direction."
    else:
        direction = "Warming up"
        explanation = "More bars are needed to calculate both moving averages."

    rsi_value = last.get("rsi_14")
    if pd.isna(rsi_value):
        momentum = "Warming up"
    elif rsi_value >= 70:
        momentum = "Overbought"
    elif rsi_value <= 30:
        momentum = "Oversold"
    elif rsi_value >= 55:
        momentum = "Positive"
    elif rsi_value <= 45:
        momentum = "Negative"
    else:
        momentum = "Neutral"

    return {
        "direction": direction,
        "explanation": explanation,
        "momentum": momentum,
        "support": support,
        "resistance": resistance,
    }


def candlestick(
    frame: pd.DataFrame,
    ticker: str,
    chart_type: str = "Candlestick",
    overlays: tuple[str, ...] = ("SMA 20", "SMA 50"),
) -> go.Figure:
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.72, 0.28],
        vertical_spacing=0.04,
        subplot_titles=(f"{ticker} · OHLCV + SMA", "Volume"),
    )
    if chart_type == "Line":
        fig.add_trace(
            go.Scatter(
                x=frame["timestamp"],
                y=frame["close"],
                name="Close price",
                line=dict(color="#3ee0b4", width=2),
            ),
            row=1,
            col=1,
        )
    else:
        fig.add_trace(
            go.Candlestick(
                x=frame["timestamp"],
                open=frame["open"],
                high=frame["high"],
                low=frame["low"],
                close=frame["close"],
                name="OHLC",
                increasing_line_color="#3ee0b4",
                decreasing_line_color="#ff6b8a",
            ),
            row=1,
            col=1,
        )
    if "SMA 20" in overlays and "sma_20" in frame.columns:
        fig.add_trace(
            go.Scatter(
                x=frame["timestamp"],
                y=frame["sma_20"],
                name="SMA 20",
                line=dict(color="#7dd3fc", width=1.6),
            ),
            row=1,
            col=1,
        )
    if "SMA 50" in overlays and "sma_50" in frame.columns:
        fig.add_trace(
            go.Scatter(
                x=frame["timestamp"],
                y=frame["sma_50"],
                name="SMA 50",
                line=dict(color="#fbbf24", width=1.6),
            ),
            row=1,
            col=1,
        )
    if "Bollinger Bands" in overlays and "bb_upper" in frame.columns:
        fig.add_trace(
            go.Scatter(
                x=frame["timestamp"],
                y=frame["bb_upper"],
                name="Bollinger upper",
                line=dict(color="#a78bfa", width=1, dash="dot"),
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=frame["timestamp"],
                y=frame["bb_lower"],
                name="Bollinger lower",
                line=dict(color="#a78bfa", width=1, dash="dot"),
                fill="tonexty",
                fillcolor="rgba(167, 139, 250, 0.08)",
            ),
            row=1,
            col=1,
        )
    if "Support / resistance" in overlays:
        recent = frame.tail(min(20, len(frame)))
        fig.add_hline(
            y=float(recent["low"].min()),
            line_dash="dash",
            line_color="#22c55e",
            annotation_text="Support",
            row=1,
            col=1,
        )
        fig.add_hline(
            y=float(recent["high"].max()),
            line_dash="dash",
            line_color="#f97316",
            annotation_text="Resistance",
            row=1,
            col=1,
        )
    fig.add_trace(
        go.Bar(
            x=frame["timestamp"],
            y=frame["volume"],
            name="Volume",
            marker_color="rgba(125, 211, 252, 0.45)",
        ),
        row=2,
        col=1,
    )
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0b1220",
        plot_bgcolor="#0b1220",
        height=720,
        margin=dict(l=16, r=16, t=48, b=16),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        xaxis_rangeslider_visible=False,
        font=dict(family="IBM Plex Sans, sans-serif"),
    )
    return fig


@st.fragment(run_every="10s")
def render_live_analysis(
    ticker: str,
    limit: int,
    chart_type: str,
    overlays: tuple[str, ...],
) -> None:
    """Refresh the data-dependent dashboard region every ten seconds."""
    settings = get_settings()
    bars = load_bars(ticker, limit=limit)
    if bars.empty:
        st.warning(
            f"No data available yet for {ticker}. Add rows to "
            f"data/sample/ohlcv_sample.csv or wait for the live pipeline to publish some."
        )
        return
    if bars.attrs.get("source") == "sample":
        st.info("Showing bundled sample data while live database data is unavailable.")
    bars = latest_contiguous_segment(bars, settings.indicator_max_gap_seconds)
    bars = enrich(bars)
    bars = sma_crossover(bars)

    last = bars.iloc[-1]
    source_label = {
        "live": "Live market data",
        "sample": "Bundled sample",
        "local": "Imported local dataset",
        "unknown": "Legacy/unknown",
    }.get(str(last.get("source", "unknown")), "Unknown")
    st.caption(
        f"Current data source: **{source_label}** · Auto-refreshes every 10 seconds"
    )
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Close", f"{last['close']:.2f}")
    k2.metric("RSI 14", f"{last['rsi_14']:.1f}" if pd.notna(last["rsi_14"]) else "—")
    k3.metric(
        "SMA 20",
        f"{last['sma_20']:.2f}" if pd.notna(last["sma_20"]) else "warming up",
    )
    cross = int(last["sma_cross"]) if pd.notna(last["sma_cross"]) else 0
    k4.metric("SMA cross", {1: "BULLISH", -1: "BEARISH"}.get(cross, "none"))

    trend = analyze_trend(bars)
    st.subheader("Trend analysis")
    t1, t2, t3, t4 = st.columns(4)
    t1.metric("Trend", trend["direction"])
    t2.metric("Momentum", trend["momentum"])
    t3.metric("Support", f"{trend['support']:.2f}")
    t4.metric("Resistance", f"{trend['resistance']:.2f}")
    st.caption(str(trend["explanation"]))
    with st.expander("How to read these lines"):
        st.markdown(
            """
            - **SMA 20** follows the shorter-term average price; **SMA 50** shows the broader trend.
            - **Bollinger Bands** show a typical volatility range around the 20-bar average.
            - **Support** is the recent low area; **resistance** is the recent high area.
            - These indicators describe historical price behavior and are not financial advice.
            """
        )

    st.plotly_chart(
        candlestick(bars, ticker, chart_type, overlays),
        use_container_width=True,
    )
    st.subheader("Latest bars")
    st.dataframe(bars.tail(20), use_container_width=True, hide_index=True)


def main() -> None:
    settings = get_settings()
    st.markdown(
        """
        <style>
        .stApp { background: radial-gradient(1200px 600px at 10% -10%, #163154 0%, #070b14 45%); }
        h1 { letter-spacing: -0.03em; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title("Pulse Pipeline")
    st.caption("Educational real-time stock market data pipeline · Redis Streams · dual storage · Streamlit")

    health = overall_health()
    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("Pipeline", health["status"].upper())
    redis_ok = next(c for c in health["checks"] if c["service"] == "redis")["ok"]
    pg_ok = next(c for c in health["checks"] if c["service"] == "postgres")["ok"]
    minio_ok = next(c for c in health["checks"] if c["service"] == "minio")["ok"]
    col_b.metric("Redis", "healthy" if redis_ok else "offline")
    col_c.metric("PostgreSQL", "healthy" if pg_ok else "sample mode")
    col_d.metric("MinIO", "healthy" if minio_ok else "offline")

    ticker_options = settings.ticker_list
    default_ticker = settings.dashboard_default_ticker.upper()

    try:
        default_index = ticker_options.index(default_ticker)
    except ValueError:
        default_index = 0

    with st.sidebar:
        st.header("Controls")
        ticker = st.selectbox(
            "Ticker",
            ticker_options,
            index=default_index,
        )
        limit = st.slider("Bars", 50, 500, 200)
        chart_type = st.radio("Chart style", ["Candlestick", "Line"], horizontal=True)
        overlays = st.multiselect(
            "Analysis lines",
            ["SMA 20", "SMA 50", "Bollinger Bands", "Support / resistance"],
            default=["SMA 20", "SMA 50", "Support / resistance"],
        )
        st.markdown("MinIO console: [localhost:9001](http://localhost:9001)")
        st.caption("Administrator credentials are configured in `.env`.")

    render_live_analysis(ticker, limit, chart_type, tuple(overlays))


if __name__ == "__main__":
    main()
