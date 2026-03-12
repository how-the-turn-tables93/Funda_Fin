const APP_STATE = {
  extractedHoldings: [],
  schemeCatalog: [],
  benchmarkSeries: [],
  chart: null,
};

const DEMO_HOLDINGS = [
  {
    amc: "Axis Mutual Fund",
    scheme: "Axis Bluechip Fund Direct Growth",
    folio: "12345678",
    units: 425.761,
    averageCostPerUnit: 42.18,
    investedAmount: 17956.6,
  },
  {
    amc: "HDFC Mutual Fund",
    scheme: "HDFC Balanced Advantage Fund Direct Growth",
    folio: "28374655",
    units: 382.191,
    averageCostPerUnit: 52.72,
    investedAmount: 20146.71,
  },
  {
    amc: "ICICI Prudential Mutual Fund",
    scheme: "ICICI Prudential Technology Fund Direct Growth",
    folio: "92837465",
    units: 218.924,
    averageCostPerUnit: 81.31,
    investedAmount: 17800.11,
  },
];

const dom = {
  casFile: document.getElementById("casFile"),
  analyzeButton: document.getElementById("analyzeButton"),
  demoButton: document.getElementById("demoButton"),
  benchmarkSelect: document.getElementById("benchmarkSelect"),
  tenureSelect: document.getElementById("tenureSelect"),
  riskFreeRate: document.getElementById("riskFreeRate"),
  holdingsTableBody: document.getElementById("holdingsTableBody"),
  portfolioMetricsTable: document.getElementById("portfolioMetricsTable"),
  schemeMetricsBody: document.getElementById("schemeMetricsBody"),
  totalValue: document.getElementById("totalValue"),
  totalCost: document.getElementById("totalCost"),
  unrealizedGain: document.getElementById("unrealizedGain"),
  portfolioCagr: document.getElementById("portfolioCagr"),
  statusBanner: document.getElementById("statusBanner"),
  heroSchemeCount: document.getElementById("heroSchemeCount"),
  growthChart: document.getElementById("growthChart"),
};

window.addEventListener("DOMContentLoaded", () => {
  wireEvents();
  renderHoldings([]);
});

function wireEvents() {
  dom.casFile.addEventListener("change", handleFileUpload);
  dom.analyzeButton.addEventListener("click", analyzePortfolio);
  dom.demoButton.addEventListener("click", async () => {
    APP_STATE.extractedHoldings = DEMO_HOLDINGS.map((item) => ({ ...item }));
    setStatus("Demo holdings loaded. You can run analysis immediately.", "info");
    renderHoldings(APP_STATE.extractedHoldings);
    dom.analyzeButton.disabled = false;
  });
}

async function handleFileUpload(event) {
  const file = event.target.files?.[0];
  if (!file) {
    return;
  }

  try {
    setStatus("Reading CAS PDF and extracting text blocks...", "info");
    const textLines = await extractPdfLines(file);
    const holdings = parseCasHoldings(textLines);

    APP_STATE.extractedHoldings = holdings;
    renderHoldings(holdings);

    if (holdings.length === 0) {
      setStatus("The PDF was read, but no holdings could be parsed from the text. This usually means the statement layout differs from the current parser or the PDF is image-based.", "warning");
      dom.analyzeButton.disabled = true;
      return;
    }

    dom.analyzeButton.disabled = false;
    setStatus(`Extracted ${holdings.length} holdings from the uploaded CAS. Review them and click Analyze Portfolio.`, "info");
  } catch (error) {
    console.error(error);
    setStatus(`Could not parse the uploaded PDF: ${error.message}`, "error");
    dom.analyzeButton.disabled = true;
  }
}

async function extractPdfLines(file) {
  const data = await file.arrayBuffer();
  const pdfjs = await import("https://cdn.jsdelivr.net/npm/pdfjs-dist@4.4.168/build/pdf.min.mjs");
  pdfjs.GlobalWorkerOptions.workerSrc = "https://cdn.jsdelivr.net/npm/pdfjs-dist@4.4.168/build/pdf.worker.min.mjs";

  const pdf = await pdfjs.getDocument({ data }).promise;
  const lines = [];

  for (let pageIndex = 1; pageIndex <= pdf.numPages; pageIndex += 1) {
    const page = await pdf.getPage(pageIndex);
    const content = await page.getTextContent();
    const lineMap = new Map();

    for (const item of content.items) {
      if (!("str" in item) || !item.str.trim()) {
        continue;
      }
      const y = Math.round(item.transform[5]);
      if (!lineMap.has(y)) {
        lineMap.set(y, []);
      }
      lineMap.get(y).push({
        text: item.str.trim(),
        x: item.transform[4],
      });
    }

    const pageLines = [...lineMap.entries()]
      .sort((a, b) => b[0] - a[0])
      .map(([, items]) => items.sort((a, b) => a.x - b.x).map((entry) => entry.text).join(" "))
      .map((line) => normalizeSpaces(line))
      .filter(Boolean);

    lines.push(...pageLines);
  }

  return lines;
}

function parseCasHoldings(lines) {
  const holdings = [];
  let currentAmc = "";
  let currentFolio = "";
  let currentScheme = "";

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];

    if (/(mutual fund|asset management|amc)/i.test(line) && line.length < 90 && !/\bfolio\b/i.test(line)) {
      currentAmc = cleanSchemeText(line);
    }

    const folioMatch = line.match(/folio(?:\s*(?:no|number|#))?\s*[:\-]?\s*([A-Z0-9\/-]{4,})/i);
    if (folioMatch) {
      currentFolio = folioMatch[1].trim();
    }

    const possibleScheme = detectSchemeLine(line);
    if (possibleScheme) {
      currentScheme = possibleScheme;
      continue;
    }

    const valuationMatch = findValuationData(line);
    if (!valuationMatch && index + 1 < lines.length) {
      const nextLine = lines[index + 1];
      const mergedMatch = findValuationData(`${line} ${nextLine}`);
      if (mergedMatch && currentScheme) {
        holdings.push(buildHoldingRecord(currentAmc, currentScheme, currentFolio, mergedMatch));
      }
      continue;
    }

    if (valuationMatch && currentScheme) {
      holdings.push(buildHoldingRecord(currentAmc, currentScheme, currentFolio, valuationMatch));
    }
  }

  return dedupeHoldings(holdings).filter((holding) => holding.units > 0 && holding.scheme);
}

function detectSchemeLine(line) {
  const cleanLine = cleanSchemeText(line);
  if (!cleanLine) {
    return null;
  }

  const looksLikeScheme =
    /(fund|scheme|equity|balanced|elss|midcap|small cap|large cap|index|advantage|value|opportunities|technology|hybrid|bluechip|flexi cap|multicap|overnight|liquid|debt)/i.test(cleanLine) &&
    !/(statement|registrar|advisor|nav|balance|closing|opening|transaction|mobile|email|isin|pan|nominee|bank|address|branch)/i.test(cleanLine) &&
    cleanLine.length > 10 &&
    cleanLine.length < 140;

  return looksLikeScheme ? cleanLine : null;
}

function findValuationData(line) {
  const numbers = [...line.matchAll(/(?:Rs\.?|INR)?\s*([0-9,]+\.\d{2,4}|[0-9,]+)/gi)]
    .map((match) => parseAmount(match[1]))
    .filter((value) => Number.isFinite(value));

  if (numbers.length < 3) {
    return null;
  }

  const value = [...numbers].reverse().find((num) => num > 100);
  const nav = numbers.length >= 2 ? numbers[numbers.length - 2] : null;
  const units = numbers[0];

  if (!units || !nav || !value) {
    return null;
  }

  const optionalCost = numbers.length >= 4 ? numbers[numbers.length - 3] : null;
  let investedAmount = value;
  let averageCostPerUnit = value / units;

  if (optionalCost && optionalCost > 0) {
    if (optionalCost <= 1000) {
      averageCostPerUnit = optionalCost;
      investedAmount = units * averageCostPerUnit;
    } else if (optionalCost < value * 1.5) {
      investedAmount = optionalCost;
      averageCostPerUnit = investedAmount / units;
    }
  }

  return {
    units,
    nav,
    currentValue: value,
    averageCostPerUnit,
    investedAmount,
  };
}

function buildHoldingRecord(amc, scheme, folio, valuation) {
  return {
    amc: amc || inferAmcFromSchemeName(scheme),
    scheme,
    folio: folio || "Not found",
    units: valuation.units,
    averageCostPerUnit: valuation.averageCostPerUnit,
    investedAmount: valuation.investedAmount,
    currentNav: valuation.nav,
    currentValue: valuation.currentValue,
  };
}

function dedupeHoldings(holdings) {
  const map = new Map();

  holdings.forEach((holding) => {
    const key = `${holding.folio}__${holding.scheme}`;
    if (!map.has(key)) {
      map.set(key, holding);
      return;
    }

    const existing = map.get(key);
    if ((holding.currentValue || 0) >= (existing.currentValue || 0)) {
      map.set(key, holding);
    }
  });

  return [...map.values()];
}

async function analyzePortfolio() {
  if (!APP_STATE.extractedHoldings.length) {
    setStatus("There are no holdings to analyze yet.", "warning");
    return;
  }

  try {
    dom.analyzeButton.disabled = true;
    setStatus("Fetching AMFI scheme list, matching holdings, and loading NAV history...", "info");

    if (!APP_STATE.schemeCatalog.length) {
      APP_STATE.schemeCatalog = await fetchSchemeCatalog();
    }

    const matchedHoldings = await enrichHoldings(APP_STATE.extractedHoldings);
    let benchmarkSeries = [];
    let benchmarkWarning = "";

    try {
      benchmarkSeries = await fetchBenchmarkSeries(dom.benchmarkSelect.value);
      APP_STATE.benchmarkSeries = benchmarkSeries;
    } catch (benchmarkError) {
      console.warn(benchmarkError);
      benchmarkWarning = " Benchmark data could not be loaded, so Alpha, Beta, Treynor's Ratio, and Information Ratio may be unavailable.";
    }

    setStatus("Computing portfolio and scheme-level analytics...", "info");
    const analytics = computeAnalytics(matchedHoldings, benchmarkSeries, dom.tenureSelect.value, Number(dom.riskFreeRate.value) / 100);

    renderHoldings(analytics.holdings);
    renderPortfolioSummary(analytics);
    renderPortfolioMetrics(analytics.portfolioMetrics);
    renderSchemeMetrics(analytics.schemeMetrics);
    renderGrowthChart(analytics.growthSeries, analytics.benchmarkGrowthSeries);

    dom.analyzeButton.disabled = false;
    setStatus(`Analysis complete. Review the summary, scheme metrics, and benchmarked growth chart below.${benchmarkWarning}`, "info");
  } catch (error) {
    console.error(error);
    setStatus(`Analysis failed: ${error.message}`, "error");
    dom.analyzeButton.disabled = false;
  }
}

async function fetchSchemeCatalog() {
  const response = await fetch("https://api.mfapi.in/mf");
  if (!response.ok) {
    throw new Error("AMFI scheme catalog could not be fetched.");
  }
  return response.json();
}

async function enrichHoldings(holdings) {
  const enriched = await Promise.all(
    holdings.map(async (holding) => {
      const schemeMatch = findBestSchemeMatch(holding.scheme, APP_STATE.schemeCatalog);
      let navHistory = [];
      let latestNav = holding.currentNav || 0;

      if (schemeMatch) {
        navHistory = await fetchNavHistory(schemeMatch.schemeCode);
        if (navHistory.length) {
          latestNav = navHistory[navHistory.length - 1].nav;
        }
      }

      const currentValue = latestNav && holding.units ? latestNav * holding.units : holding.currentValue || 0;
      const investedAmount = holding.investedAmount || holding.units * holding.averageCostPerUnit;

      return {
        ...holding,
        schemeCode: schemeMatch?.schemeCode || null,
        matchedSchemeName: schemeMatch?.schemeName || "Unmatched",
        navHistory,
        currentNav: latestNav,
        currentValue,
        investedAmount,
        averageCostPerUnit: holding.averageCostPerUnit || (holding.units ? investedAmount / holding.units : 0),
        weight: 0,
      };
    }),
  );

  const totalCurrentValue = enriched.reduce((sum, item) => sum + (item.currentValue || 0), 0);
  return enriched.map((holding) => ({
    ...holding,
    weight: totalCurrentValue > 0 ? (holding.currentValue || 0) / totalCurrentValue : 0,
  }));
}

async function fetchNavHistory(schemeCode) {
  const response = await fetch(`https://api.mfapi.in/mf/${schemeCode}`);
  if (!response.ok) {
    return [];
  }

  const payload = await response.json();
  return (payload.data || [])
    .map((entry) => ({
      date: parseMfApiDate(entry.date),
      nav: Number(entry.nav),
    }))
    .filter((entry) => entry.date && Number.isFinite(entry.nav))
    .sort((a, b) => a.date - b.date);
}

async function fetchBenchmarkSeries(symbol) {
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${symbol}?range=10y&interval=1d&includeAdjustedClose=true`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error("Benchmark history could not be fetched from Yahoo Finance.");
  }

  const payload = await response.json();
  const result = payload.chart?.result?.[0];
  const timestamps = result?.timestamp || [];
  const closes = result?.indicators?.adjclose?.[0]?.adjclose || result?.indicators?.quote?.[0]?.close || [];

  return timestamps
    .map((timestamp, index) => ({
      date: new Date(timestamp * 1000),
      nav: Number(closes[index]),
    }))
    .filter((point) => point.date && Number.isFinite(point.nav))
    .sort((a, b) => a.date - b.date);
}

function computeAnalytics(holdings, benchmarkSeries, tenure, riskFreeRate) {
  const filteredHoldings = holdings.map((holding) => ({
    ...holding,
    navHistory: trimSeriesByTenure(holding.navHistory, tenure),
  }));
  const filteredBenchmark = trimSeriesByTenure(benchmarkSeries, tenure);
  const alignedHoldings = filteredHoldings.filter((holding) => holding.navHistory.length >= 30);

  const portfolioSeries = buildPortfolioSeries(alignedHoldings);
  const aligned = alignSeries(portfolioSeries, filteredBenchmark);
  const portfolioMetrics = calculateMetrics(aligned.asset, aligned.benchmark, riskFreeRate);
  const schemeMetrics = alignedHoldings.map((holding) => {
    const merged = alignSeries(holding.navHistory, filteredBenchmark);
    return {
      scheme: holding.scheme,
      ...calculateMetrics(merged.asset, merged.benchmark, riskFreeRate),
    };
  });

  const totalValue = holdings.reduce((sum, item) => sum + (item.currentValue || 0), 0);
  const totalCost = holdings.reduce((sum, item) => sum + (item.investedAmount || 0), 0);

  return {
    holdings: holdings.map((holding) => ({
      ...holding,
      weight: totalValue ? holding.currentValue / totalValue : 0,
    })),
    totalValue,
    totalCost,
    totalGain: totalValue - totalCost,
    portfolioMetrics,
    schemeMetrics,
    growthSeries: rebasedSeries(aligned.asset, 100000),
    benchmarkGrowthSeries: rebasedSeries(aligned.benchmark, 100000),
  };
}

function buildPortfolioSeries(holdings) {
  const dateMap = new Map();

  holdings.forEach((holding) => {
    const rebased = rebasedSeries(holding.navHistory, 1);
    rebased.forEach((point) => {
      const key = isoDate(point.date);
      if (!dateMap.has(key)) {
        dateMap.set(key, { date: point.date, nav: 0 });
      }
      dateMap.get(key).nav += point.nav * (holding.weight || 0);
    });
  });

  return [...dateMap.values()].sort((a, b) => a.date - b.date);
}

function calculateMetrics(assetSeries, benchmarkSeries, riskFreeRate) {
  if (assetSeries.length < 30) {
    return emptyMetricSet();
  }

  const assetReturns = toDailyReturns(assetSeries);
  const benchmarkReturns = benchmarkSeries.length >= 30 ? toDailyReturns(benchmarkSeries) : [];
  const alignedReturns = alignReturnSeries(assetReturns, benchmarkReturns);
  const assetOnlyReturns = alignedReturns.asset.length ? alignedReturns.asset : assetReturns;
  const benchmarkOnlyReturns = alignedReturns.benchmark;

  const totalReturn = assetSeries[assetSeries.length - 1].nav / assetSeries[0].nav - 1;
  const years = Math.max((assetSeries[assetSeries.length - 1].date - assetSeries[0].date) / (365.25 * 24 * 60 * 60 * 1000), 1 / 252);
  const cagr = Math.pow(1 + totalReturn, 1 / years) - 1;
  const stdDev = standardDeviation(assetOnlyReturns.map((item) => item.value)) * Math.sqrt(252);
  const maxDrawdown = calculateMaxDrawdown(assetSeries);

  if (!benchmarkOnlyReturns.length) {
    return {
      cagr,
      standardDeviation: stdDev,
      sharpe: stdDev ? (cagr - riskFreeRate) / stdDev : null,
      alpha: null,
      beta: null,
      treynor: null,
      informationRatio: null,
      maxDrawdown,
    };
  }

  const assetValues = alignedReturns.asset.map((item) => item.value);
  const benchmarkValues = alignedReturns.benchmark.map((item) => item.value);
  const benchmarkCagr = annualizeFromReturns(benchmarkValues);
  const beta = covariance(assetValues, benchmarkValues) / variance(benchmarkValues);
  const trackingDiff = assetValues.map((value, index) => value - benchmarkValues[index]);
  const trackingError = standardDeviation(trackingDiff) * Math.sqrt(252);
  const activeReturnAnnual = average(trackingDiff) * 252;

  return {
    cagr,
    standardDeviation: stdDev,
    sharpe: stdDev ? (cagr - riskFreeRate) / stdDev : null,
    alpha: beta != null ? cagr - (riskFreeRate + beta * (benchmarkCagr - riskFreeRate)) : null,
    beta,
    treynor: beta ? (cagr - riskFreeRate) / beta : null,
    informationRatio: trackingError ? activeReturnAnnual / trackingError : null,
    maxDrawdown,
  };
}

function emptyMetricSet() {
  return {
    cagr: null,
    standardDeviation: null,
    sharpe: null,
    alpha: null,
    beta: null,
    treynor: null,
    informationRatio: null,
    maxDrawdown: null,
  };
}

function renderPortfolioSummary(analytics) {
  dom.totalValue.textContent = formatCurrency(analytics.totalValue);
  dom.totalCost.textContent = formatCurrency(analytics.totalCost);
  dom.unrealizedGain.textContent = formatCurrency(analytics.totalGain);
  dom.unrealizedGain.className = analytics.totalGain >= 0 ? "positive" : "negative";
  dom.portfolioCagr.textContent = formatPercent(analytics.portfolioMetrics.cagr);
}

function renderHoldings(holdings) {
  dom.heroSchemeCount.textContent = `${holdings.length} schemes loaded`;

  if (!holdings.length) {
    dom.holdingsTableBody.innerHTML = `<tr><td colspan="9" class="empty-state">No holdings extracted yet.</td></tr>`;
    return;
  }

  const totalValue = holdings.reduce((sum, item) => sum + (item.currentValue || 0), 0);

  dom.holdingsTableBody.innerHTML = holdings.map((holding) => `
    <tr>
      <td>${escapeHtml(holding.amc || "-")}</td>
      <td>${escapeHtml(holding.scheme || "-")}</td>
      <td>${escapeHtml(holding.folio || "-")}</td>
      <td>${formatNumber(holding.units, 3)}</td>
      <td>${formatCurrency(holding.averageCostPerUnit || 0)}</td>
      <td>${formatCurrency(holding.currentNav || 0)}</td>
      <td>${formatCurrency(holding.currentValue || 0)}</td>
      <td>${formatPercent(totalValue ? (holding.currentValue || 0) / totalValue : holding.weight || 0)}</td>
      <td>${escapeHtml(holding.matchedSchemeName || "Pending")}</td>
    </tr>
  `).join("");
}

function renderPortfolioMetrics(metrics) {
  const entries = [
    ["CAGR", formatPercent(metrics.cagr)],
    ["Annualized Standard Deviation", formatPercent(metrics.standardDeviation)],
    ["Sharpe Ratio", formatDecimal(metrics.sharpe)],
    ["Alpha", formatPercent(metrics.alpha)],
    ["Beta", formatDecimal(metrics.beta)],
    ["Treynor's Ratio", formatDecimal(metrics.treynor)],
    ["Information Ratio", formatDecimal(metrics.informationRatio)],
    ["Maximum Drawdown", formatPercent(metrics.maxDrawdown)],
  ];

  dom.portfolioMetricsTable.innerHTML = entries.map(([label, value]) => `
    <tr>
      <th>${label}</th>
      <td>${value}</td>
    </tr>
  `).join("");
}

function renderSchemeMetrics(metrics) {
  if (!metrics.length) {
    dom.schemeMetricsBody.innerHTML = `<tr><td colspan="9" class="empty-state">Not enough NAV history was available for the imported schemes.</td></tr>`;
    return;
  }

  dom.schemeMetricsBody.innerHTML = metrics.map((metric) => `
    <tr>
      <td>${escapeHtml(metric.scheme)}</td>
      <td>${formatPercent(metric.cagr)}</td>
      <td>${formatPercent(metric.standardDeviation)}</td>
      <td>${formatDecimal(metric.sharpe)}</td>
      <td>${formatPercent(metric.alpha)}</td>
      <td>${formatDecimal(metric.beta)}</td>
      <td>${formatDecimal(metric.treynor)}</td>
      <td>${formatDecimal(metric.informationRatio)}</td>
      <td>${formatPercent(metric.maxDrawdown)}</td>
    </tr>
  `).join("");
}

function renderGrowthChart(portfolioSeries, benchmarkSeries) {
  if (APP_STATE.chart) {
    APP_STATE.chart.destroy();
  }

  APP_STATE.chart = new Chart(dom.growthChart, {
    type: "line",
    data: {
      labels: portfolioSeries.map((point) => isoDate(point.date)),
      datasets: [
        {
          label: "Portfolio",
          data: portfolioSeries.map((point) => point.nav),
          borderColor: "#0d6b57",
          backgroundColor: "rgba(13, 107, 87, 0.15)",
          borderWidth: 3,
          tension: 0.25,
          pointRadius: 0,
        },
        {
          label: "Benchmark",
          data: benchmarkSeries.map((point) => point.nav),
          borderColor: "#cf7a19",
          backgroundColor: "rgba(207, 122, 25, 0.12)",
          borderWidth: 2.4,
          tension: 0.25,
          pointRadius: 0,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      aspectRatio: 2.1,
      interaction: {
        mode: "index",
        intersect: false,
      },
      plugins: {
        legend: {
          labels: {
            usePointStyle: true,
          },
        },
      },
      scales: {
        x: {
          ticks: {
            maxTicksLimit: 8,
          },
          grid: {
            display: false,
          },
        },
        y: {
          ticks: {
            callback(value) {
              return formatCurrency(value, true);
            },
          },
        },
      },
    },
  });
}

function findBestSchemeMatch(targetScheme, catalog) {
  const normalizedTarget = normalizeSchemeName(targetScheme);
  let bestMatch = null;
  let bestScore = 0;

  catalog.forEach((entry) => {
    const score = similarityScore(normalizedTarget, normalizeSchemeName(entry.schemeName));
    if (score > bestScore) {
      bestScore = score;
      bestMatch = entry;
    }
  });

  return bestScore >= 0.55 ? bestMatch : null;
}

function normalizeSchemeName(value) {
  return normalizeSpaces(
    (value || "")
      .toLowerCase()
      .replace(/\b(direct|regular|growth|plan|option|idcw|dividend|reinvestment)\b/g, " ")
      .replace(/[^a-z0-9]+/g, " "),
  ).trim();
}

function similarityScore(left, right) {
  const leftSet = new Set(left.split(" ").filter(Boolean));
  const rightSet = new Set(right.split(" ").filter(Boolean));
  const union = new Set([...leftSet, ...rightSet]);
  const intersection = [...leftSet].filter((token) => rightSet.has(token));
  return union.size ? intersection.length / union.size : 0;
}

function trimSeriesByTenure(series, tenure) {
  if (!series.length || tenure === "MAX") {
    return series;
  }

  const endDate = series[series.length - 1].date;
  const startDate = new Date(endDate);
  if (tenure === "1Y") startDate.setFullYear(startDate.getFullYear() - 1);
  if (tenure === "3Y") startDate.setFullYear(startDate.getFullYear() - 3);
  if (tenure === "5Y") startDate.setFullYear(startDate.getFullYear() - 5);

  return series.filter((point) => point.date >= startDate);
}

function alignSeries(assetSeries, benchmarkSeries) {
  if (!assetSeries.length) {
    return { asset: [], benchmark: [] };
  }
  if (!benchmarkSeries.length) {
    return { asset: assetSeries, benchmark: [] };
  }

  const benchmarkMap = new Map(benchmarkSeries.map((point) => [isoDate(point.date), point]));
  const asset = [];
  const benchmark = [];

  assetSeries.forEach((point) => {
    const key = isoDate(point.date);
    const benchmarkPoint = benchmarkMap.get(key);
    if (benchmarkPoint) {
      asset.push(point);
      benchmark.push(benchmarkPoint);
    }
  });

  return { asset, benchmark };
}

function rebasedSeries(series, base) {
  if (!series.length || !series[0].nav) {
    return [];
  }
  return series.map((point) => ({
    date: point.date,
    nav: (point.nav / series[0].nav) * base,
  }));
}

function toDailyReturns(series) {
  const returns = [];

  for (let index = 1; index < series.length; index += 1) {
    const previous = series[index - 1].nav;
    const current = series[index].nav;
    if (!previous || !current) {
      continue;
    }
    returns.push({
      date: series[index].date,
      value: current / previous - 1,
    });
  }

  return returns;
}

function alignReturnSeries(assetReturns, benchmarkReturns) {
  const benchmarkMap = new Map(benchmarkReturns.map((item) => [isoDate(item.date), item.value]));
  const asset = [];
  const benchmark = [];

  assetReturns.forEach((item) => {
    const benchmarkValue = benchmarkMap.get(isoDate(item.date));
    if (Number.isFinite(benchmarkValue)) {
      asset.push(item);
      benchmark.push({ date: item.date, value: benchmarkValue });
    }
  });

  return { asset, benchmark };
}

function annualizeFromReturns(returns) {
  if (!returns.length) {
    return 0;
  }
  const compounded = returns.reduce((acc, item) => acc * (1 + item), 1);
  return Math.pow(compounded, 252 / returns.length) - 1;
}

function calculateMaxDrawdown(series) {
  let peak = series[0].nav;
  let maxDrawdown = 0;

  series.forEach((point) => {
    peak = Math.max(peak, point.nav);
    const drawdown = point.nav / peak - 1;
    maxDrawdown = Math.min(maxDrawdown, drawdown);
  });

  return maxDrawdown;
}

function standardDeviation(values) {
  if (values.length < 2) {
    return 0;
  }
  const avg = values.reduce((sum, value) => sum + value, 0) / values.length;
  const varianceValue = values.reduce((sum, value) => sum + ((value - avg) ** 2), 0) / (values.length - 1);
  return Math.sqrt(varianceValue);
}

function covariance(left, right) {
  if (left.length < 2 || right.length < 2 || left.length !== right.length) {
    return 0;
  }
  const leftMean = left.reduce((sum, value) => sum + value, 0) / left.length;
  const rightMean = right.reduce((sum, value) => sum + value, 0) / right.length;
  let total = 0;
  for (let index = 0; index < left.length; index += 1) {
    total += (left[index] - leftMean) * (right[index] - rightMean);
  }
  return total / (left.length - 1);
}

function variance(values) {
  if (values.length < 2) {
    return 0;
  }
  const mean = values.reduce((sum, value) => sum + value, 0) / values.length;
  return values.reduce((sum, value) => sum + ((value - mean) ** 2), 0) / (values.length - 1);
}

function average(values) {
  if (!values.length) {
    return 0;
  }
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function parseMfApiDate(value) {
  const [day, month, year] = value.split("-");
  return new Date(`${year}-${month}-${day}T00:00:00`);
}

function parseAmount(value) {
  return Number(String(value).replace(/,/g, ""));
}

function normalizeSpaces(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function cleanSchemeText(value) {
  return normalizeSpaces(
    String(value || "")
      .replace(/\b(?:isin|advisor|arn|branch|email|mobile|pan|nominee|bank).*/i, "")
      .replace(/[:|]+/g, " "),
  );
}

function inferAmcFromSchemeName(scheme) {
  const firstChunk = normalizeSpaces(scheme).split(" ").slice(0, 3).join(" ");
  return `${firstChunk} AMC`.trim();
}

function setStatus(message, kind) {
  dom.statusBanner.textContent = message;
  dom.statusBanner.className = `status-banner ${kind}`;
}

function formatCurrency(value, compact = false) {
  if (!Number.isFinite(value)) {
    return "-";
  }
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    notation: compact ? "compact" : "standard",
    maximumFractionDigits: compact ? 1 : 2,
  }).format(value);
}

function formatPercent(value) {
  if (!Number.isFinite(value)) {
    return "-";
  }
  return `${(value * 100).toFixed(2)}%`;
}

function formatNumber(value, decimals = 2) {
  if (!Number.isFinite(value)) {
    return "-";
  }
  return value.toLocaleString("en-IN", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function formatDecimal(value) {
  if (!Number.isFinite(value)) {
    return "-";
  }
  return value.toFixed(3);
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function isoDate(date) {
  return date.toISOString().slice(0, 10);
}
