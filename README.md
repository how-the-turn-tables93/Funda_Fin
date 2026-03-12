# CAS Mutual Fund Analyzer

This workspace now contains a Python Streamlit app for uploading a consolidated account statement PDF and analyzing mutual fund holdings.

## Main app

- `streamlit_app.py`: Streamlit UI, CAS parser, NAV/benchmark fetchers, and portfolio analytics
- `requirements.txt`: Python dependencies
- `index.html`, `styles.css`, `app.js`: earlier browser-only prototype kept for reference

## Features

- Upload a detailed CAS PDF
- Extract mutual fund holdings into structured rows
- Detect and handle statements that explicitly say `No Folios Found`
- Enrich schemes with NAV history from `mfapi.in`
- Pull benchmark history using `yfinance`
- Compute scheme-level and portfolio-level:
  - CAGR
  - Annualized standard deviation
  - Sharpe ratio
  - Alpha
  - Beta
  - Treynor's Ratio
  - Information Ratio
  - Maximum drawdown
- Weight portfolio analytics using each scheme's current portfolio weight

## Run

Use your installed Python:

```powershell
& 'C:\Users\aksha\AppData\Local\Programs\Python\Python313\python.exe' -m streamlit run .\streamlit_app.py
```

If `python` works in your terminal, this is equivalent:

```powershell
python -m streamlit run .\streamlit_app.py
```

## Easier launch

If you want a more intuitive startup flow, just run one of these from the project folder:

```powershell
.\launch_app.bat
```

or:

```powershell
.\launch_app.ps1
```

The scripts will:

- find Python automatically
- try launching Streamlit
- install `requirements.txt` once if Streamlit or dependencies are missing

## Current status with the sample PDF

The provided sample file:

- `C:\Users\aksha\OneDrive\Documents\Work\Gamification\Sample files\cas_detailed_report_2026_03_06_190156.pdf`

parses successfully, but it contains no holdings. Its text explicitly says `No Folios Found`, so it is useful for validating the empty-state flow, not for tuning actual folio/scheme extraction rules.

## Important limitations

- Parser tuning for real holdings still needs a CAS file that contains actual folios and scheme rows.
- Scanned or image-only PDFs are not supported yet.
- If `mfapi.in` or Yahoo Finance is unavailable, the app still shows imported holdings and summary values, but historical risk ratios may be blank.
- Scheme matching is fuzzy and may need a manual correction step for similarly named plans.

## Recommended next step

Provide one detailed CAS PDF that contains actual mutual fund folios and holdings. With that, the parser can be tuned to your exact statement layout and made much more reliable.
