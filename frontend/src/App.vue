<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { api } from "./api.js";
import { amount, changePercent, direction, percent, price } from "./format.js";
import CandleChart from "./components/CandleChart.vue";
import MarketSnapshot from "./components/MarketSnapshot.vue";
import StockDirectory from "./components/StockDirectory.vue";

const view = ref("dashboard");
const selected = ref("000001");
const instrument = ref(null);
const pages = ref([]);
const pageIndex = ref(0);
const hasMore = ref(false);
const nextEnd = ref(null);
const loadingStock = ref(false);
const loadingOlder = ref(false);
const stockError = ref("");
const historyNote = ref("");
const market = ref(null);
const marketError = ref("");
const searchQuery = ref("");
const suggestions = ref([]);
const suggestionsVisible = ref(false);
const searchLoading = ref(false);
const searchError = ref("");
const quickStocks = [
  { symbol: "000001", name: "平安银行" },
  { symbol: "300001", name: "特锐德" },
  { symbol: "000004", name: "000004" },
];
let stockSerial = 0, searchSerial = 0, searchTimer;

const latestPage = computed(() => pages.value[0] || []);
const latest = computed(() => latestPage.value.at(-1) || null);
const currentPage = computed(() => pages.value[pageIndex.value] || []);
const loadedCount = computed(() => pages.value.reduce((sum, group) => sum + group.length, 0));
const olderAvailable = computed(() => pages.value.length > 0 && (
  pageIndex.value + 1 < pages.value.length || (hasMore.value && Boolean(nextEnd.value))
));
const cachedHistory = computed(() => pages.value.slice(pageIndex.value + 1).reverse().flat()
  .concat(currentPage.value));
const lastChange = computed(() => changePercent(latest.value));
const showSearch = computed(() => suggestionsVisible.value &&
  Boolean(searchQuery.value.trim()));

function navigate(next) {
  view.value = next;
  window.scrollTo({ top: 0, behavior: "smooth" });
}
async function loadMarket() {
  try {
    market.value = await api("/api/market/overview?limit=30");
    marketError.value = "";
  } catch (error) {
    marketError.value = error.message;
  }
}
async function selectStock(code) {
  const serial = ++stockSerial;
  selected.value = code;
  instrument.value = null;
  pages.value = [];
  pageIndex.value = 0;
  hasMore.value = false;
  nextEnd.value = null;
  loadingStock.value = true;
  loadingOlder.value = false;
  stockError.value = "";
  historyNote.value = "";
  searchQuery.value = "";
  suggestionsVisible.value = false;
  suggestions.value = [];
  navigate("dashboard");
  try {
    const [info, history] = await Promise.all([
      api("/api/instruments/" + encodeURIComponent(code)),
      api("/api/instruments/" + encodeURIComponent(code) + "/daily?limit=750"),
    ]);
    if (serial !== stockSerial) return;
    instrument.value = info;
    if (history.bars?.length) pages.value = [history.bars];
    hasMore.value = Boolean(history.has_more);
    nextEnd.value = history.next_end || null;
  } catch (error) {
    if (serial === stockSerial) stockError.value = error.message;
  } finally {
    if (serial === stockSerial) loadingStock.value = false;
  }
}
async function loadOlder() {
  if (loadingOlder.value || !olderAvailable.value) return;
  if (pageIndex.value + 1 < pages.value.length) {
    pageIndex.value += 1;
    historyNote.value = "";
    return;
  }
  const serial = stockSerial;
  const code = selected.value;
  loadingOlder.value = true;
  historyNote.value = "";
  try {
    const history = await api("/api/instruments/" + encodeURIComponent(code) +
      "/daily?limit=750&end=" + encodeURIComponent(nextEnd.value));
    if (serial !== stockSerial) return;
    if (!history.bars?.length) {
      hasMore.value = false;
      nextEnd.value = null;
      historyNote.value = "数据库中没有更多历史日线";
      return;
    }
    pages.value = [...pages.value, history.bars];
    pageIndex.value += 1;
    hasMore.value = Boolean(history.has_more);
    nextEnd.value = history.next_end || null;
  } catch (error) {
    if (serial === stockSerial) historyNote.value = "读取更早行情失败：" + error.message;
  } finally {
    if (serial === stockSerial) loadingOlder.value = false;
  }
}
function showNewer() {
  if (!loadingOlder.value && pageIndex.value > 0) {
    pageIndex.value -= 1;
    historyNote.value = "";
  }
}
function dismissSuggestions(event) {
  if (!event.target.closest(".search-box")) suggestionsVisible.value = false;
}
function chooseFirst() {
  const code = suggestions.value[0]?.symbol ||
    (/^\d{6}(?:\.SZ)?$/i.test(searchQuery.value.trim())
      ? searchQuery.value.trim().slice(0, 6) : null);
  if (code) selectStock(code);
}
watch(searchQuery, (value) => {
  clearTimeout(searchTimer);
  const query = value.trim();
  const serial = ++searchSerial;
  suggestions.value = [];
  searchError.value = "";
  if (!query) { suggestionsVisible.value = false; searchLoading.value = false; return; }
  suggestionsVisible.value = true;
  searchLoading.value = true;
  searchTimer = setTimeout(async () => {
    try {
      const data = await api("/api/instruments?q=" + encodeURIComponent(query) + "&limit=8");
      if (serial !== searchSerial) return;
      suggestions.value = data.items || [];
    } catch (error) {
      if (serial === searchSerial) searchError.value = error.message;
    } finally {
      if (serial === searchSerial) searchLoading.value = false;
    }
  }, 250);
});
onMounted(() => {
  document.addEventListener("click", dismissSuggestions);
  loadMarket();
  selectStock(selected.value);
});
onUnmounted(() => {
  clearTimeout(searchTimer);
  document.removeEventListener("click", dismissSuggestions);
});
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <a href="/" class="brand" aria-label="Stockroom 首页">
        <span class="brand-icon">S<span>.</span></span>
        <span class="brand-word">stockroom<small>MARKET INTELLIGENCE</small></span>
      </a>
      <div class="sidebar-caption">工作空间</div>
      <nav class="nav-menu" aria-label="主导航">
        <button class="nav-item" :class="{ active: view === 'dashboard' }" @click="navigate('dashboard')">
          <span class="nav-icon">▦</span>行情工作台<span class="nav-arrow">›</span>
        </button>
        <button class="nav-item" :class="{ active: view === 'about' }" @click="navigate('about')">
          <span class="nav-icon">ⓘ</span>数据说明<span class="nav-arrow">›</span>
        </button>
      </nav>
      <div class="sidebar-caption watch-caption">快速查看</div>
      <div class="watch-list">
        <button v-for="stock in quickStocks" :key="stock.symbol" class="watch-item"
          :class="{ selected: selected === stock.symbol }" @click="selectStock(stock.symbol)">
          <span class="watch-dot"></span>
          <span><b>{{ stock.symbol }}</b><small>{{ stock.name }}</small></span>
          <span class="watch-chevron">↗</span>
        </button>
      </div>
      <div class="sidebar-bottom">
        <span class="status-orb" :class="{ offline: Boolean(marketError) }"></span>
        <span>本地数据库<small>历史数据 · 非实时行情</small></span>
      </div>
    </aside>

    <div class="workspace">
      <header class="topbar">
        <div class="mobile-brand">stockroom<span>.</span></div>
        <div class="search-box">
          <span class="search-icon">⌕</span>
          <input v-model="searchQuery" type="search" placeholder="搜索股票代码或名称…"
            autocomplete="off" aria-label="搜索股票" @focus="suggestionsVisible = true"
            @keydown.escape="suggestionsVisible = false" @keydown.enter.prevent="chooseFirst"/>
          <span class="search-shortcut">SZ</span>
          <div v-if="showSearch" class="search-results">
            <div v-if="searchLoading" class="search-message">正在搜索…</div>
            <div v-else-if="searchError" class="search-message">搜索失败：{{ searchError }}</div>
            <div v-else-if="!suggestions.length" class="search-message">没有找到匹配的股票</div>
            <button v-for="item in !searchLoading ? suggestions : []" :key="item.symbol"
              class="suggest-item" @click="selectStock(item.symbol)">
              <span class="suggest-code">{{ item.symbol }}</span>
              <span class="suggest-name">{{ item.current_name || "未命名证券" }}</span>
              <span class="suggest-arrow">↗</span>
            </button>
          </div>
        </div>
        <button class="mobile-about" @click="navigate(view === 'about' ? 'dashboard' : 'about')">
          {{ view === "about" ? "返回行情" : "数据说明" }}
        </button>
        <div class="topbar-right"><span class="market-dot" :class="{ offline: Boolean(marketError) }"></span>
          <span>深圳市场</span><span class="topbar-divider"></span>
          <span>{{ marketError ? "API 未连接" : market?.as_of ? "截至 " + market.as_of : "尚无行情" }}</span>
        </div>
      </header>
      <main class="main-content">
        <section v-show="view === 'dashboard'" id="dashboard-view">
          <div class="page-heading">
            <div><div class="eyebrow"><span class="eyebrow-line"></span> STOCK MARKET DASHBOARD</div>
              <h1>市场数据，一目了然<span class="heading-period">.</span></h1>
              <p>探索已入库的深市股票、历史价格与成交趋势。</p>
            </div>
            <span class="history-pill"><span class="history-dot"></span>历史行情 · 非实时</span>
          </div>
          <div v-if="marketError" class="notice">
            无法连接行情 API。请确认 PostgreSQL 和后端服务已启动：{{ marketError }}
          </div>
          <div class="overview-grid">
            <article class="metric-card">
              <div class="metric-title">当前股票 <span>01 / STOCK</span></div>
              <div class="metric-main"><strong>{{ instrument?.current_name || (loadingStock ? "加载中…" : selected) }}</strong>
                <span class="metric-code">{{ selected }}.SZ</span></div>
              <div class="metric-foot"><span>{{ [instrument?.board, instrument?.industry].filter(Boolean).join(" · ") || "深市证券" }}</span>
                <span>未复权 · 日线</span></div>
            </article>
            <article class="metric-card">
              <div class="metric-title">最近收盘 <span>02 / CLOSE</span></div>
              <div class="metric-main"><strong>{{ price(latest?.close) }}</strong><span class="metric-unit">CNY</span></div>
              <div class="metric-foot">
                <span :class="direction(lastChange)">{{ lastChange === null ? "最近交易日涨跌：—" : "最近交易日 " + percent(lastChange) }}</span>
                <span>{{ latest?.trade_date || "暂无日线" }}</span>
              </div>
            </article>
            <article class="metric-card">
              <div class="metric-title">日线记录 <span>03 / HISTORY</span></div>
              <div class="metric-main"><strong>{{ loadedCount.toLocaleString("zh-CN") }}</strong><span class="metric-unit">条</span></div>
              <div class="metric-foot"><span>当前已加载</span><span>{{ latest?.selected_source || "暂无来源" }}</span></div>
            </article>
          </div>
          <div v-if="stockError" class="notice">无法读取 {{ selected }} 的行情：{{ stockError }}</div>
          <CandleChart v-if="!loadingStock && !stockError" :key="selected + ':' + pageIndex"
            :symbol="selected" :name="instrument?.current_name || selected"
            :bars="currentPage" :history="cachedHistory" :page-index="pageIndex"
            :loaded-count="loadedCount" :has-more="hasMore" :can-older="olderAvailable"
            :can-newer="pageIndex > 0" :loading-older="loadingOlder" :history-note="historyNote"
            @older="loadOlder" @newer="showNewer"/>
          <div v-else-if="loadingStock" class="content-card chart-empty">正在读取股票详情和历史日线…</div>
          <MarketSnapshot :snapshot="market" :error="marketError" @select="selectStock"/>
          <StockDirectory @select="selectStock"/>
          <footer class="footer"><span>STOCKROOM / 深市历史数据工作台</span>
            <span>仅供研究与数据展示 · 非实时行情</span></footer>
        </section>
        <section v-show="view === 'about'" id="about-view" class="about-view">
          <div class="eyebrow"><span class="eyebrow-line"></span> ABOUT THE DATA</div>
          <h1>关于这里的数据<span class="heading-period">.</span></h1>
          <p>这个工作台只读取你本机 PostgreSQL 中已经导入的历史行情，不会直接访问外部行情服务。</p>
          <div class="about-grid">
            <article class="content-card"><span class="about-num">01</span><h2>数据来源</h2>
              <p>BaoStock 历史未复权日线及深圳证券交易所官方日快照。每条日线展示数据库选择的来源；未回填的日期不会生成模拟价格。</p>
            </article>
            <article class="content-card"><span class="about-num">02</span><h2>日期与范围</h2>
              <p>概览日期是数据库中最后一个有记录的日期，不一定是今天。K 线分段加载每段最多 750 条；“当前段全部”不代表上市以来的全部历史。</p>
            </article>
            <article class="content-card"><span class="about-num">03</span><h2>开发阶段</h2>
              <p>当前功能包括股票搜索、目录、历史日 K 线、成交量、均线和日线明细；复权与交易日历尚未接入。</p>
            </article>
          </div>
          <button class="return-button" @click="navigate('dashboard')">返回行情工作台 →</button>
        </section>
      </main>
    </div>
  </div>
</template>
