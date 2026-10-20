<script setup>
import { ref, watch, onMounted } from "vue";
import { api } from "../api.js";

const emit = defineEmits(["select"]);
const query = ref("");
const page = ref(0);
const items = ref([]);
const hasMore = ref(false);
const loading = ref(false);
const error = ref("");
let request = 0;
let debounce;

async function load(nextPage = 0) {
  const serial = ++request;
  const q = query.value.trim();
  loading.value = true;
  error.value = "";
  try {
    const data = await api("/api/instruments?limit=21&offset=" + (nextPage * 20) +
      "&q=" + encodeURIComponent(q));
    if (serial !== request) return;
    items.value = (data.items || []).slice(0, 20);
    hasMore.value = data.items.length > 20;
    page.value = nextPage;
  } catch (cause) {
    if (serial !== request) return;
    error.value = cause.message;
    items.value = [];
    hasMore.value = false;
  } finally {
    if (serial === request) loading.value = false;
  }
}
watch(query, () => {
  clearTimeout(debounce);
  // Invalidate any in-flight request immediately when input changes.
  request += 1;
  loading.value = true;
  debounce = setTimeout(() => load(0), 220);
});
onMounted(() => load());
</script>

<template>
  <section class="content-card directory-card" id="stock-directory">
    <div class="section-heading">
      <div>
        <div class="section-eyebrow">STOCK DIRECTORY</div>
        <div class="section-title">
          <h2>股票目录</h2>
          <span class="section-subtitle">浏览主数据中的全部深市证券，包括尚未补齐最新行情的股票</span>
        </div>
      </div>
      <label class="directory-search"><span>⌕</span>
        <input v-model="query" type="search" maxlength="128" placeholder="按代码或名称筛选…" aria-label="筛选股票目录" />
      </label>
    </div>
    <div class="table-wrap">
      <table class="stocks-table directory-table">
        <thead><tr><th>股票</th><th>板块</th><th>上市日期</th><th>状态</th><th></th></tr></thead>
        <tbody>
          <tr v-if="loading"><td colspan="5" class="empty-row">正在读取股票目录…</td></tr>
          <tr v-else-if="error"><td colspan="5" class="empty-row">股票目录读取失败：{{ error }}</td></tr>
          <tr v-else-if="!items.length"><td colspan="5" class="empty-row">没有符合条件的股票</td></tr>
          <tr v-for="item in !loading ? items : []" :key="item.symbol">
            <td>
              <button class="stock-cell" @click="emit('select', item.symbol)">
                <span class="stock-avatar">{{ item.symbol.slice(0, 2) }}</span>
                <span><b>{{ item.current_name || "未命名证券" }}</b><small>{{ item.symbol }}.SZ</small></span>
              </button>
            </td>
            <td>{{ item.board || "—" }}</td>
            <td class="num">{{ item.list_date || "—" }}</td>
            <td><span class="table-source">{{ item.status || "UNKNOWN" }}</span></td>
            <td><button class="row-go" :aria-label="'查看 ' + item.symbol" @click="emit('select', item.symbol)">↗</button></td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="directory-pagination">
      <button :disabled="loading || page === 0" @click="load(page - 1)">← 上一页</button>
      <span id="directory-page" aria-live="polite">{{ loading ? "正在读取…" : "第 " + (page + 1) + " 页 · " + items.length + " 只" }}</span>
      <button :disabled="loading || !hasMore" @click="load(page + 1)">下一页 →</button>
    </div>
  </section>
</template>
