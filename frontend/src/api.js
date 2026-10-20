export async function api(path) {
  const response = await fetch(path, { headers: { Accept: "application/json" } });
  if (!response.ok) {
    let detail = "";
    try { detail = (await response.json()).detail || ""; } catch { /* use HTTP status */ }
    throw new Error(detail || "HTTP " + response.status);
  }
  return response.json();
}
