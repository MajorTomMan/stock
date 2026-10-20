<script setup>
import { computed, nextTick, ref, watch } from "vue";
import { amount, changePercent, direction, number, percent, price } from "../format.js";

const props = defineProps({
  symbol: { type: String, required: true },
  name: { type: String, default: "" },
  bars: { type: Array, default: () => [] },
  // Chronologically ordered cached rows from older pages through the active page.
  history: { type: Array, default: () => [] },
  pageIndex: { type: Number, default: 0 },
  loadedCount: { type: Number, default: 0 },
  hasMore: { type: Boolean, default: false },
  canOlder: { type: Boolean, default: false },
  canNewer: { type: Boolean, default: false },
  loadingOlder: { type: Boolean, default: false },
  historyNote: { type: String, default: "" },
});
const emit = defineEmits(["older", "newer"]);
const range = ref(props.pageIndex === 0 ? "3M" : "ALL");
const enabled = ref([5, 10, 20]);
const hovered = ref(null);
const viewport = ref(null);
const periods = [5, 10, 20];
const rangeOptions = [["1M", "1月"], ["3M", "3月"], ["6M", "6月"], ["1Y", "1年"], ["ALL", "当前段全部"]];
const colors = { 5: "#d49a30", 10: "#8d7ccd", 20: "#467dbd" };

const visibleBars = computed(() => {
  const rows = props.bars;
  const end = rows.at(-1)?.trade_date;
  if (!end || range.value === "ALL") return rows;
  const days = { "1M": 30, "3M": 90, "6M": 180, "1Y": 365 }[range.value];
  const cutoff = new Date(end + "T00:00:00Z");
  cutoff.setUTCDate(cutoff.getUTCDate() - days);
  const from = cutoff.toISOString().slice(0, 10);
  return rows.filter((bar) => bar.trade_date >= from);
});
const detailRows = computed(() => visibleBars.value.slice(-20).reverse());

// Calculate only from cached real bars. Null or invalid close breaks the
// corresponding MA window; do not interpolate suspended or missing sessions.
const averages = computed(() => {
  const result = new Map();
  const rows = props.history;
  for (let i = 0; i < rows.length; i += 1) {
    const data = {};
    for (const period of periods) {
      if (i + 1 < period) { data[period] = null; continue; }
      const values = rows.slice(i + 1 - period, i + 1).map((bar) => number(bar.close));
      data[period] = values.every((value) => value !== null && value > 0)
        ? values.reduce((sum, value) => sum + value, 0) / period : null;
    }
    result.set(rows[i].trade_date, data);
  }
  return result;
});
const validBars = computed(() => visibleBars.value.filter((bar) =>
  ["open", "high", "low", "close"].every((key) => number(bar[key]) !== null && number(bar[key]) > 0)
));
const chart = computed(() => {
  const rows = validBars.value;
  if (!rows.length) return null;
  const left = 14, right = 78, top = 22, bottom = 262, volumeTop = 284, volumeBottom = 351;
  const width = Math.max(980, rows.length * 10 + left + right);
  const step = (width - left - right) / rows.length;
  const bodyWidth = Math.max(3, Math.min(13, step * 0.64));
  const maValues = rows.flatMap((row) => enabled.value.map((period) =>
    averages.value.get(row.trade_date)?.[period]).filter((value) => value != null));
  const minPrice = Math.min(...rows.map((row) => Number(row.low)), ...maValues);
  const maxPrice = Math.max(...rows.map((row) => Number(row.high)), ...maValues);
  const margin = Math.max((maxPrice - minPrice) * 0.08, maxPrice * 0.002, 0.01);
  const low = minPrice - margin, high = maxPrice + margin;
  const y = (value) => top + ((high - Number(value)) / (high - low)) * (bottom - top);
  const maxVolume = Math.max(1, ...rows.map((row) => number(row.volume_shares) || 0));
  const candles = rows.map((bar, index) => {
    const x = left + step * (index + 0.5);
    const open = number(bar.open), close = number(bar.close);
    const volume = Math.max(0, number(bar.volume_shares) || 0);
    const volHeight = volume / maxVolume * (volumeBottom - volumeTop);
    return { bar, index, x, upper: y(bar.high), lower: y(bar.low),
      bodyTop: Math.min(y(open), y(close)), bodyHeight: Math.max(1.8, Math.abs(y(open) - y(close))),
      volumeY: volumeBottom - volHeight, volHeight, bodyWidth, step,
      color: close >= open ? "#e5484d" : "#23a486" };
  });
  const axes = Array.from({ length: 5 }, (_, i) => ({
    y: top + (bottom - top) * i / 4,
    price: (high - (high - low) * i / 4).toFixed(2),
  }));
  const labelEvery = Math.max(1, Math.ceil(96 / step));
  const paths = enabled.value.flatMap((period) => {
    const segments = [];
    let points = [];
    const flush = () => { if (points.length >= 2) segments.push(points.join(" ")); points = []; };
    candles.forEach((item) => {
      const value = averages.value.get(item.bar.trade_date)?.[period];
      if (value == null) { flush(); return; }
      points.push(item.x.toFixed(2) + "," + y(value).toFixed(2));
    });
    flush();
    return segments.map((points, index) => ({ period, key: period + "-" + index, points, color: colors[period] }));
  });
  return { width, left, right, top, bottom, volumeTop, volumeBottom,
    candles, axes, labelEvery, paths };
});
const activeBar = computed(() => hovered.value || validBars.value.at(-1) || null);
const dateRange = computed(() => visibleBars.value.length
  ? visibleBars.value[0].trade_date + " — " + visibleBars.value.at(-1).trade_date +
    " · " + visibleBars.value.length + " 条" : "当前时间范围暂无数据");

function toggle(period) {
  enabled.value = enabled.value.includes(period)
    ? enabled.value.filter((value) => value !== period) : [...enabled.value, period];
}
watch([range, () => props.bars], async () => {
  hovered.value = null;
  await nextTick();
  if (viewport.value) viewport.value.scrollLeft = viewport.value.scrollWidth;
}, { flush: "post", immediate: true });
</script>

<template>
  <section class="content-card chart-card">
    <div class="section-heading">
      <div>
        <div class="section-eyebrow">PRICE &amp; VOLUME</div>
        <div class="section-title">
          <h2>{{ name || symbol }} · 日 K 线</h2>
          <span class="section-subtitle">{{ symbol }}.SZ / 未复权历史行情</span>
        </div>
      </div>
      <div class="range-buttons" role="group" aria-label="图表时间范围">
        <button v-for="[value, label] in rangeOptions" :key="value"
          :class="{ active: range === value }" @click="range = value">{{ label }}</button>
      </div>
    </div>
    <div class="chart-legend">
      <span><i class="legend-candle"></i> 未复权价格 (CNY)</span>
      <span><i class="legend-volume"></i> 成交量 (股)</span>
      <span class="legend-hint">横向滚动查看更早日期 · 悬停查看明细</span>
    </div>
    <div class="ma-toolbar">
      <span>移动平均线</span>
      <button v-for="period in periods" :key="period" type="button"
        class="ma-toggle" :class="['ma-' + ({ 5:'five', 10:'ten', 20:'twenty' }[period]), { active: enabled.includes(period) }]"
        :aria-pressed="enabled.includes(period)" @click="toggle(period)">
        <i></i> MA{{ period }}
      </button>
      <span class="ma-caption">按已加载收盘价计算 · 样本不足时不显示</span>
    </div>
    <div class="hover-details" aria-live="polite">
      <template v-if="activeBar">
        <span class="hover-date">{{ activeBar.trade_date }}</span>
        <span>开 <b>{{ price(activeBar.open) }}</b></span>
        <span>高 <b>{{ price(activeBar.high) }}</b></span>
        <span>低 <b>{{ price(activeBar.low) }}</b></span>
        <span>收 <b>{{ price(activeBar.close) }}</b></span>
        <span>成交量 <b>{{ amount(activeBar.volume_shares, "股") }}</b></span>
        <span class="source-label">{{ activeBar.selected_source || "未知来源" }}</span>
        <span v-for="period in enabled" :key="period" class="ma-detail" :class="'ma-detail-' + period">
          MA{{ period }} <b>{{ price(averages.get(activeBar.trade_date)?.[period]) }}</b>
        </span>
      </template>
      <span v-else>当前时间范围暂无可绘制的价格记录</span>
    </div>
    <div ref="viewport" class="chart-viewport">
      <div v-if="!visibleBars.length" class="chart-empty">当前时间范围没有已入库的日线记录</div>
      <div v-else-if="!chart" class="chart-empty">此时间范围尚无可绘制的价格记录（可能停牌或价格为空）</div>
      <svg v-else class="candle-svg" :width="chart.width" height="393"
        :viewBox="'0 0 ' + chart.width + ' 393'" role="img"
        :aria-label="symbol + ' 未复权日 K 线与成交量'">
        <g v-for="(axis, index) in chart.axes" :key="'axis-' + index">
          <line :x1="chart.left" :y1="axis.y" :x2="chart.width - chart.right + 10"
            :y2="axis.y" class="grid-line"/>
          <text :x="chart.width - chart.right + 20" :y="axis.y + 4" class="axis-label">{{ axis.price }}</text>
        </g>
        <text :x="chart.width - chart.right + 20" :y="chart.volumeTop + 9" class="axis-label">成交量</text>
        <g v-for="item in chart.candles" :key="item.bar.trade_date" class="candle-group"
          :class="{ 'is-hovered': activeBar?.trade_date === item.bar.trade_date }"
          @pointerenter="hovered = item.bar" @click="hovered = item.bar">
          <line :x1="item.x" :y1="item.upper" :x2="item.x" :y2="item.lower"
            :stroke="item.color" stroke-width="1.5"/>
          <rect :x="item.x - item.bodyWidth / 2" :y="item.bodyTop"
            :width="item.bodyWidth" :height="item.bodyHeight" rx=".7" :fill="item.color"/>
          <rect :x="item.x - item.bodyWidth / 2" :y="item.volumeY"
            :width="item.bodyWidth" :height="item.volHeight" rx=".5" :fill="item.color" opacity=".68"/>
          <rect :x="item.x - item.step / 2" :y="chart.top" :width="item.step"
            :height="chart.volumeBottom - chart.top" fill="transparent" class="candle-hit"/>
          <text v-if="item.index % chart.labelEvery === 0 || item.index === chart.candles.length - 1"
            :x="item.x" y="378" text-anchor="middle" class="date-label">{{ item.bar.trade_date.slice(5) }}</text>
        </g>
        <polyline v-for="path in chart.paths" :key="path.key" class="ma-path"
          :stroke="path.color" :points="path.points"/>
      </svg>
    </div>
    <div class="chart-footer"><span>{{ dateRange }}</span><span>↑ 红涨 &nbsp; ↓ 绿跌</span></div>
    <div class="history-navigation">
      <button :disabled="loadingOlder || !canOlder" @click="emit('older')">
        {{ loadingOlder ? "正在加载…" : "← 更早 750 条" }}
      </button>
      <span id="history-status" aria-live="polite">{{ historyNote || ("第 " + (pageIndex + 1) +
        " 段 · 已加载 " + loadedCount.toLocaleString("zh-CN") + " 条" +
        (hasMore ? " · 仍有更早数据" : "")) }}</span>
      <button :disabled="loadingOlder || !canNewer" @click="emit('newer')">较新 750 条 →</button>
    </div>
  </section>
  <section class="content-card list-card">
    <div class="section-heading">
      <div><div class="section-eyebrow">DAILY DETAILS</div>
        <div class="section-title"><h2>日线明细</h2>
          <span class="section-subtitle">当前图表区间 {{ visibleBars.length }} 条 · 显示最近 {{ detailRows.length }} 条</span>
        </div>
      </div>
      <span class="table-note">全部数值来自数据库 · 未复权</span>
    </div>
    <div class="table-wrap">
      <table class="stocks-table daily-details-table">
        <thead><tr><th>日期</th><th>开盘</th><th>最高</th><th>最低</th><th>收盘</th><th>涨跌幅</th><th>成交量（股）</th><th>成交额（元）</th><th>来源</th></tr></thead>
        <tbody>
          <tr v-if="!detailRows.length"><td colspan="9" class="empty-row">此区间暂无日线数据</td></tr>
          <tr v-for="bar in detailRows" :key="bar.trade_date">
            <td class="num strong">{{ bar.trade_date }}</td>
            <td class="num">{{ price(bar.open) }}</td>
            <td class="num">{{ price(bar.high) }}</td>
            <td class="num">{{ price(bar.low) }}</td>
            <td class="num strong">{{ price(bar.close) }}</td>
            <td class="num" :class="direction(changePercent(bar))">{{ percent(changePercent(bar)) }}</td>
            <td class="num">{{ amount(bar.volume_shares) }}</td>
            <td class="num">{{ amount(bar.turnover_cny) }}</td>
            <td><span class="table-source">{{ bar.selected_source || "—" }}</span></td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
