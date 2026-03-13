from __future__ import annotations

import io
import math
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from typing import Iterable

import numpy as np
import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
from pypdf import PdfReader
import plotly.graph_objects as go
import plotly.io as pio


MF_API_BASE = "https://api.mfapi.in"
HTTP_TIMEOUT_SECONDS = 8
BENCHMARK_OPTIONS = {
    "Nifty 50": "^NSEI",
    "Sensex": "^BSESN",
    "Nifty BeES ETF": "NIFTYBEES.NS",
    "Nifty 500": "^CRSLDX",
}
TENURE_OPTIONS = {
    "1 Year": 252,
    "3 Years": 252 * 3,
    "5 Years": 252 * 5,
    "Max": None,
}
DEMO_HOLDINGS = [
    {
        "amc": "Axis Mutual Fund",
        "scheme": "Axis Bluechip Fund Direct Growth",
        "folio": "12345678",
        "units": 425.761,
        "average_cost_per_unit": 42.18,
        "invested_amount": 17956.60,
    },
    {
        "amc": "HDFC Mutual Fund",
        "scheme": "HDFC Balanced Advantage Fund Direct Growth",
        "folio": "28374655",
        "units": 382.191,
        "average_cost_per_unit": 52.72,
        "invested_amount": 20146.71,
    },
    {
        "amc": "ICICI Prudential Mutual Fund",
        "scheme": "ICICI Prudential Technology Fund Direct Growth",
        "folio": "92837465",
        "units": 218.924,
        "average_cost_per_unit": 81.31,
        "invested_amount": 17800.11,
    },
]


@dataclass
class ParsedCas:
    holdings: pd.DataFrame
    raw_lines: list[str]
    no_folios_found: bool = False


def inject_app_styles() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background: linear-gradient(180deg, #f2f2f2 0%, #fafafa 100%);
            color: #111827;
        }
        .main .block-container {
            padding-top: 2rem;
        }
        h1, h2, h3, h4, h5, h6, p, li, label, div, span {
            color: #111827;
        }
        .app-hero {
            display: grid;
            grid-template-columns: 1.5fr 0.9fr;
            gap: 1rem;
            padding: 1.25rem 0 1.5rem 0;
        }
        .app-hero h1 {
            font-size: 2.25rem;
            line-height: 1.05;
            margin: 0.25rem 0 0.75rem 0;
        }
        .app-hero p {
            font-size: 1rem;
            color: #1f2937;
            max-width: 60rem;
        }
        .eyebrow {
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.14em;
            color: #4b5563;
            font-weight: 700;
        }
        .hero-note, .upload-panel {
            background: #ffffff;
            border: 1px solid #d1d5db;
            border-radius: 18px;
            padding: 1rem 1.1rem;
            box-shadow: 0 12px 28px rgba(17, 24, 39, 0.06);
        }
        .hero-note ul {
            margin-bottom: 0;
            padding-left: 1rem;
        }
        [data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #d1d5db;
            border-radius: 16px;
            padding: 0.75rem 1rem;
            box-shadow: 0 10px 24px rgba(17, 24, 39, 0.05);
        }
        [data-testid="stMetricLabel"] *,
        [data-testid="stMetricValue"] * {
            color: #111827 !important;
        }
        [data-testid="stMetricValue"] {
            font-size: 1.1rem !important;
            line-height: 1.2 !important;
        }
        .stButton > button,
        .stDownloadButton > button {
            background: linear-gradient(135deg, #111111, #2f2f2f);
            color: #ffffff;
            border: none;
            border-radius: 12px;
            font-weight: 700;
        }
        .stButton > button:hover,
        .stDownloadButton > button:hover {
            background: linear-gradient(135deg, #222222, #555555);
            color: #ffffff;
        }
        .stTextInput input,
        .stNumberInput input,
        .stDateInput input,
        .stTextArea textarea,
        .stFileUploader section {
            background: #ffffff !important;
            color: #111827 !important;
            border: 1px solid #9ca3af !important;
            border-radius: 12px !important;
        }
        .stSelectbox div[data-baseweb="select"] > div,
        .stMultiSelect div[data-baseweb="select"] > div {
            background: #ffffff !important;
            color: #111827 !important;
            border: 1px solid #9ca3af !important;
            border-radius: 12px !important;
        }
        .stSelectbox div[data-baseweb="select"] input,
        .stMultiSelect div[data-baseweb="select"] input,
        .stSelectbox div[data-baseweb="select"] span,
        .stMultiSelect div[data-baseweb="select"] span {
            color: #111827 !important;
            -webkit-text-fill-color: #111827 !important;
        }
        .stTextInput label,
        .stNumberInput label,
        .stSelectbox label,
        .stMultiSelect label,
        .stDateInput label,
        .stFileUploader label,
        .stTextArea label,
        .stToggle label {
            color: #111827 !important;
            font-weight: 600;
        }
        .stTextInput [disabled],
        .stNumberInput [disabled],
        .stSelectbox [aria-disabled="true"],
        .stTextInput input:disabled,
        .stNumberInput input:disabled {
            background: #f3f4f6 !important;
            color: #111827 !important;
            -webkit-text-fill-color: #111827 !important;
            opacity: 1 !important;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 0.5rem;
        }
        .stTabs [data-baseweb="tab"] {
            background: #ffffff;
            border: 1px solid #d1d5db;
            border-radius: 12px 12px 0 0;
            color: #111827;
        }
        .stTabs [aria-selected="true"] {
            color: #111827 !important;
            border-bottom: 2px solid #111827 !important;
        }
        [data-testid="stDataFrame"],
        [data-testid="stTable"] {
            background: #ffffff;
            border: 1px solid #d1d5db;
            border-radius: 16px;
            padding: 0.25rem;
        }
        [data-testid="stFileUploaderDropzone"] {
            background: #ffffff !important;
            border: 1px solid #9ca3af !important;
            color: #111827 !important;
        }
        [data-testid="stFileUploaderDropzone"] * {
            color: #111827 !important;
            fill: #111827 !important;
        }
        [data-testid="stFileUploaderFile"] {
            background: #ffffff !important;
            border: 1px solid #d1d5db !important;
        }
        [data-testid="stFileUploaderFile"] * {
            color: #111827 !important;
            fill: #111827 !important;
        }
        [data-testid="stFileUploaderFileName"] {
            color: #111827 !important;
            -webkit-text-fill-color: #111827 !important;
        }
        [data-testid="stBaseButton-secondary"] {
            background: #ffffff !important;
            color: #111827 !important;
            border: 1px solid #9ca3af !important;
        }
        [data-testid="stBaseButton-secondary"] * {
            color: #111827 !important;
            fill: #111827 !important;
        }
        [data-baseweb="popover"] [role="listbox"],
        [data-baseweb="popover"] [role="option"],
        [data-baseweb="menu"],
        [role="menu"],
        [role="menuitem"] {
            background: #111111 !important;
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
        }
        .stCheckbox label,
        .stCheckbox span,
        .stToggle span {
            color: #111827 !important;
        }
        .st-emotion-cache-16txtl3, .st-emotion-cache-1f3w014 {
            color: #111827 !important;
        }
        .stAlert {
            color: #111827;
            background: #ffffff !important;
            border: 1px solid #d1d5db !important;
        }
        .stMarkdown, .stCaption {
            color: #111827 !important;
        }
        code, pre {
            color: #111827 !important;
        }
        .workflow-step {
            background: linear-gradient(135deg, #5b5b5b, #7a7a7a);
            border: 1px solid #6b7280;
            border-radius: 14px;
            padding: 0.9rem 1rem;
            font-weight: 600;
            min-height: 64px;
            display: flex;
            align-items: center;
            color: #ffffff;
            box-shadow: 0 8px 18px rgba(17, 24, 39, 0.08);
        }
        .stat-chip {
            border-radius: 14px;
            padding: 0.85rem 1rem;
            min-height: 74px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            gap: 0.25rem;
            border: 1px solid #d1d5db;
        }
        .stat-chip.dark {
            background: #111111;
            color: #ffffff;
            border-color: #111111;
        }
        .stat-chip.light {
            background: #ffffff;
            color: #111827;
        }
        .stat-chip.dark .label,
        .stat-chip.dark .value {
            color: #ffffff !important;
        }
        .stat-chip.light .label,
        .stat-chip.light .value {
            color: #111827 !important;
        }
        .stat-chip .label {
            font-size: 0.82rem;
            font-weight: 600;
            opacity: 0.9;
        }
        .stat-chip .value {
            font-size: 1rem;
            font-weight: 700;
        }
        .vega-embed, .js-plotly-plot {
            background: #ffffff;
            border: 1px solid #d1d5db;
            border-radius: 16px;
            padding: 0.5rem;
        }
        .js-plotly-plot .plotly .modebar {
            background: rgba(17, 17, 17, 0.88) !important;
        }
        .js-plotly-plot .plotly .modebar-btn path {
            fill: #ffffff !important;
        }
        @media (max-width: 900px) {
            .app-hero {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title="CAS Mutual Fund Analyzer", layout="wide")
    inject_app_styles()

    st.markdown(
        """
        <div class="app-hero">
            <div>
                <div class="eyebrow">Mutual Fund Portfolio Analyzer</div>
                <h1>Upload your CAS and review folios, valuations, returns, and risk ratios in one place.</h1>
                <p>
                    Import a consolidated account statement PDF directly in the app, structure the holdings automatically,
                    and compute portfolio-weighted analytics such as Sharpe ratio, Alpha, Beta, Treynor's Ratio,
                    Information Ratio, standard deviation, and drawdown.
                </p>
            </div>
            <div class="hero-note">
                <strong>What this app does</strong>
                <ul>
                    <li>Reads CAS PDFs inside the app UI</li>
                    <li>Extracts folios and scheme-level holdings</li>
                    <li>Shows portfolio summary and scheme metrics</li>
                    <li>Uses benchmark-aware risk analytics</li>
                </ul>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    control_col, upload_col = st.columns([0.9, 1.1], gap="large")

    with control_col:
        st.markdown("### Analysis Controls")
        benchmark_label = st.selectbox("Benchmark", list(BENCHMARK_OPTIONS.keys()))
        risk_free_rate = st.number_input("Risk-free rate (%)", min_value=0.0, max_value=20.0, value=7.0, step=0.1)
        show_zero_holdings = st.toggle("Include zero-balance folios", value=False)
        use_demo = st.button("Load Demo Portfolio", use_container_width=True)

    with upload_col:
        st.markdown("### Upload CAS")
        st.markdown(
            """
            <div class="upload-panel">
                <strong>Step 1</strong>
                <p>Upload a detailed or summary CAS PDF here. The app will extract folios and holdings directly inside the interface.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        uploaded_file = st.file_uploader("Choose CAS PDF", type=["pdf"], label_visibility="collapsed")

    st.markdown("### Workflow")
    workflow_cols = st.columns(3)
    workflow_cols[0].markdown('<div class="workflow-step">1. Upload CAS</div>', unsafe_allow_html=True)
    workflow_cols[1].markdown('<div class="workflow-step">2. Review extracted folios</div>', unsafe_allow_html=True)
    workflow_cols[2].markdown('<div class="workflow-step">3. Analyze returns and risk ratios</div>', unsafe_allow_html=True)

    parsed = None
    if use_demo:
        parsed = ParsedCas(holdings=pd.DataFrame(DEMO_HOLDINGS), raw_lines=[])
    elif uploaded_file is not None:
        parsed = parse_cas_pdf(uploaded_file.getvalue())

    if parsed is None:
        st.info("Upload a CAS PDF or use demo holdings to begin.")
        return

    if parsed.no_folios_found:
        st.warning("This CAS explicitly says 'No Folios Found'. There are no mutual fund holdings to import from this file.")
        with st.expander("Extracted CAS text preview"):
            st.code("\n".join(parsed.raw_lines[:120]))
        return

    if parsed.holdings.empty:
        st.error("The PDF was read, but no holdings could be extracted. This likely means the statement layout needs a parser refinement.")
        with st.expander("Extracted CAS text preview"):
            st.code("\n".join(parsed.raw_lines[:150]))
        return

    working_holdings = parsed.holdings.copy()
    if not show_zero_holdings and {"current_value", "units"}.issubset(working_holdings.columns):
        working_holdings = working_holdings[(working_holdings["current_value"] > 0) | (working_holdings["units"] > 0)].copy()

    portfolio_tab, holdings_tab, diagnostics_tab = st.tabs(["Portfolio Overview", "Holdings", "Diagnostics"])

    with portfolio_tab:
        metric_controls = st.columns([1.1, 1.1, 1.2], gap="medium")
        with metric_controls[0]:
            tenure_label = st.selectbox("Return / Risk Duration", list(TENURE_OPTIONS.keys()), index=2)
        with metric_controls[1]:
            st.markdown(
                f'<div class="stat-chip light"><div class="label">Benchmark Used</div><div class="value">{benchmark_label}</div></div>',
                unsafe_allow_html=True,
            )
        with metric_controls[2]:
            st.markdown(
                f'<div class="stat-chip light"><div class="label">Risk-Free Rate Applied</div><div class="value">{risk_free_rate:.1f}%</div></div>',
                unsafe_allow_html=True,
            )

        benchmark_symbol = BENCHMARK_OPTIONS[benchmark_label]
        analytics = analyze_portfolio(working_holdings, benchmark_symbol, TENURE_OPTIONS[tenure_label], risk_free_rate / 100.0)

        if analytics["scheme_metrics"].empty:
            st.info("Historical NAV or benchmark data could not be loaded for the imported schemes. Holdings and valuation summary are still shown, but risk ratios may be unavailable.")

        summary_cols = st.columns(5)
        summary_cols[0].metric("Folios / Rows", f"{len(working_holdings)}")
        summary_cols[1].metric("Total Value", format_inr_whole(analytics["total_value"]))
        summary_cols[2].metric("Total Cost", format_inr_whole(analytics["total_cost"]))
        summary_cols[3].metric("Unrealized Gain", format_inr_whole(analytics["total_gain"]))
        summary_cols[4].metric("Portfolio CAGR", format_pct(analytics["portfolio_metrics"]["cagr"]))

        chart_df = analytics["growth_chart"].copy()
        if not chart_df.empty:
            st.subheader("Growth of Rs 100,000")
            render_growth_chart(chart_df)

        col1, col2 = st.columns([0.9, 1.1], gap="large")
        with col1:
            st.subheader("Portfolio Metrics")
            st.dataframe(metrics_to_frame(analytics["portfolio_metrics"]), use_container_width=True, hide_index=True)

        with col2:
            st.subheader("Scheme Metrics")
            st.dataframe(analytics["scheme_metrics"], use_container_width=True, hide_index=True)

    with holdings_tab:
        benchmark_symbol = BENCHMARK_OPTIONS[benchmark_label]
        analytics = analyze_portfolio(working_holdings, benchmark_symbol, TENURE_OPTIONS[tenure_label], risk_free_rate / 100.0)
        st.subheader("Extracted Holdings")
        st.dataframe(format_holdings_table(analytics["holdings"]), use_container_width=True, hide_index=True)

    with diagnostics_tab:
        with st.expander("Notes and assumptions", expanded=True):
            st.markdown(
                """
                - CAS parsing currently targets text-based detailed and summary statements and not scanned/image-only PDFs.
                - Scheme matching is fuzzy against the AMFI scheme list and may need manual correction for near-duplicate names.
                - Benchmark-sensitive ratios depend on Yahoo Finance history being available for the selected benchmark.
                - Zero-balance or legacy folios can be hidden with the toggle in Analysis Controls.
                """
            )
        with st.expander("Extracted CAS text preview"):
            st.code("\n".join(parsed.raw_lines[:180]))


def parse_cas_pdf(pdf_bytes: bytes) -> ParsedCas:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    raw_text = "\n".join((page.extract_text() or "") for page in reader.pages)
    raw_lines = [normalize_spaces(line) for line in raw_text.splitlines() if normalize_spaces(line)]

    if "No Folios Found" in raw_text:
        return ParsedCas(holdings=pd.DataFrame(), raw_lines=raw_lines, no_folios_found=True)

    if "Consolidated Account Summary" in raw_text and "Scheme DetailsFolio No. NAV" in raw_text:
        holdings = extract_summary_holdings(raw_lines)
    else:
        holdings = extract_holdings(raw_lines)
    return ParsedCas(holdings=holdings, raw_lines=raw_lines)


def extract_holdings(lines: list[str]) -> pd.DataFrame:
    records: list[dict] = []
    current_amc = ""
    current_scheme = ""
    current_folio = ""

    for index, line in enumerate(lines):
        if is_amc_line(line):
            current_amc = clean_text(line)
            continue

        folio_match = re.search(r"folio(?:\s*(?:no|number|#))?\s*[:\-]?\s*([A-Z0-9/\-]{4,})", line, re.I)
        if folio_match:
            current_folio = folio_match.group(1).strip()

        if is_scheme_line(line):
            current_scheme = clean_text(line)
            continue

        valuation = extract_valuation(line)
        if not valuation and index + 1 < len(lines):
            valuation = extract_valuation(f"{line} {lines[index + 1]}")

        if valuation and current_scheme:
            records.append(
                {
                    "amc": current_amc or infer_amc(current_scheme),
                    "scheme": current_scheme,
                    "folio": current_folio or "Not found",
                    **valuation,
                }
            )

    if not records:
        return pd.DataFrame()

    frame = pd.DataFrame(records)
    frame = frame.sort_values(["folio", "scheme", "current_value"], ascending=[True, True, False])
    frame = frame.drop_duplicates(subset=["folio", "scheme"], keep="first").reset_index(drop=True)
    return frame


def extract_summary_holdings(lines: list[str]) -> pd.DataFrame:
    records: list[dict] = []
    in_holdings_table = False
    scheme_parts: list[str] = []
    pending_amounts: tuple[float, float, float] | None = None

    for line in lines:
        if "Scheme DetailsFolio No. NAV" in line:
            in_holdings_table = True
            scheme_parts = []
            pending_amounts = None
            continue

        if not in_holdings_table:
            continue

        if is_summary_footer_or_header(line):
            continue

        if line.startswith("Total "):
            break

        inline_match = parse_summary_scheme_with_amounts(line)
        if inline_match:
            scheme_parts = [inline_match["scheme"]]
            pending_amounts = (
                inline_match["invested_amount"],
                inline_match["current_value"],
                inline_match["gain_loss"],
            )
            continue

        amount_match = parse_amount_line(line)
        if amount_match and scheme_parts:
            pending_amounts = amount_match
            continue

        detail_match = parse_summary_detail_line(line)
        if detail_match and scheme_parts and pending_amounts:
            invested_amount, current_value, gain_loss = pending_amounts
            scheme = normalize_spaces(" ".join(scheme_parts))
            units = detail_match["units"]
            current_nav = detail_match["nav"]
            average_cost_per_unit = invested_amount / units if units else 0.0
            records.append(
                {
                    "amc": infer_amc_from_summary_scheme(scheme),
                    "scheme": scheme,
                    "folio": detail_match["folio"],
                    "units": units,
                    "average_cost_per_unit": average_cost_per_unit,
                    "invested_amount": invested_amount,
                    "current_nav": current_nav,
                    "current_value": current_value,
                    "gain_loss": gain_loss,
                    "nav_date": detail_match["nav_date"],
                }
            )
            scheme_parts = []
            pending_amounts = None
            continue

        if not parse_summary_detail_line(line):
            scheme_parts.append(line)

    if not records:
        return pd.DataFrame()

    return pd.DataFrame(records)


def parse_summary_scheme_with_amounts(line: str) -> dict | None:
    pattern = re.compile(
        r"^(?P<scheme>.+?)\s+(?P<invested>[0-9,]+\.\d{2})\s+(?P<market>[0-9,]+\.\d{2})\s+(?P<gain>\(?[0-9,]+\.\d{2}\)?)$"
    )
    match = pattern.match(line)
    if not match:
        return None
    return {
        "scheme": clean_summary_scheme(match.group("scheme")),
        "invested_amount": parse_amount(match.group("invested")) or 0.0,
        "current_value": parse_amount(match.group("market")) or 0.0,
        "gain_loss": parse_signed_amount(match.group("gain")),
    }


def parse_amount_line(line: str) -> tuple[float, float, float] | None:
    match = re.match(r"^(?P<invested>[0-9,]+\.\d{2})\s+(?P<market>[0-9,]+\.\d{2})\s+(?P<gain>\(?[0-9,]+\.\d{2}\)?)$", line)
    if not match:
        return None
    return (
        parse_amount(match.group("invested")) or 0.0,
        parse_amount(match.group("market")) or 0.0,
        parse_signed_amount(match.group("gain")),
    )


def parse_summary_detail_line(line: str) -> dict | None:
    pattern = re.compile(
        r"^\((?P<pct>[+-]?[0-9,]+\.\d+)%\)\s*(?P<units>[0-9,]+\.\d+)\s+(?P<nav_date>\d{2}-[A-Za-z]{3}-\d{4})(?P<folio>[A-Z0-9]+)\s+(?P<nav>[0-9,]+\.\d+)$"
    )
    match = pattern.match(line)
    if not match:
        return None
    return {
        "absolute_return_pct": parse_amount(match.group("pct")) or 0.0,
        "units": parse_amount(match.group("units")) or 0.0,
        "nav_date": match.group("nav_date"),
        "folio": match.group("folio"),
        "nav": parse_amount(match.group("nav")) or 0.0,
    }


def is_summary_footer_or_header(line: str) -> bool:
    patterns = [
        r"^Consolidated Account Summary$",
        r"^\( As on Date:",
        r"^MFCentralCASSummary_",
        r"^SoA Holdings Demat Holdings$",
        r"^Invested Value$",
        r"^\(INR\)$",
        r"^Market Value$",
        r"^Gain/Loss$",
        r"^\(Absolute\)$",
        r"^Balance$",
        r"^-- No MF holdings in Demat --",
        r"^\#IDCW",
        r"^\*SoA",
        r"^Please note:",
        r"^For any queries",
    ]
    return any(re.search(pattern, line) for pattern in patterns)


def clean_summary_scheme(value: str) -> str:
    return normalize_spaces(value.rstrip("-").strip())


def extract_valuation(line: str) -> dict | None:
    numbers = [
        parse_amount(match)
        for match in re.findall(r"(?:Rs\.?|INR)?\s*([0-9,]+\.\d{2,4}|[0-9,]+)", line, flags=re.I)
    ]
    numbers = [value for value in numbers if value is not None]
    if len(numbers) < 3:
        return None

    units = numbers[0]
    nav = numbers[-2]
    current_value = numbers[-1]
    if units <= 0 or nav <= 0 or current_value <= 0:
        return None

    average_cost_per_unit = current_value / units
    invested_amount = current_value
    if len(numbers) >= 4:
        candidate = numbers[-3]
        if 0 < candidate <= 1000:
            average_cost_per_unit = candidate
            invested_amount = average_cost_per_unit * units
        elif candidate < current_value * 1.5:
            invested_amount = candidate
            average_cost_per_unit = invested_amount / units

    return {
        "units": float(units),
        "average_cost_per_unit": float(average_cost_per_unit),
        "invested_amount": float(invested_amount),
        "current_nav": float(nav),
        "current_value": float(current_value),
    }


def analyze_portfolio(holdings: pd.DataFrame, benchmark_symbol: str, trading_days: int | None, risk_free_rate: float) -> dict:
    enriched = enrich_holdings(holdings)
    benchmark_series = fetch_benchmark_series(benchmark_symbol)

    if trading_days is not None:
        benchmark_series = benchmark_series.tail(trading_days)

    total_value = float(enriched["current_value"].sum())
    total_cost = float(enriched["invested_amount"].sum())
    enriched["weight"] = np.where(total_value > 0, enriched["current_value"] / total_value, 0.0)

    scheme_metrics = []
    indexed_series = []
    for _, row in enriched.iterrows():
        nav_history = row["nav_history"]
        if trading_days is not None:
            nav_history = nav_history.tail(trading_days)
        if nav_history.empty:
            continue
        aligned_fund, aligned_benchmark = align_series(nav_history, benchmark_series)
        metrics = compute_risk_metrics(aligned_fund, aligned_benchmark, risk_free_rate)
        scheme_metrics.append(
            {
                "Scheme": row["scheme"],
                "CAGR": format_pct(metrics["cagr"]),
                "Std Dev": format_pct(metrics["standard_deviation"]),
                "Sharpe": format_num(metrics["sharpe"]),
                "Alpha": format_pct(metrics["alpha"]),
                "Beta": format_num(metrics["beta"]),
                "Treynor": format_num(metrics["treynor"]),
                "Info Ratio": format_num(metrics["information_ratio"]),
                "Max Drawdown": format_pct(metrics["max_drawdown"]),
            }
        )
        indexed_series.append(rebase_series(aligned_fund, row["weight"]))

    portfolio_series = combine_weighted_series(indexed_series)
    aligned_portfolio, aligned_benchmark = align_series(portfolio_series, benchmark_series)
    portfolio_metrics = compute_risk_metrics(aligned_portfolio, aligned_benchmark, risk_free_rate)

    growth_chart = pd.DataFrame()
    if not aligned_portfolio.empty:
        growth_chart = pd.DataFrame(
            {
                "date": aligned_portfolio.index,
                "Portfolio": rebase_series(aligned_portfolio, 100000.0)["value"].values,
            }
        )
        if not aligned_benchmark.empty:
            growth_chart["Benchmark"] = rebase_series(aligned_benchmark, 100000.0)["value"].values

    holdings_display = enriched.drop(columns=["nav_history"]).copy()
    return {
        "holdings": holdings_display,
        "total_value": total_value,
        "total_cost": total_cost,
        "total_gain": total_value - total_cost,
        "portfolio_metrics": portfolio_metrics,
        "scheme_metrics": pd.DataFrame(scheme_metrics),
        "growth_chart": growth_chart,
    }


@st.cache_data(show_spinner=False, ttl=24 * 60 * 60)
def fetch_scheme_catalog() -> pd.DataFrame:
    try:
        response = requests.get(f"{MF_API_BASE}/mf", timeout=HTTP_TIMEOUT_SECONDS)
        response.raise_for_status()
        frame = pd.DataFrame(response.json())
        if not frame.empty:
            frame["normalized_name"] = frame["schemeName"].map(normalize_scheme_name)
        return frame
    except requests.RequestException:
        return pd.DataFrame(columns=["schemeCode", "schemeName", "normalized_name"])


def enrich_holdings(holdings: pd.DataFrame) -> pd.DataFrame:
    catalog = fetch_scheme_catalog()
    source_rows = holdings.to_dict(orient="records")
    matches = []
    codes_to_fetch: set[str] = set()

    for row in source_rows:
        match = match_scheme(row["scheme"], catalog) if not catalog.empty else None
        matches.append(match)
        should_fetch_history = match is not None and float(row.get("units", 0.0)) > 0 and float(row.get("current_value", 0.0)) > 0
        if should_fetch_history:
            codes_to_fetch.add(str(match["schemeCode"]))

    nav_cache: dict[str, pd.DataFrame] = {}
    if codes_to_fetch:
        with ThreadPoolExecutor(max_workers=min(8, len(codes_to_fetch))) as executor:
            future_map = {executor.submit(fetch_nav_history, code): code for code in codes_to_fetch}
            for future in as_completed(future_map):
                code = future_map[future]
                try:
                    nav_cache[code] = future.result()
                except Exception:
                    nav_cache[code] = pd.DataFrame()

    enriched_rows = []
    for row, match in zip(source_rows, matches):
        should_fetch_history = match is not None and float(row.get("units", 0.0)) > 0 and float(row.get("current_value", 0.0)) > 0
        nav_history = nav_cache.get(str(match["schemeCode"]), pd.DataFrame()) if should_fetch_history else pd.DataFrame()
        current_nav = row.get("current_nav", 0.0)
        if not nav_history.empty:
            current_nav = float(nav_history["nav"].iloc[-1])
        current_value = current_nav * float(row["units"]) if current_nav else float(row.get("current_value", 0.0))
        enriched_rows.append(
            {
                **row,
                "scheme_code": str(match["schemeCode"]) if match is not None else "Unmatched",
                "matched_scheme_name": match["schemeName"] if match is not None else "Unmatched",
                "current_nav": current_nav,
                "current_value": current_value,
                "nav_history": nav_history,
            }
        )
    return pd.DataFrame(enriched_rows)


@st.cache_data(show_spinner=False, ttl=24 * 60 * 60)
def fetch_nav_history(scheme_code: str) -> pd.DataFrame:
    try:
        response = requests.get(f"{MF_API_BASE}/mf/{scheme_code}", timeout=HTTP_TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException:
        return pd.DataFrame(columns=["nav"])
    records = []
    for item in payload.get("data", []):
        try:
            records.append(
                {
                    "date": datetime.strptime(item["date"], "%d-%m-%Y").date(),
                    "nav": float(item["nav"]),
                }
            )
        except (ValueError, TypeError):
            continue
    if not records:
        return pd.DataFrame(columns=["nav"])
    frame = pd.DataFrame(records).dropna().sort_values("date")
    return frame.set_index("date")


@st.cache_data(show_spinner=False, ttl=12 * 60 * 60)
def fetch_benchmark_series(symbol: str) -> pd.DataFrame:
    try:
        history = yf.download(
            symbol,
            period="10y",
            interval="1d",
            auto_adjust=True,
            progress=False,
            timeout=HTTP_TIMEOUT_SECONDS,
            threads=False,
        )
    except Exception:
        return pd.DataFrame(columns=["value"])
    if history.empty:
        return pd.DataFrame(columns=["value"])
    if isinstance(history.columns, pd.MultiIndex):
        history.columns = [col[0] if isinstance(col, tuple) else col for col in history.columns]
    series = history[["Close"]].rename(columns={"Close": "value"}).dropna()
    series.index = pd.to_datetime(series.index).date
    return series


def match_scheme(target_scheme: str, catalog: pd.DataFrame) -> pd.Series | None:
    normalized_target = normalize_scheme_name(target_scheme)
    target_tokens = normalized_target.split()
    candidate_catalog = catalog

    if target_tokens:
        first_token = target_tokens[0]
        candidate_catalog = candidate_catalog[candidate_catalog["normalized_name"].str.contains(rf"\b{re.escape(first_token)}\b", regex=True, na=False)]
    if len(target_tokens) > 1:
        second_token = target_tokens[1]
        narrowed = candidate_catalog[candidate_catalog["normalized_name"].str.contains(rf"\b{re.escape(second_token)}\b", regex=True, na=False)]
        if not narrowed.empty:
            candidate_catalog = narrowed
    if candidate_catalog.empty:
        candidate_catalog = catalog

    best_row = None
    best_score = float("-inf")
    for _, row in candidate_catalog.iterrows():
        score = score_scheme_match(normalized_target, row["normalized_name"])
        if score > best_score:
            best_score = score
            best_row = row
    return best_row if best_score >= 0.45 else None


def compute_risk_metrics(asset_series: pd.DataFrame, benchmark_series: pd.DataFrame, risk_free_rate: float) -> dict:
    if asset_series.empty or len(asset_series) < 30:
        return empty_metrics()

    asset_returns = asset_series["value"].pct_change().dropna()
    cagr = annualized_return(asset_series["value"])
    standard_deviation = float(asset_returns.std(ddof=1) * math.sqrt(252)) if len(asset_returns) > 1 else np.nan
    max_drawdown = calculate_max_drawdown(asset_series["value"])

    metrics = {
        "cagr": cagr,
        "standard_deviation": standard_deviation,
        "sharpe": safe_div(cagr - risk_free_rate, standard_deviation),
        "alpha": np.nan,
        "beta": np.nan,
        "treynor": np.nan,
        "information_ratio": np.nan,
        "max_drawdown": max_drawdown,
    }

    if benchmark_series.empty or len(benchmark_series) < 30:
        return metrics

    benchmark_returns = benchmark_series["value"].pct_change().dropna()
    joined = pd.concat([asset_returns.rename("asset"), benchmark_returns.rename("benchmark")], axis=1).dropna()
    if joined.empty or len(joined) < 30:
        return metrics

    beta = joined["asset"].cov(joined["benchmark"]) / joined["benchmark"].var(ddof=1)
    benchmark_cagr = annualized_from_returns(joined["benchmark"])
    tracking_diff = joined["asset"] - joined["benchmark"]
    tracking_error = float(tracking_diff.std(ddof=1) * math.sqrt(252)) if len(tracking_diff) > 1 else np.nan
    active_return = float(tracking_diff.mean() * 252)

    metrics.update(
        {
            "alpha": cagr - (risk_free_rate + beta * (benchmark_cagr - risk_free_rate)) if pd.notna(beta) else np.nan,
            "beta": beta,
            "treynor": safe_div(cagr - risk_free_rate, beta),
            "information_ratio": safe_div(active_return, tracking_error),
        }
    )
    return metrics


def combine_weighted_series(series_list: Iterable[pd.DataFrame]) -> pd.DataFrame:
    series_list = [series for series in series_list if not series.empty]
    if not series_list:
        return pd.DataFrame(columns=["value"])
    combined = pd.concat([series.rename(columns={"value": f"series_{i}"}) for i, series in enumerate(series_list)], axis=1)
    combined = combined.ffill().dropna(how="all")
    combined["value"] = combined.sum(axis=1)
    return combined[["value"]]


def rebase_series(series: pd.DataFrame, base: float) -> pd.DataFrame:
    if series.empty:
        return pd.DataFrame(columns=["value"])
    first_value = float(series["value"].iloc[0])
    rebased = series.copy()
    rebased["value"] = rebased["value"] / first_value * base
    return rebased[["value"]]


def align_series(asset_series: pd.DataFrame, benchmark_series: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    asset_series = to_value_frame(asset_series)
    benchmark_series = to_value_frame(benchmark_series)
    if benchmark_series.empty:
        return asset_series.copy(), benchmark_series.copy()
    joined = asset_series.join(benchmark_series, how="inner", lsuffix="_asset", rsuffix="_benchmark")
    if joined.empty:
        return pd.DataFrame(columns=["value"]), pd.DataFrame(columns=["value"])
    return joined[["value_asset"]].rename(columns={"value_asset": "value"}), joined[["value_benchmark"]].rename(columns={"value_benchmark": "value"})


def annualized_return(values: pd.Series) -> float:
    if values.empty or len(values) < 2:
        return np.nan
    years = max((len(values) - 1) / 252.0, 1 / 252.0)
    total_return = float(values.iloc[-1] / values.iloc[0]) - 1.0
    return (1.0 + total_return) ** (1.0 / years) - 1.0


def annualized_from_returns(returns: pd.Series) -> float:
    if returns.empty:
        return np.nan
    compounded = float((1.0 + returns).prod())
    return compounded ** (252.0 / len(returns)) - 1.0


def calculate_max_drawdown(values: pd.Series) -> float:
    running_peak = values.cummax()
    drawdown = values / running_peak - 1.0
    return float(drawdown.min())


def format_holdings_table(frame: pd.DataFrame) -> pd.DataFrame:
    display = frame.copy()
    for col in ["average_cost_per_unit", "invested_amount", "current_nav", "current_value"]:
        if col in display.columns:
            display[col] = display[col].map(format_inr)
    if "weight" in display.columns:
        display["weight"] = display["weight"].map(format_pct)
    return display.rename(
        columns={
            "amc": "AMC",
            "scheme": "Scheme",
            "folio": "Folio",
            "units": "Units",
            "average_cost_per_unit": "Avg Cost / Unit",
            "invested_amount": "Invested Amount",
            "current_nav": "Current NAV",
            "current_value": "Current Value",
            "weight": "Weight",
            "matched_scheme_name": "Matched Scheme",
            "scheme_code": "Scheme Code",
        }
    )


def metrics_to_frame(metrics: dict) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Metric": "CAGR", "Value": format_pct(metrics["cagr"])},
            {"Metric": "Annualized Standard Deviation", "Value": format_pct(metrics["standard_deviation"])},
            {"Metric": "Sharpe Ratio", "Value": format_num(metrics["sharpe"])},
            {"Metric": "Alpha", "Value": format_pct(metrics["alpha"])},
            {"Metric": "Beta", "Value": format_num(metrics["beta"])},
            {"Metric": "Treynor's Ratio", "Value": format_num(metrics["treynor"])},
            {"Metric": "Information Ratio", "Value": format_num(metrics["information_ratio"])},
            {"Metric": "Max Drawdown", "Value": format_pct(metrics["max_drawdown"])},
        ]
    )


def render_growth_chart(chart_df: pd.DataFrame) -> None:
    plot_df = chart_df.copy()
    plot_df["date"] = pd.to_datetime(plot_df["date"])
    series_columns = [col for col in plot_df.columns if col != "date"]
    if not series_columns:
        return
    color_map = {
        "Portfolio": "#38bdf8",
        "Benchmark": "#f59e0b",
    }

    fig = go.Figure()
    all_values = []

    for series_name in series_columns:
        series = plot_df[["date", series_name]].dropna()
        if series.empty:
            continue
        all_values.extend(series[series_name].tolist())
        line_color = color_map.get(series_name, "#a3a3a3")
        fig.add_trace(
            go.Scatter(
                x=series["date"],
                y=series[series_name],
                mode="lines",
                name=series_name,
                line={"color": line_color, "width": 3},
                hovertemplate="%{x|%b %d, %Y}<br>%{fullData.name}: %{y:,.2f}<extra></extra>",
            )
        )

    if not all_values:
        return

    y_min = min(all_values)
    y_max = max(all_values)
    spread = max(y_max - y_min, 1)
    y_padding = spread * 0.08
    fig.update_layout(
        height=420,
        paper_bgcolor="#0b0b0c",
        plot_bgcolor="#0b0b0c",
        margin=dict(l=90, r=40, t=40, b=80),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(color="#ffffff")),
        xaxis=dict(
            title="Month",
            color="#ffffff",
            gridcolor="rgba(255,255,255,0.08)",
            tickformat="%b %Y",
            tickangle=0,
            range=[plot_df["date"].min(), plot_df["date"].max()],
            showline=True,
            linecolor="#ffffff",
            zeroline=False,
            automargin=True,
        ),
        yaxis=dict(
            title="Value (INR)",
            color="#ffffff",
            gridcolor="rgba(255,255,255,0.08)",
            range=[y_min - y_padding, y_max + y_padding],
            showline=True,
            linecolor="#ffffff",
            zeroline=False,
            automargin=True,
            tickformat=",",
        ),
        hoverlabel=dict(bgcolor="#1f2937", font_color="#ffffff"),
    )

    html = pio.to_html(fig, include_plotlyjs="cdn", full_html=False, config={"displaylogo": False, "responsive": True})
    components.html(html, height=460)


def to_value_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["value"])
    if "value" in frame.columns:
        return frame[["value"]].copy()
    if "nav" in frame.columns:
        return frame.rename(columns={"nav": "value"})[["value"]].copy()
    first_col = frame.columns[0]
    return frame[[first_col]].rename(columns={first_col: "value"}).copy()


def normalize_scheme_name(value: str) -> str:
    cleaned = value.lower()
    cleaned = cleaned.replace("children's", "childrens")
    cleaned = cleaned.replace("&", " and ")
    cleaned = re.sub(r"[^a-z0-9]+", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def score_scheme_match(left: str, right: str) -> float:
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    overlap = len(left_tokens & right_tokens) / max(len(left_tokens | right_tokens), 1)
    sequence_score = SequenceMatcher(None, left, right).ratio()
    score = 0.55 * overlap + 0.45 * sequence_score

    score += variant_bonus_or_penalty(left_tokens, right_tokens, "growth", reward=0.08, penalty=0.18)
    score += variant_bonus_or_penalty(left_tokens, right_tokens, "idcw", reward=0.08, penalty=0.22)
    score += variant_bonus_or_penalty(left_tokens, right_tokens, "direct", reward=0.05, penalty=0.08)
    score += variant_bonus_or_penalty(left_tokens, right_tokens, "regular", reward=0.05, penalty=0.08)

    for token, penalty in {
        "small": 0.08,
        "mid": 0.08,
        "large": 0.05,
        "flexi": 0.10,
        "multi": 0.10,
        "cap": 0.06,
        "childrens": 0.12,
    }.items():
        if token in left_tokens and token not in right_tokens:
            score -= penalty
    if "value" in right_tokens and "value" not in left_tokens:
        score -= 0.12

    return score


def variant_bonus_or_penalty(left_tokens: set[str], right_tokens: set[str], token: str, reward: float, penalty: float) -> float:
    left_has = token in left_tokens
    right_has = token in right_tokens
    if left_has and right_has:
        return reward
    if left_has != right_has:
        return -penalty
    return 0.0


def is_amc_line(line: str) -> bool:
    return bool(re.search(r"(mutual fund|asset management|amc)", line, re.I)) and len(line) < 100 and "folio" not in line.lower()


def is_scheme_line(line: str) -> bool:
    return (
        bool(
            re.search(
                r"(fund|scheme|equity|balanced|elss|midcap|small cap|large cap|index|advantage|value|opportunities|technology|hybrid|bluechip|flexi cap|multicap|debt)",
                line,
                re.I,
            )
        )
        and not re.search(r"(statement|registrar|advisor|nav|balance|transaction|mobile|email|isin|pan|nominee|bank|address|page \d)", line, re.I)
        and 10 < len(line) < 160
    )


def clean_text(value: str) -> str:
    return normalize_spaces(re.sub(r"\b(?:isin|advisor|arn|branch|email|mobile|pan|nominee|bank).*$", "", value, flags=re.I))


def normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def infer_amc(scheme: str) -> str:
    return " ".join(normalize_spaces(scheme).split()[:3]) + " AMC"


def infer_amc_from_summary_scheme(scheme: str) -> str:
    tokens = normalize_spaces(scheme).split()
    return " ".join(tokens[: min(3, len(tokens))]) + " AMC"


def parse_amount(value: str) -> float | None:
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def parse_signed_amount(value: str) -> float:
    cleaned = str(value).strip()
    if cleaned.startswith("(") and cleaned.endswith(")"):
        parsed = parse_amount(cleaned[1:-1])
        return -(parsed or 0.0)
    return parse_amount(cleaned) or 0.0


def empty_metrics() -> dict:
    return {
        "cagr": np.nan,
        "standard_deviation": np.nan,
        "sharpe": np.nan,
        "alpha": np.nan,
        "beta": np.nan,
        "treynor": np.nan,
        "information_ratio": np.nan,
        "max_drawdown": np.nan,
    }


def safe_div(left: float, right: float) -> float:
    if right in (0, 0.0) or pd.isna(right):
        return np.nan
    return float(left / right)


def format_pct(value: float) -> str:
    return "-" if pd.isna(value) else f"{value * 100:.2f}%"


def format_num(value: float) -> str:
    return "-" if pd.isna(value) else f"{value:.3f}"


def format_inr(value: float) -> str:
    if pd.isna(value):
        return "-"
    return f"Rs {value:,.2f}"


def format_inr_whole(value: float) -> str:
    if pd.isna(value):
        return "-"
    amount = int(round(float(value)))
    sign = "-" if amount < 0 else ""
    digits = str(abs(amount))
    if len(digits) <= 3:
        return f"Rs {sign}{digits}"
    last_three = digits[-3:]
    remaining = digits[:-3]
    groups = []
    while len(remaining) > 2:
        groups.insert(0, remaining[-2:])
        remaining = remaining[:-2]
    if remaining:
        groups.insert(0, remaining)
    return f"Rs {sign}{','.join(groups + [last_three])}"


if __name__ == "__main__":
    main()
