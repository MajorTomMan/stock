import "./style.css";

const root = document.querySelector("#app");
const state = {
  selected: "000001",
  instrument: null,
  bars: [],               // Latest page for summary cards
  pages: [],              // Cached history pages: newest first
  pageIndex: 0,
  hasMore: false,
  nextEnd: null,
  loadingOlder: false,
  market: null,
  range: "3M",
  view: "dashboard",
  stockRequest: 0,
  searchRequest: 0,
  searchTimer: null,
  directoryRequest: 0,
  directoryPage: 0,
  directoryHasMore: false,
  directoryQuery: "",
  directoryTimer: null,
  maEnabled: new Set([5, 10, 20]),
  maByDate: new Map(),
};

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]
  );
}
function number(value) {
  return value === null || value === undefined || value === "" ? null : Number(value);
}
function price(value) {
  const v = number(value);
  return v === null || !Number.isFinite(v) ? "—" : v.toFixed(2);
}
function amount(value, unit = "") {
  const n = number(value);
  if (n === null || !Number.isFinite(n)) return "—";
  if (Math.abs(n) >= 1e8) return (n / 1e8).toFixed(2) + " 亿" + unit;
  if (Math.abs(n) >= 1e4) return (n / 1e4).toFixed(2) + " 万" + unit;
  return n.toLocaleString("zh-CN", { maximumFractionDigits: 0 }) + (unit ? " " + unit : "");
}
function percent(value) {
  const n = number(value);
  if (n === null || !Number.isFinite(n)) return "—";
  return (n > 0 ? "+" : "") + n.toFixed(2) + "%";
}
function direction(current, previous) {
  const c = number(current), p = number(previous);
  if (c === null || p === null) return "";
  return c > p ? "up" : c < p ? "down" : "flat";
}
async function api(path) {
  const response = await fetch(path, { headers: { Accept: "application/json" } });
  if (!response.ok) {
    let detail = "";
    try { detail = (await response.json()).detail || ""; } catch { /* use HTTP status */ }
    throw new Error(detail || "HTTP " + response.status);
  }
  return response.json();
}

function shell() {
  root.innerHTML = [
    '<div class="app-shell">',
    '  <aside class="sidebar">',
    '    <a href="/" class="brand" aria-label="Stockroom 首页"><span class="brand-icon">S<span>.</span></span><span class="brand-word">stockroom<small>MARKET INTELLIGENCE</small></span></a>',
    '    <div class="sidebar-caption">工作空间</div>',
    '    <nav class="nav-menu" aria-label="主导航">',
    '      <button class="nav-item active" data-view="dashboard"><span class="nav-icon">▦</span>行情工作台<span class="nav-arrow">›</span></button>',
    '      <button class="nav-item" data-view="about"><span class="nav-icon">ⓘ</span>数据说明<span class="nav-arrow">›</span></button>',
    '    </nav>',
    '    <div class="sidebar-caption watch-caption">快速查看</div>',
    '    <div class="watch-list">',
    '      <button class="watch-item" data-code="000001"><span class="watch-dot"></span><span><b>000001</b><small>平安银行</small></span><span class="watch-chevron">↗</span></button>',
    '      <button class="watch-item" data-code="300001"><span class="watch-dot"></span><span><b>300001</b><small>特锐德</small></span><span class="watch-chevron">↗</span></button>',
    '      <button class="watch-item" data-code="000004"><span class="watch-dot"></span><span><b>000004</b><small>国华退</small></span><span class="watch-chevron">↗</span></button>',
    '    </div>',
    '    <div class="sidebar-bottom"><span class="status-orb"></span><span>本地数据库<small>历史数据 · 非实时行情</small></span></div>',
    '  </aside>',
    '  <div class="workspace">',
    '    <header class="topbar"><div class="mobile-brand">stockroom<span>.</span></div>',
    '      <div class="search-box"><span class="search-icon">⌕</span><input id="stock-search" type="search" placeholder="搜索股票代码或名称…" autocomplete="off" aria-label="搜索股票" /><span class="search-shortcut">SZ</span>',
    '        <div id="search-results" class="search-results" hidden></div>',
    '      </div>',
    '      <button class="mobile-about" id="mobile-toggle-about">数据说明</button><div class="topbar-right"><span class="market-dot"></span><span>深圳市场</span><span class="topbar-divider"></span><span id="last-date">读取数据库中…</span></div>',
    '    </header>',
    '    <main class="main-content">',
    '      <section id="dashboard-view">',
    '        <div class="page-heading"><div><div class="eyebrow"><span class="eyebrow-line"></span> STOCK MARKET DASHBOARD</div><h1>市场数据，一目了然<span class="heading-period">.</span></h1><p>探索已入库的深市股票、历史价格与成交趋势。</p></div><span class="history-pill"><span class="history-dot"></span>历史行情 · 非实时</span></div>',
    '        <div id="connection-error" class="notice" hidden></div>',
    '        <div class="overview-grid">',
    '          <article class="metric-card"><div class="metric-title">当前股票 <span>01 / STOCK</span></div><div class="metric-main"><strong id="selected-name">加载中…</strong><span id="selected-symbol" class="metric-code">000001.SZ</span></div><div class="metric-foot"><span id="selected-industry">深市证券</span><span>未复权 · 日线</span></div></article>',
    '          <article class="metric-card"><div class="metric-title">最近收盘 <span>02 / CLOSE</span></div><div class="metric-main"><strong id="latest-close">—</strong><span class="metric-unit">CNY</span></div><div class="metric-foot"><span id="latest-change">等待历史数据</span><span id="latest-close-date">—</span></div></article>',
    '          <article class="metric-card"><div class="metric-title">日线记录 <span>03 / HISTORY</span></div><div class="metric-main"><strong id="bar-count">—</strong><span class="metric-unit">条</span></div><div class="metric-foot"><span>当前已加载</span><span id="source-tag">—</span></div></article>',
    '        </div>',
    '        <section class="content-card chart-card"><div class="section-heading"><div><div class="section-eyebrow">PRICE &amp; VOLUME</div><div class="section-title"><h2 id="chart-title">日 K 线</h2><span class="section-subtitle" id="chart-subtitle">正在读取行情…</span></div></div><div class="range-buttons" role="group" aria-label="图表时间范围"><button data-range="1M">1月</button><button data-range="3M" class="active">3月</button><button data-range="6M">6月</button><button data-range="1Y">1年</button><button data-range="ALL">当前段全部</button></div></div>',
    '          <div class="chart-legend"><span><i class="legend-candle"></i> 未复权价格 (CNY)</span><span><i class="legend-volume"></i> 成交量 (股)</span><span class="legend-hint">横向滚动查看更早日期 · 悬停查看明细</span></div>',
    '          <div class="ma-toolbar"><span>移动平均线</span><button type="button" data-ma="5" aria-pressed="true" class="ma-toggle active ma-five"><i></i> MA5</button><button type="button" data-ma="10" aria-pressed="true" class="ma-toggle active ma-ten"><i></i> MA10</button><button type="button" data-ma="20" aria-pressed="true" class="ma-toggle active ma-twenty"><i></i> MA20</button><span class="ma-caption">按已加载收盘价计算 · 样本不足时不显示</span></div>',
    '          <div id="hover-details" class="hover-details">选择股票后展示行情</div>',
    '          <div class="chart-viewport" id="chart-viewport"><div id="chart" class="chart-empty">正在读取日线…</div></div>',
    '          <div class="chart-footer"><span id="chart-range">—</span><span>↑ 红涨 &nbsp; ↓ 绿跌</span></div>',
    '          <div class="history-navigation"><button id="history-older" disabled>← 更早 750 条</button><span id="history-status" aria-live="polite">正在读取历史…</span><button id="history-newer" disabled>较新 750 条 →</button></div>',
    '        </section>',
    '        <section class="content-card list-card"><div class="section-heading"><div><div class="section-eyebrow">DAILY DETAILS</div><div class="section-title"><h2>日线明细</h2><span class="section-subtitle" id="daily-details-range">当前图表区间内最近 20 条</span></div></div><span class="table-note">全部数值来自数据库 · 未复权</span></div>',
    '          <div class="table-wrap"><table class="stocks-table daily-details-table"><thead><tr><th>日期</th><th>开盘</th><th>最高</th><th>最低</th><th>收盘</th><th>涨跌幅</th><th>成交量（股）</th><th>成交额（元）</th><th>来源</th></tr></thead><tbody id="daily-details-rows"><tr><td colspan="9" class="empty-row">正在读取日线…</td></tr></tbody></table></div>',
    '        </section>',
    '        <section class="content-card list-card"><div class="section-heading"><div><div class="section-eyebrow">MARKET SNAPSHOT</div><div class="section-title"><h2>行情概览</h2><span class="section-subtitle" id="market-subtitle">读取已入库数据…</span></div></div><span class="table-note">按已入库股票的成交额排序</span></div>',
    '          <div class="table-wrap"><table class="stocks-table"><thead><tr><th>股票</th><th>收盘价</th><th>涨跌幅</th><th>成交额</th><th>来源</th><th></th></tr></thead><tbody id="market-rows"><tr><td colspan="6" class="empty-row">正在载入…</td></tr></tbody></table></div>',
    '        </section>',
    '        <section class="content-card directory-card" id="stock-directory"><div class="section-heading"><div><div class="section-eyebrow">STOCK DIRECTORY</div><div class="section-title"><h2>股票目录</h2><span class="section-subtitle">浏览主数据中的全部深市证券，包括尚未补齐最新行情的股票</span></div></div><label class="directory-search"><span>⌕</span><input id="directory-filter" type="search" maxlength="128" placeholder="按代码或名称筛选…" aria-label="筛选股票目录" /></label></div>',
    '          <div class="table-wrap"><table class="stocks-table directory-table"><thead><tr><th>股票</th><th>板块</th><th>上市日期</th><th>状态</th><th></th></tr></thead><tbody id="directory-rows"><tr><td colspan="5" class="empty-row">正在读取股票目录…</td></tr></tbody></table></div>',
    '          <div class="directory-pagination"><button id="directory-prev" disabled>← 上一页</button><span id="directory-page" aria-live="polite">—</span><button id="directory-next" disabled>下一页 →</button></div>',
    '        </section>',
    '        <footer class="footer"><span>STOCKROOM / 深市历史数据工作台</span><span>仅供研究与数据展示 · 非实时行情</span></footer>',
    '      </section>',
    '      <section id="about-view" class="about-view" hidden><div class="eyebrow"><span class="eyebrow-line"></span> ABOUT THE DATA</div><h1>关于这里的数据<span class="heading-period">.</span></h1><p>这个工作台只读取你本机 PostgreSQL 中已经导入的历史行情，不会直接访问外部行情服务。</p>',
    '        <div class="about-grid"><article class="content-card"><span class="about-num">01</span><h2>数据来源</h2><p>BaoStock 历史未复权日线及深圳证券交易所官方日快照。每条日线展示数据库选择的来源；股票尚未回填的日期不会生成模拟价格。</p></article><article class="content-card"><span class="about-num">02</span><h2>日期与范围</h2><p>概览日期是数据库中最后一个有记录的日期，不一定是今天。图表按段加载历史日线，每段最多 750 条。点击“更早”或“较新”切换区间；“当前段全部”仅展示本段数据，未采集的日期不会显示。</p></article><article class="content-card"><span class="about-num">03</span><h2>开发阶段</h2><p>当前功能是搜索、股票详情、未复权日 K 线、成交量和数据库行情概览；复权、交易日历与历史覆盖率检查尚未接入。</p></article></div>',
    '        <button class="return-button" id="back-to-dashboard">返回行情工作台 →</button>',
    '      </section>',
    '    </main>',
    '  </div>',
    '</div>',
  ].join("");
  root.querySelectorAll("[data-view]").forEach((button) =>
    button.addEventListener("click", () => switchView(button.dataset.view))
  );
  root.querySelectorAll("[data-code]").forEach((button) =>
    button.addEventListener("click", () => selectStock(button.dataset.code))
  );
  root.querySelectorAll("[data-range]").forEach((button) =>
    button.addEventListener("click", () => {
      state.range = button.dataset.range;
      root.querySelectorAll("[data-range]").forEach((item) =>
        item.classList.toggle("active", item.dataset.range === state.range)
      );
      renderChart();
    })
  );
  root.querySelectorAll("[data-ma]").forEach((button) => {
    button.addEventListener("click", () => {
      const period = Number(button.dataset.ma);
      if (state.maEnabled.has(period)) state.maEnabled.delete(period);
      else state.maEnabled.add(period);
      button.classList.toggle("active", state.maEnabled.has(period));
      button.setAttribute("aria-pressed", String(state.maEnabled.has(period)));
      renderChart();
    });
  });
  root.querySelector("#history-older").addEventListener("click", loadOlder);
  root.querySelector("#history-newer").addEventListener("click", showNewer);
  root.querySelector("#market-rows").addEventListener("click", (event) => {
    const button = event.target.closest("[data-symbol]");
    if (button) selectStock(button.dataset.symbol);
  });
  root.querySelector("#directory-rows").addEventListener("click", (event) => {
    const button = event.target.closest("[data-directory-symbol]");
    if (button) selectStock(button.dataset.directorySymbol);
  });
  root.querySelector("#directory-filter").addEventListener("input", (event) => {
    clearTimeout(state.directoryTimer);
    state.directoryQuery = event.target.value.trim();
    state.directoryTimer = setTimeout(() => loadDirectory(0), 200);
  });
  root.querySelector("#directory-prev").addEventListener("click", () => {
    if (state.directoryPage > 0) loadDirectory(state.directoryPage - 1);
  });
  root.querySelector("#directory-next").addEventListener("click", () => {
    if (state.directoryHasMore) loadDirectory(state.directoryPage + 1);
  });
  root.querySelector("#back-to-dashboard").addEventListener("click", () => switchView("dashboard"));
  root.querySelector("#mobile-toggle-about").addEventListener("click", () => switchView(state.view === "about" ? "dashboard" : "about"));
  const search = root.querySelector("#stock-search");
  search.addEventListener("input", () => {
    clearTimeout(state.searchTimer);
    const term = search.value.trim();
    if (!term) return hideSuggestions();
    state.searchTimer = setTimeout(() => suggest(term), 250);
  });
  search.addEventListener("keydown", (event) => {
    if (event.key === "Escape") hideSuggestions();
    if (event.key === "Enter") {
      const first = root.querySelector("#search-results [data-suggestion]");
      if (first) { event.preventDefault(); selectStock(first.dataset.suggestion); }
      else if (/^\d{6}(?:\.SZ)?$/i.test(search.value.trim())) selectStock(search.value.trim().slice(0, 6));
    }
  });
  root.querySelector("#search-results").addEventListener("click", (event) => {
    const button = event.target.closest("[data-suggestion]");
    if (button) selectStock(button.dataset.suggestion);
  });
  document.addEventListener("click", (event) => {
    if (!event.target.closest(".search-box")) hideSuggestions();
  });
}

function switchView(view) {
  state.view = view;
  root.querySelector("#dashboard-view").hidden = view !== "dashboard";
  root.querySelector("#about-view").hidden = view !== "about";
  root.querySelectorAll("[data-view]").forEach((item) =>
    item.classList.toggle("active", item.dataset.view === view)
  );
  root.querySelector("#mobile-toggle-about").textContent = view === "about" ? "返回行情" : "数据说明";
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function hideSuggestions() {
  root.querySelector("#search-results").hidden = true;
}

async function suggest(term) {
  const serial = ++state.searchRequest;
  const box = root.querySelector("#search-results");
  box.hidden = false;
  box.innerHTML = '<div class="search-message">正在搜索…</div>';
  try {
    const data = await api("/api/instruments?q=" + encodeURIComponent(term) + "&limit=8");
    if (serial !== state.searchRequest || root.querySelector("#stock-search").value.trim() !== term) return;
    box.innerHTML = data.items.length ? data.items.map((item) =>
      '<button class="suggest-item" data-suggestion="' + escapeHtml(item.symbol) + '"><span class="suggest-code">' +
      escapeHtml(item.symbol) + '</span><span class="suggest-name">' +
      escapeHtml(item.current_name || "未命名证券") + '</span><span class="suggest-arrow">↗</span></button>'
    ).join("") : '<div class="search-message">没有找到匹配的股票</div>';
  } catch {
    if (serial === state.searchRequest) box.innerHTML = '<div class="search-message">搜索失败，请检查本地 API</div>';
  }
}

async function selectStock(code) {
  const serial = ++state.stockRequest;
  state.selected = code;
  state.instrument = null;
  state.bars = [];
  state.pages = [];
  state.pageIndex = 0;
  state.hasMore = false;
  state.nextEnd = null;
  state.loadingOlder = false;
  state.range = "3M";
  state.maByDate = new Map();
  root.querySelector("#daily-details-rows").innerHTML =
    '<tr><td colspan="9" class="empty-row">正在读取日线…</td></tr>';
  root.querySelector("#stock-search").value = "";
  hideSuggestions();
  switchView("dashboard");
  root.querySelectorAll("[data-code]").forEach((item) =>
    item.classList.toggle("selected", item.dataset.code === code)
  );
  root.querySelectorAll("[data-range]").forEach((item) =>
    item.classList.toggle("active", item.dataset.range === "3M")
  );
  root.querySelector("#selected-name").textContent = "加载中…";
  root.querySelector("#selected-symbol").textContent = code + ".SZ";
  root.querySelector("#chart").innerHTML = '<div class="chart-empty">正在加载 ' + escapeHtml(code) + ' 的日线数据…</div>';
  root.querySelector("#hover-details").textContent = "正在读取…";
  updateHistoryNavigation();
  try {
    const [instrument, history] = await Promise.all([
      api("/api/instruments/" + encodeURIComponent(code)),
      api("/api/instruments/" + encodeURIComponent(code) + "/daily?limit=750"),
    ]);
    if (serial !== state.stockRequest) return;
    state.instrument = instrument;
    state.bars = history.bars || [];
    state.pages = state.bars.length ? [state.bars] : [];
    state.hasMore = Boolean(history.has_more);
    state.nextEnd = history.next_end || null;
    renderStock();
    renderChart();
  } catch (error) {
    if (serial !== state.stockRequest) return;
    root.querySelector("#selected-name").textContent = "无法读取股票";
    root.querySelector("#latest-close").textContent = "—";
    root.querySelector("#bar-count").textContent = "—";
    root.querySelector("#chart").innerHTML = '<div class="chart-empty">暂时无法读取这只股票：' +
      escapeHtml(error.message) + '</div>';
    root.querySelector("#hover-details").textContent = "请确认数据库与后端 API 已启动";
    root.querySelector("#daily-details-rows").innerHTML =
      '<tr><td colspan="9" class="empty-row">日线读取失败</td></tr>';
    updateHistoryNavigation();
  }
}

function setHistoryRange(range) {
  state.range = range;
  root.querySelectorAll("[data-range]").forEach((item) =>
    item.classList.toggle("active", item.dataset.range === state.range)
  );
}

function updateHistoryNavigation(note = "") {
  const older = root.querySelector("#history-older");
  const newer = root.querySelector("#history-newer");
  const pageCount = state.pages.length;
  older.disabled = state.loadingOlder || !pageCount ||
    (state.pageIndex + 1 >= pageCount && (!state.hasMore || !state.nextEnd));
  newer.disabled = state.loadingOlder || state.pageIndex === 0;
  older.textContent = state.loadingOlder ? "正在加载…" : "← 更早 750 条";
  root.querySelector("#history-status").textContent = note || (pageCount
    ? "第 " + (state.pageIndex + 1) + " 段 · 已加载 " +
      state.pages.reduce((sum, page) => sum + page.length, 0).toLocaleString("zh-CN") +
      " 条" + (state.pageIndex + 1 < pageCount || state.hasMore
        ? " · 可继续向前查看" : " · 已到最早记录")
    : "当前股票暂无历史数据");
}

async function loadOlder() {
  if (state.loadingOlder || !state.pages.length) return;
  if (state.pageIndex + 1 < state.pages.length) {
    state.pageIndex += 1;
    setHistoryRange("ALL");
    renderChart();
    return;
  }
  if (!state.hasMore || !state.nextEnd) return;

  const serial = state.stockRequest;
  const code = state.selected;
  state.loadingOlder = true;
  updateHistoryNavigation();
  let errorNote = "";
  try {
    const history = await api("/api/instruments/" + encodeURIComponent(code) +
      "/daily?limit=750&end=" + encodeURIComponent(state.nextEnd));
    if (serial !== state.stockRequest) return;
    const older = history.bars || [];
    if (!older.length) {
      state.hasMore = false;
      state.nextEnd = null;
      updateHistoryNavigation("没有更多已入库的历史行情");
      return;
    }
    state.pages.push(older);
    state.hasMore = Boolean(history.has_more);
    state.nextEnd = history.next_end || null;
    state.pageIndex += 1;
    setHistoryRange("ALL");
    root.querySelector("#bar-count").textContent = state.pages.reduce(
      (sum, page) => sum + page.length, 0
    ).toLocaleString("zh-CN");
    renderChart();
  } catch (error) {
    if (serial === state.stockRequest) {
      errorNote = "加载失败：" + error.message;
    }
  } finally {
    if (serial === state.stockRequest) {
      state.loadingOlder = false;
      updateHistoryNavigation(errorNote);
    }
  }
}

function showNewer() {
  if (state.loadingOlder || state.pageIndex === 0) return;
  state.pageIndex -= 1;
  setHistoryRange("ALL");
  renderChart();
}

function renderStock() {
  const item = state.instrument;
  const last = state.bars.at(-1);
  root.querySelector("#selected-name").textContent = item.current_name || "未命名证券";
  root.querySelector("#selected-symbol").textContent = item.symbol + ".SZ";
  root.querySelector("#selected-industry").textContent = [item.board, item.industry].filter(Boolean).join(" · ") || "深市证券";
  root.querySelector("#latest-close").textContent = last ? price(last.close) : "—";
  root.querySelector("#latest-close-date").textContent = last?.trade_date || "暂无日线";
  const pct = last && number(last.close) !== null && number(last.pre_close) > 0
    ? (Number(last.close) / Number(last.pre_close) - 1) * 100 : last?.pct_change;
  const changeElement = root.querySelector("#latest-change");
  changeElement.textContent = pct === null || pct === undefined ? "最近交易日涨跌：—" : "最近交易日 " + percent(pct);
  changeElement.className = "metric-foot-change " + direction(pct, 0);
  root.querySelector("#bar-count").textContent = state.pages.reduce(
    (sum, page) => sum + page.length, 0
  ).toLocaleString("zh-CN");
  root.querySelector("#source-tag").textContent = last?.selected_source || "暂无来源";
  root.querySelector("#chart-title").textContent = (item.current_name || item.symbol) + " · 日 K 线";
  root.querySelector("#chart-subtitle").textContent = item.symbol + ".SZ / 未复权历史行情";
}

function visibleBars() {
  const page = state.pages[state.pageIndex] || [];
  const last = page.at(-1)?.trade_date;
  if (!last || state.range === "ALL") return page;
  const days = { "1M": 30, "3M": 90, "6M": 180, "1Y": 365 }[state.range];
  const from = new Date(last + "T00:00:00Z");
  from.setUTCDate(from.getUTCDate() - days);
  const cutoff = from.toISOString().slice(0, 10);
  return page.filter((bar) => bar.trade_date >= cutoff);
}

function renderDailyRows(bars) {
  const selected = bars.slice(-20).reverse();
  root.querySelector("#daily-details-range").textContent = bars.length
    ? "当前图表区间 " + bars.length + " 条 · 显示最近 " + selected.length + " 条"
    : "当前图表区间没有已入库日线";
  root.querySelector("#daily-details-rows").innerHTML = selected.length ? selected.map((bar) => {
    const preClose = number(bar.pre_close);
    const close = number(bar.close);
    const pct = preClose !== null && preClose > 0 && close !== null
      ? (close / preClose - 1) * 100 : bar.pct_change;
    return '<tr><td class="num strong">' + escapeHtml(bar.trade_date) +
      '</td><td class="num">' + price(bar.open) +
      '</td><td class="num">' + price(bar.high) +
      '</td><td class="num">' + price(bar.low) +
      '</td><td class="num strong">' + price(bar.close) +
      '</td><td class="num ' + direction(pct, 0) + '">' + percent(pct) +
      '</td><td class="num">' + amount(bar.volume_shares) +
      '</td><td class="num">' + amount(bar.turnover_cny) +
      '</td><td><span class="table-source">' + escapeHtml(bar.selected_source || "—") +
      '</span></td></tr>';
  }).join("") : '<tr><td colspan="9" class="empty-row">此区间暂无日线数据</td></tr>';
}

function movingAverages() {
  // Include already cached older pages when available, to maintain MA continuity
  // across page boundaries without making extra requests.
  const older = state.pages.slice(state.pageIndex + 1).reverse().flat();
  const current = state.pages[state.pageIndex] || [];
  const history = older.concat(current);
  const result = new Map();
  const periods = [5, 10, 20];
  for (let i = 0; i < history.length; i += 1) {
    const averages = {};
    for (const period of periods) {
      if (i + 1 < period) { averages[period] = null; continue; }
      const values = history.slice(i + 1 - period, i + 1).map((bar) => number(bar.close));
      averages[period] = values.every((value) => value !== null && Number.isFinite(value) && value > 0)
        ? values.reduce((sum, value) => sum + value, 0) / period : null;
    }
    result.set(history[i].trade_date, averages);
  }
  return result;
}

function showBarDetails(bar) {
  root.querySelector("#hover-details").innerHTML = '<span class="hover-date">' + escapeHtml(bar.trade_date) +
    '</span><span>开 <b>' + price(bar.open) + '</b></span><span>高 <b>' + price(bar.high) +
    '</b></span><span>低 <b>' + price(bar.low) + '</b></span><span>收 <b>' +
    price(bar.close) + '</b></span><span>成交量 <b>' + amount(bar.volume_shares, "股") +
    '</b></span><span class="source-label">' + escapeHtml(bar.selected_source || "未知来源") + '</span>' +
    [5, 10, 20].filter((period) => state.maEnabled.has(period)).map((period) =>
      '<span class="ma-detail ma-detail-' + period + '">MA' + period + ' <b>' +
      price(state.maByDate.get(bar.trade_date)?.[period]) + '</b></span>'
    ).join("");
}

function renderChart() {
  updateHistoryNavigation();
  const viewport = root.querySelector("#chart-viewport");
  const chart = root.querySelector("#chart");
  const bars = visibleBars();
  renderDailyRows(bars);
  state.maByDate = movingAverages();
  root.querySelector("#chart-range").textContent = bars.length
    ? bars[0].trade_date + " — " + bars.at(-1).trade_date + " · " + bars.length + " 条"
    : "当前时间范围暂无数据";
  if (!bars.length) {
    chart.innerHTML = '<div class="chart-empty">当前时间范围没有已入库的日线记录</div>';
    root.querySelector("#hover-details").textContent = "请选择其他股票或时间范围";
    return;
  }
  const valid = bars.filter((bar) => ["open", "high", "low", "close"].every((key) =>
    number(bar[key]) !== null && Number.isFinite(Number(bar[key])) && Number(bar[key]) > 0
  ));
  if (!valid.length) {
    chart.innerHTML = '<div class="chart-empty">此时间范围尚无可绘制的价格记录</div>';
    root.querySelector("#hover-details").textContent = "部分日期可能停牌或价格为空";
    return;
  }
  const marginL = 14, marginR = 78, top = 22, bottom = 262, volumeTop = 284, volumeBottom = 351;
  const width = Math.max(980, valid.length * 10 + marginL + marginR);
  const plotWidth = width - marginL - marginR;
  const step = plotWidth / valid.length;
  const bodyWidth = Math.max(3, Math.min(13, step * 0.64));
  const maValues = valid.flatMap((bar) =>
    [...state.maEnabled].map((period) => state.maByDate.get(bar.trade_date)?.[period])
      .filter((value) => value !== null && value !== undefined && Number.isFinite(value))
  );
  let low = Math.min(...valid.map((bar) => Number(bar.low)), ...maValues);
  let high = Math.max(...valid.map((bar) => Number(bar.high)), ...maValues);
  const margin = Math.max((high - low) * 0.08, high * 0.002, 0.01);
  low -= margin;
  high += margin;
  const scaleY = (value) => top + ((high - value) / (high - low)) * (bottom - top);
  const maxVolume = Math.max(1, ...valid.map((bar) => Number(bar.volume_shares) || 0));
  const shapes = [];
  for (let tick = 0; tick <= 4; tick += 1) {
    const y = top + (bottom - top) * tick / 4;
    const level = high - (high - low) * tick / 4;
    shapes.push('<line x1="' + marginL + '" y1="' + y + '" x2="' + (width - marginR + 10) +
      '" y2="' + y + '" class="grid-line"/>');
    shapes.push('<text x="' + (width - marginR + 20) + '" y="' + (y + 4) +
      '" class="axis-label">' + level.toFixed(2) + '</text>');
  }
  shapes.push('<text x="' + (width - marginR + 20) + '" y="' + (volumeTop + 9) +
    '" class="axis-label">成交量</text>');
  const labelEvery = Math.max(1, Math.ceil(96 / step));
  valid.forEach((bar, i) => {
    const x = marginL + step * (i + 0.5);
    const open = Number(bar.open), close = Number(bar.close);
    const up = close >= open;
    const color = up ? "#e5484d" : "#23a486";
    const upper = scaleY(Number(bar.high)), lower = scaleY(Number(bar.low));
    const bodyTop = Math.min(scaleY(open), scaleY(close));
    const bodyHeight = Math.max(1.8, Math.abs(scaleY(open) - scaleY(close)));
    const volume = Math.max(0, Number(bar.volume_shares) || 0);
    const volumeHeight = volume / maxVolume * (volumeBottom - volumeTop);
    shapes.push('<g class="candle-group" data-candle="' + i + '"><line x1="' + x + '" y1="' +
      upper + '" x2="' + x + '" y2="' + lower + '" stroke="' + color +
      '" stroke-width="1.5"/><rect x="' + (x - bodyWidth / 2) + '" y="' + bodyTop +
      '" width="' + bodyWidth + '" height="' + bodyHeight + '" rx=".7" fill="' + color +
      '"/><rect x="' + (x - bodyWidth / 2) + '" y="' + (volumeBottom - volumeHeight) +
      '" width="' + bodyWidth + '" height="' + volumeHeight + '" rx=".5" fill="' + color +
      '" opacity=".68"/><rect x="' + (x - step / 2) +
      '" y="' + top + '" width="' + step + '" height="' + (volumeBottom - top) +
      '" fill="transparent" class="candle-hit"/></g>');
    if (i % labelEvery === 0 || i === valid.length - 1) {
      shapes.push('<text x="' + x + '" y="378" class="date-label" text-anchor="middle">' +
        escapeHtml(bar.trade_date.slice(5)) + '</text>');
    }
  });
  for (const period of [5, 10, 20]) {
    if (!state.maEnabled.has(period)) continue;
    const segments = [];
    let points = [];
    const flush = () => {
      if (points.length >= 2) segments.push('<polyline class="ma-path ma-path-' + period +
        '" points="' + points.join(" ") + '"/>');
      points = [];
    };
    valid.forEach((bar, i) => {
      const average = state.maByDate.get(bar.trade_date)?.[period];
      if (average === null || average === undefined) { flush(); return; }
      points.push((marginL + step * (i + 0.5)).toFixed(2) + "," + scaleY(average).toFixed(2));
    });
    flush();
    shapes.push(...segments);
  }
  chart.innerHTML = '<svg class="candle-svg" viewBox="0 0 ' + width + ' 393" width="' +
    width + '" height="393" role="img" aria-label="' + escapeHtml(state.selected) +
    ' 未复权日 K 线与成交量">' + shapes.join("") + '</svg>';
  showBarDetails(valid.at(-1));
  chart.onpointermove = (event) => {
    const group = event.target.closest("[data-candle]");
    if (!group) return;
    const index = Number(group.dataset.candle);
    showBarDetails(valid[index]);
    chart.querySelector(".candle-group.is-hovered")?.classList.remove("is-hovered");
    group.classList.add("is-hovered");
  };
  chart.onpointerleave = () => {
    chart.querySelector(".candle-group.is-hovered")?.classList.remove("is-hovered");
    showBarDetails(valid.at(-1));
  };
  viewport.scrollLeft = viewport.scrollWidth;
}

async function loadDirectory(page = 0) {
  const serial = ++state.directoryRequest;
  const prev = root.querySelector("#directory-prev");
  const next = root.querySelector("#directory-next");
  const info = root.querySelector("#directory-page");
  const tbody = root.querySelector("#directory-rows");
  prev.disabled = true;
  next.disabled = true;
  info.textContent = "读取第 " + (page + 1) + " 页…";
  try {
    const q = state.directoryQuery;
    const data = await api("/api/instruments?limit=21&offset=" + (page * 20) +
      "&q=" + encodeURIComponent(q));
    if (serial !== state.directoryRequest) return;
    state.directoryPage = page;
    state.directoryHasMore = data.items.length > 20;
    const rows = data.items.slice(0, 20);
    tbody.innerHTML = rows.length ? rows.map((item) =>
      '<tr><td><button class="stock-cell" data-directory-symbol="' + escapeHtml(item.symbol) +
      '"><span class="stock-avatar">' + escapeHtml(item.symbol.slice(0, 2)) +
      '</span><span><b>' + escapeHtml(item.current_name || "未命名证券") +
      '</b><small>' + escapeHtml(item.symbol) + '.SZ</small></span></button></td><td>' +
      escapeHtml(item.board || "—") + '</td><td class="num">' +
      escapeHtml(item.list_date || "—") + '</td><td><span class="table-source">' +
      escapeHtml(item.status || "UNKNOWN") + '</span></td><td><button class="row-go" data-directory-symbol="' +
      escapeHtml(item.symbol) + '" aria-label="查看 ' + escapeHtml(item.symbol) +
      '">↗</button></td></tr>'
    ).join("") : '<tr><td colspan="5" class="empty-row">没有符合条件的股票</td></tr>';
    info.textContent = "第 " + (page + 1) + " 页 · " + rows.length + " 只";
    prev.disabled = page === 0;
    next.disabled = !state.directoryHasMore;
  } catch (error) {
    if (serial !== state.directoryRequest) return;
    tbody.innerHTML = '<tr><td colspan="5" class="empty-row">股票目录读取失败：' +
      escapeHtml(error.message) + '</td></tr>';
    info.textContent = "读取失败";
    prev.disabled = true;
    next.disabled = true;
  }
}

async function loadMarket() {
  try {
    const result = await api("/api/market/overview?limit=30");
    state.market = result;
    root.querySelector("#last-date").textContent = result.as_of ? "截至 " + result.as_of : "尚无行情";
    root.querySelector("#market-subtitle").textContent = result.as_of
      ? result.as_of + " · 数据库最近行情日 · " + result.items.length + " 只已入库证券"
      : "数据库尚未有历史日线";
    root.querySelector("#market-rows").innerHTML = result.items.length ? result.items.map((row) =>
      '<tr><td><button class="stock-cell" data-symbol="' + escapeHtml(row.symbol) +
      '"><span class="stock-avatar">' + escapeHtml(row.symbol.slice(0, 2)) +
      '</span><span><b>' + escapeHtml(row.current_name || row.symbol) +
      '</b><small>' + escapeHtml(row.symbol) + '.SZ</small></span></button></td><td class="num strong">' +
      price(row.close) + '</td><td class="num ' + direction(row.pct_change, 0) + '">' +
      percent(row.pct_change) + '</td><td class="num">' +
      amount(row.turnover_cny, "元") + '</td><td><span class="table-source">' +
      escapeHtml(row.selected_source) + '</span></td><td><button class="row-go" data-symbol="' +
      escapeHtml(row.symbol) + '" aria-label="查看 ' + escapeHtml(row.symbol) +
      '">↗</button></td></tr>'
    ).join("") : '<tr><td colspan="6" class="empty-row">当前数据库没有可展示的行情</td></tr>';
  } catch (error) {
    root.querySelector("#last-date").textContent = "API 未连接";
    root.querySelector(".status-orb").classList.add("offline");
    root.querySelector(".market-dot").classList.add("offline");
    root.querySelector("#market-rows").innerHTML =
      '<tr><td colspan="6" class="empty-row">无法读取数据库行情：' + escapeHtml(error.message) + '</td></tr>';
    const notice = root.querySelector("#connection-error");
    notice.hidden = false;
    notice.textContent = "无法连接行情 API。请先启动 PostgreSQL 和 backend 服务（127.0.0.1:8000），再刷新页面。";
  }
}

shell();
loadMarket();
loadDirectory();
selectStock(state.selected);
