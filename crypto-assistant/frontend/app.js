const $ = (sel) => document.querySelector(sel);
const fmtUsd = (v) => v == null ? "—" : "$" + Number(v).toLocaleString(undefined, { maximumFractionDigits: v < 1 ? 6 : 0 });
const fmtPct = (v) => v == null ? "—" : (v >= 0 ? "+" : "") + v.toFixed(1) + "%";
const short = (a) => a ? a.slice(0, 4) + "…" + a.slice(-4) : "";

async function load() {
  const btn = $("#refresh");
  const status = $("#status");
  btn.disabled = true;
  status.textContent = "Fetching on-chain + market data…";
  try {
    const res = await fetch("/api/overview");
    if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
    const data = await res.json();
    render(data);
    status.textContent = "Updated " + new Date().toLocaleTimeString();
  } catch (e) {
    status.textContent = "Error: " + e.message;
  } finally {
    btn.disabled = false;
  }
}

function render(data) {
  // Stats
  const highRisk = data.wallets.flatMap(w => w.coins || []).filter(c => c.risk_level === "high").length;
  $("#stats").innerHTML = [
    stat(data.wallet_count, "Wallets"),
    stat(data.coin_count, "Unique coins"),
    stat(data.shared_coins.length, "Shared coins"),
    stat(highRisk, "High-risk holdings"),
  ].join("");

  // Shared coins
  $("#shared").innerHTML = data.shared_coins.length
    ? data.shared_coins.map(c => `
        <div class="shared-card">
          <div class="sym">${c.symbol || short(c.mint)} <span class="badge ${c.risk_level || ""}">${(c.risk_level || "?").toUpperCase()}</span></div>
          <div>${fmtUsd(c.market_cap)} mcap · <span class="${(c.price_change_24h||0)>=0?'pos':'neg'}">${fmtPct(c.price_change_24h)}</span></div>
          <div class="held">Held by ${c.holder_count}: ${c.held_by.join(", ")}</div>
        </div>`).join("")
    : `<p class="empty">No coins held across multiple wallets yet.</p>`;

  // Wallets
  $("#wallets").innerHTML = data.wallets.map((w, i) => walletHtml(w, i)).join("");
  document.querySelectorAll(".wallet-head").forEach(h => {
    h.addEventListener("click", () => h.parentElement.classList.toggle("open"));
  });
}

function stat(num, lbl) {
  return `<div class="stat"><div class="num">${num}</div><div class="lbl">${lbl}</div></div>`;
}

function walletHtml(w, i) {
  const coins = w.coins || [];
  const body = w.error
    ? `<p class="error">RPC error: ${w.error}</p>`
    : coins.length
      ? `<table>
           <tr><th>Coin</th><th>Market cap</th><th>24h</th><th>Value held</th><th>Risk</th></tr>
           ${coins.map(coinRow).join("")}
         </table>`
      : `<p class="empty">No non-stablecoin holdings above threshold.</p>`;
  return `
    <div class="wallet ${i === 0 ? "open" : ""}">
      <div class="wallet-head">
        <div>
          <div class="wallet-label">${w.label}</div>
          <div class="wallet-addr">${short(w.address)}</div>
        </div>
        <div class="wallet-meta">${w.error ? '<span class="error">error</span>' : coins.length + " coins"}</div>
      </div>
      <div class="coins">${body}</div>
    </div>`;
}

function coinRow(c) {
  const link = c.dex_url ? `<a href="${c.dex_url}" target="_blank">${c.symbol}</a>` : (c.symbol || "");
  return `<tr>
    <td>${link}</td>
    <td>${fmtUsd(c.market_cap)}</td>
    <td class="${(c.price_change_24h||0)>=0?'pos':'neg'}">${fmtPct(c.price_change_24h)}</td>
    <td>${fmtUsd(c.value_usd)}</td>
    <td><span class="badge ${c.risk_level}">${c.risk_score}</span></td>
  </tr>`;
}

$("#refresh").addEventListener("click", load);
load();
