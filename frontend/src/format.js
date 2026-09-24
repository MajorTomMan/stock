export function number(value) {
  if (value === null || value === undefined || value === "") return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

export function price(value) {
  const n = number(value);
  return n === null ? "—" : n.toFixed(2);
}

export function amount(value, unit = "") {
  const n = number(value);
  if (n === null) return "—";
  if (Math.abs(n) >= 1e8) return (n / 1e8).toFixed(2) + " 亿" + unit;
  if (Math.abs(n) >= 1e4) return (n / 1e4).toFixed(2) + " 万" + unit;
  return n.toLocaleString("zh-CN", { maximumFractionDigits: 0 }) + (unit ? " " + unit : "");
}

export function percent(value) {
  const n = number(value);
  if (n === null) return "—";
  return (n > 0 ? "+" : "") + n.toFixed(2) + "%";
}

export function direction(value, baseline = 0) {
  const n = number(value), b = number(baseline);
  if (n === null || b === null) return "";
  return n > b ? "up" : n < b ? "down" : "flat";
}

export function changePercent(bar) {
  if (!bar) return null;
  const previous = number(bar.pre_close), close = number(bar.close);
  return previous !== null && previous > 0 && close !== null
    ? (close / previous - 1) * 100 : number(bar.pct_change);
}
