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
    const [ovRes, actRes, accRes] = await Promise.all([
      fetch("/api/overview"),
      fetch("/api/activity"),
      fetch("/api/accounts"),
    ]);
    if (!ovRes.ok) throw new Error((await ovRes.json()).detail || ovRes.statusText);
    const data = await ovRes.json();
    render(data);
    if (actRes.ok) renderActivity((await actRes.json()).activity || []);
    if (accRes.ok) renderAccounts(await accRes.json());
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

  // Alerts
  renderAlerts(data.alerts || []);

  // Meta radar
  renderMetas(data.metas || []);

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

const EVENT_META = {
  NEW:    { icon: "🟢", verb: "bought" },
  ADD:    { icon: "➕", verb: "added to" },
  REDUCE: { icon: "➖", verb: "reduced" },
  EXIT:   { icon: "🔴", verb: "exited" },
};

function timeAgo(ts) {
  const secs = Math.max(0, Date.now() / 1000 - ts);
  if (secs < 60) return "just now";
  if (secs < 3600) return Math.floor(secs / 60) + "m ago";
  if (secs < 86400) return Math.floor(secs / 3600) + "h ago";
  return Math.floor(secs / 86400) + "d ago";
}

function renderActivity(events) {
  const el = $("#activity");
  if (!events.length) {
    el.innerHTML = `<p class="empty">No activity yet — the poller records new buys/exits between snapshots (live mode).</p>`;
    return;
  }
  el.innerHTML = events.map(e => {
    const m = EVENT_META[e.event_type] || { icon: "•", verb: e.event_type };
    return `<div class="feed-row ${e.level === "alert" ? "alert" : ""}">
      <span class="feed-icon">${m.icon}</span>
      <span class="feed-text"><strong>${e.wallet_label || "?"}</strong> ${m.verb} <strong>${e.symbol || ""}</strong>${e.note ? ` <span class="feed-note">${e.note}</span>` : ""}</span>
      <span class="feed-time">${timeAgo(e.ts)}</span>
    </div>`;
  }).join("");
}

function stat(num, lbl) {
  return `<div class="stat"><div class="num">${num}</div><div class="lbl">${lbl}</div></div>`;
}

const LEAN_ICON = { bullish: "🟢", bearish: "🔴", neutral: "⚪" };

function renderAccounts(data) {
  const el = $("#accounts");
  const accounts = data.accounts || [];
  $("#x-provider").textContent = `— provider: ${data.provider}`;
  if (!accounts.length || data.provider === "none") {
    el.innerHTML = `<p class="empty">No X data. Set <code>X_PROVIDER</code> (and add accounts to <code>x_accounts.json</code>) to read posts — free tier can't read X, so this needs a paid provider. Try <code>DEMO_MODE=1</code> to preview.</p>`;
    return;
  }
  el.innerHTML = accounts.map(a => `
    <div class="wallet open">
      <div class="wallet-head">
        <div>
          <div class="wallet-label">${LEAN_ICON[a.lean] || "⚪"} <a href="${a.url}" target="_blank">@${a.handle}</a></div>
          <div class="wallet-addr">${a.person || ""}</div>
        </div>
        <div class="wallet-meta">${a.lean}</div>
      </div>
      <div class="coins" style="display:block">
        ${(a.posts || []).map(p => `<div class="post ${p.sentiment}"><span class="post-sent">${LEAN_ICON[p.sentiment]}</span> ${p.text} <span class="feed-time">${timeAgo(p.ts)}</span></div>`).join("") || '<p class="empty">No recent posts.</p>'}
      </div>
    </div>`).join("");
}

function renderAlerts(alerts) {
  const el = $("#alerts");
  if (!alerts.length) {
    el.innerHTML = `<p class="empty">No high-risk holdings across tracked wallets. ✅</p>`;
    return;
  }
  el.innerHTML = alerts.map(a => `
    <div class="alert-row">
      <span class="alert-badge">${a.risk_score ?? "!"}</span>
      <span class="alert-text"><strong>${a.wallet_label}</strong> holds <strong>${a.symbol}</strong> — ${a.reason}</span>
      <span class="alert-val">${fmtUsd(a.value_usd)}</span>
    </div>`).join("");
}

function renderMetas(metas) {
  const el = $("#metas");
  if (!metas.length) {
    el.innerHTML = `<p class="empty">No recognised narratives in current holdings.</p>`;
    return;
  }
  const max = Math.max(...metas.map(m => m.wallet_count));
  el.innerHTML = metas.map((m, i) => `
    <div class="meta-card ${i === 0 ? "lead" : ""}">
      <div class="meta-top">
        <span class="meta-name">${m.emoji} ${m.narrative}</span>
        ${i === 0 ? '<span class="meta-lead-tag">TOP META</span>' : ""}
      </div>
      <div class="meta-bar"><div class="meta-fill" style="width:${(m.wallet_count / max) * 100}%"></div></div>
      <div class="meta-stats">
        <span>${m.wallet_count} wallets</span>
        <span>${m.coin_count} coins</span>
        <span class="${(m.avg_change_24h||0)>=0?'pos':'neg'}">${fmtPct(m.avg_change_24h)}</span>
      </div>
      <div class="meta-coins">${m.coins.join(" · ")}</div>
    </div>`).join("");
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

async function lookupCoin() {
  const q = $("#coin-q").value.trim();
  const out = $("#lookup-result");
  if (!q) { out.innerHTML = ""; return; }
  out.innerHTML = `<div class="lookup-card">Looking up <strong>${q}</strong>…</div>`;
  try {
    const res = await fetch("/api/coin?q=" + encodeURIComponent(q));
    if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
    const c = await res.json();
    const flags = (c.flags || []).map(f =>
      `<li class="flag ${f.severity}">${f.message}</li>`).join("");
    out.innerHTML = `<div class="lookup-card">
      <button class="lookup-close" onclick="document.getElementById('lookup-result').innerHTML=''">×</button>
      <div class="lookup-head">
        <span class="lookup-sym">${c.dex_url ? `<a href="${c.dex_url}" target="_blank">${c.symbol}</a>` : c.symbol}</span>
        <span class="badge ${c.risk_level}">RISK ${c.risk_score}</span>
        ${(c.narratives||[]).map(n => `<span class="chain-tag">${n}</span>`).join("")}
      </div>
      <div class="lookup-stats">
        <span>${fmtUsd(c.market_cap)} <small>mcap</small></span>
        <span>${fmtUsd(c.price_usd)} <small>price</small></span>
        <span class="${(c.price_change_24h||0)>=0?'pos':'neg'}">${fmtPct(c.price_change_24h)} <small>24h</small></span>
        <span>${fmtUsd(c.liquidity_usd)} <small>liq</small></span>
      </div>
      <ul class="flags">${flags}</ul>
    </div>`;
  } catch (e) {
    out.innerHTML = `<div class="lookup-card error">${e.message}</div>`;
  }
}

$("#refresh").addEventListener("click", load);
$("#lookup").addEventListener("click", lookupCoin);
$("#coin-q").addEventListener("keydown", (e) => { if (e.key === "Enter") lookupCoin(); });
load();
