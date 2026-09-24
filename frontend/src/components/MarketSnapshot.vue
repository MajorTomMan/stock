<script setup>
import { amount, direction, percent, price } from "../format.js";

defineProps({
  snapshot: { type: Object, default: null },
  error: { type: String, default: "" },
});
const emit = defineEmits(["select"]);
</script>

<template>
  <section class="content-card list-card">
    <div class="section-heading">
      <div>
        <div class="section-eyebrow">MARKET SNAPSHOT</div>
        <div class="section-title">
          <h2>行情概览</h2>
          <span class="section-subtitle">{{ error || (snapshot?.as_of ? snapshot.as_of + " · 数据库最近行情日" : "数据库尚无日线") }}</span>
        </div>
      </div>
      <span class="table-note">按已入库股票的成交额排序</span>
    </div>
    <div class="table-wrap">
      <table class="stocks-table">
        <thead><tr><th>股票</th><th>收盘价</th><th>涨跌幅</th><th>成交额</th><th>来源</th><th></th></tr></thead>
        <tbody>
          <tr v-if="!snapshot && !error"><td colspan="6" class="empty-row">正在读取行情…</td></tr>
          <tr v-else-if="error"><td colspan="6" class="empty-row">无法读取行情：{{ error }}</td></tr>
          <tr v-else-if="!snapshot.items?.length"><td colspan="6" class="empty-row">数据库最新日期尚无行情记录</td></tr>
          <tr v-for="stock in snapshot?.items || []" :key="stock.symbol">
            <td>
              <button class="stock-cell" @click="emit('select', stock.symbol)">
                <span class="stock-avatar">{{ stock.symbol.slice(0, 2) }}</span>
                <span><b>{{ stock.current_name || stock.symbol }}</b><small>{{ stock.symbol }}.SZ</small></span>
              </button>
            </td>
            <td class="num strong">{{ price(stock.close) }}</td>
            <td class="num" :class="direction(stock.pct_change)">{{ percent(stock.pct_change) }}</td>
            <td class="num">{{ amount(stock.turnover_cny, "元") }}</td>
            <td><span class="table-source">{{ stock.selected_source }}</span></td>
            <td><button class="row-go" :aria-label="'查看 ' + stock.symbol" @click="emit('select', stock.symbol)">↗</button></td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
