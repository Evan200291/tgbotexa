/* Exabyte Digital Store — Mini App & Web Admin Panel Logic
 * Uses CSS variables from theme.css; no raw hex literals appear in this file.
 */

(function () {
  "use strict";

  function getTg() {
    return window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
  }

  function getInitData() {
    const tg = getTg();
    if (tg && tg.initData) return tg.initData;
    try {
      if (window.location.hash && window.location.hash.length > 1) {
        const hp = new URLSearchParams(window.location.hash.slice(1));
        const raw = hp.get("tgWebAppData");
        if (raw) return raw;
      }
    } catch (_) {
      /* ignore */
    }
    return "";
  }

  const tg = getTg();
  let state = {
    boot: null,
    activeTab: "home",
    devAdmin: window.location.pathname === "/admin" || window.location.search.includes("admin=1"),
    countdownTimer: null,
    selectedTargetSubId: 0,
    selectedPanelId: 0,
  };

  function haptic(kind) {
    try {
      if (tg && tg.HapticFeedback) {
        if (kind === "success" || kind === "error" || kind === "warning") {
          tg.HapticFeedback.notificationOccurred(kind);
        } else {
          tg.HapticFeedback.impactOccurred(kind || "light");
        }
      }
    } catch (_) {
      /* ignore outside Telegram */
    }
  }

  function showToast(msg) {
    const el = document.getElementById("toast");
    if (!el) return;
    el.textContent = msg;
    el.classList.remove("hidden");
    clearTimeout(el._t);
    el._t = setTimeout(() => el.classList.add("hidden"), 2900);
  }

  function applyTheme(theme) {
    const root = document.documentElement;
    root.setAttribute("data-theme", theme);
    const btn = document.getElementById("theme-toggle");
    if (btn) btn.textContent = theme === "light" ? "☀️" : "🌙";
    try {
      localStorage.setItem("exabyte_theme", theme);
    } catch (_) {
      /* ignore private browsing */
    }
    try {
      if (tg) {
        const bg = getComputedStyle(root).getPropertyValue("--bg").trim();
        const surf = getComputedStyle(root).getPropertyValue("--surface").trim();
        if (tg.setHeaderColor && surf) tg.setHeaderColor(surf);
        if (tg.setBackgroundColor && bg) tg.setBackgroundColor(bg);
        if (tg.setBottomBarColor && surf) tg.setBottomBarColor(surf);
      }
    } catch (_) {
      /* ignore older WebApp versions */
    }
  }

  function initTheme() {
    let preferred = "dark";
    try {
      const params = new URLSearchParams(window.location.search);
      const qTheme = params.get("theme");
      const saved = localStorage.getItem("exabyte_theme");
      if (qTheme === "light" || qTheme === "dark") {
        preferred = qTheme;
      } else if (saved === "light" || saved === "dark") {
        preferred = saved;
      } else if (tg && tg.initData && tg.colorScheme) {
        preferred = tg.colorScheme === "light" ? "light" : "dark";
      }
    } catch (_) {
      preferred = "dark";
    }
    applyTheme(preferred);
  }

  async function api(path, opts) {
    const options = opts || {};
    const headers = Object.assign(
      { "Content-Type": "application/json" },
      options.headers || {}
    );
    const initData = getInitData();
    if (initData) {
      headers["X-Telegram-Init-Data"] = initData;
    }
    if (state.devAdmin) {
      headers["X-Dev-Admin"] = "1";
    }
    const resp = await fetch(path, {
      method: options.method || "GET",
      headers: headers,
      body: options.body ? JSON.stringify(options.body) : undefined,
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      throw new Error(data.detail || "တစ်ခုခု မှားယွင်းသွားပါသည်။");
    }
    return data;
  }

  function fmtBytes(bytes) {
    const gb = 1024 * 1024 * 1024;
    if (bytes >= gb) return (bytes / gb).toFixed(1) + " GB";
    return Math.round(bytes / (1024 * 1024)) + " MB";
  }

  function fmtDateShort(isoStr) {
    if (!isoStr) return "—";
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) return isoStr;
    try {
      // Myanmar Standard Time (UTC+6:30, Asia/Yangon)
      const parts = new Intl.DateTimeFormat("en-GB", {
        timeZone: "Asia/Yangon",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      }).formatToParts(d);
      const m = {};
      parts.forEach((p) => {
        m[p.type] = p.value;
      });
      return `${m.year}-${m.month}-${m.day} ${m.hour}:${m.minute} MMT`;
    } catch (_) {
      const mmtMs = d.getTime() + (6 * 60 + 30) * 60000;
      const mmtDate = new Date(mmtMs);
      return mmtDate.toISOString().slice(0, 16).replace("T", " ") + " MMT";
    }
  }

  function fmtCountdown(sec) {
    const s = Math.max(0, Math.floor(sec));
    const d = Math.floor(s / 86400);
    const h = Math.floor((s % 86400) / 3600);
    const m = Math.floor((s % 3600) / 60);
    const parts = [];
    if (d > 0) parts.push(d + " ရက်");
    if (h > 0) parts.push(h + " နာရီ");
    parts.push(Math.max(m, d === 0 && h === 0 ? 1 : m) + " မိနစ်");
    return parts.join(" ");
  }

  async function copyText(text, label) {
    haptic("light");
    try {
      await navigator.clipboard.writeText(text);
      showToast("✅ ကူးယူပြီးပါပြီ — " + (label || ""));
    } catch (_) {
      showToast("📋 " + text);
    }
  }

  function switchTab(tab) {
    haptic("selection");
    state.activeTab = tab;
    document.querySelectorAll(".tab-view").forEach((el) => {
      el.classList.toggle("hidden", el.id !== "view-" + tab);
    });
    document.querySelectorAll(".dock-tab").forEach((btn) => {
      btn.classList.toggle("active", btn.getAttribute("data-tab") === tab);
    });
    if (tab === "admin" && state.boot && state.boot.user && state.boot.user.is_admin) {
      loadAdminOverview();
    }
  }

  function renderHome(boot) {
    const st = boot.status;
    const badge = document.getElementById("home-status-badge");
    const arc = document.getElementById("home-ring-arc");
    const rVal = document.getElementById("home-ring-val");
    const rSub = document.getElementById("home-ring-sub");
    const kindEl = document.getElementById("home-kind");
    const daysEl = document.getElementById("home-days");
    const expEl = document.getElementById("home-expiry");
    const srvCnt = document.getElementById("home-servers-cnt");
    const circum = 301.6;

    arc.classList.remove("warn", "crit");
    if (!st.has_key) {
      badge.className = "badge badge-none";
      badge.textContent = "Key မရှိသေးပါ";
      arc.style.strokeDashoffset = String(circum);
      rVal.textContent = "0%";
      rSub.textContent = "Key မရှိသေးပါ";
      kindEl.textContent = "—";
      daysEl.textContent = "0 ရက်";
      expEl.textContent = "—";
      srvCnt.textContent = "1 လုံး";
    } else {
      const isAct = st.status === "active";
      badge.className = "badge " + (isAct ? "badge-active" : "badge-expired");
      badge.textContent = isAct
        ? "အသုံးပြုနေဆဲ"
        : st.status === "disabled"
        ? "ယာယီပိတ်ထားသည်"
        : "သက်တမ်းကုန်ပြီ";

      kindEl.textContent = st.kind === "paid" ? "ငွေပေး Plan" : "အခမဲ့ စမ်းသပ်";
      daysEl.textContent = st.days_left + " ရက်";
      expEl.textContent = fmtDateShort(st.expiry_at);
      srvCnt.textContent = ((st.servers && st.servers.length) || 1) + " လုံး";

      if (st.unlimited) {
        arc.style.strokeDashoffset = "0";
        if (!isAct) arc.classList.add("crit");
        rVal.textContent = "∞";
        rSub.textContent = fmtBytes(st.used_bytes) + " သုံးပြီး";
      } else {
        const ratio = st.quota_bytes > 0 ? Math.min(st.used_bytes / st.quota_bytes, 1) : 0;
        const pct = Math.round(ratio * 100);
        arc.style.strokeDashoffset = String(circum * (1 - ratio));
        if (!isAct || ratio >= 1) arc.classList.add("crit");
        else if (ratio >= 0.8) arc.classList.add("warn");
        rVal.textContent = pct + "%";
        rSub.textContent = fmtBytes(st.used_bytes) + " / " + fmtBytes(st.quota_bytes);
      }
    }

    // Trial section + live countdown
    const trialBtn = document.getElementById("btn-claim-trial");
    const trialDesc = document.getElementById("trial-desc");
    clearInterval(state.countdownTimer);
    const tr = st.trial || {};
    if (tr.reason === "paid_active") {
      trialBtn.disabled = true;
      trialBtn.textContent = "🛡️ ငွေပေး Plan အသုံးပြုနေဆဲ";
      trialDesc.textContent =
        "သင့်တွင် ငွေပေး Plan အသုံးပြုနေဆဲ ဖြစ်သောကြောင့် အခမဲ့ စမ်းသပ် မလိုတော့ပါ။";
    } else if (!tr.available && tr.seconds_until_next_trial > 0) {
      trialBtn.disabled = true;
      let rem = tr.seconds_until_next_trial;
      const tick = () => {
        trialBtn.textContent = "⏳ နောက်တစ်ကြိမ်: " + fmtCountdown(rem);
        trialDesc.textContent =
          "အခမဲ့ စမ်းသပ်ကို 7 ရက်ပြည့်တိုင်း Key အသစ်ဖြင့် ပြန်လည် ရယူနိုင်ပါသည်။";
        rem = Math.max(0, rem - 1);
      };
      tick();
      state.countdownTimer = setInterval(tick, 1000);
    } else {
      trialBtn.disabled = false;
      trialBtn.textContent = "⏳ အခမဲ့ စမ်းသပ် (5 GB) ရယူမည်";
      trialDesc.textContent =
        "မြန်နှုန်းမြင့် Shadowsocks VPN ကို 5 GB (7 ရက်) အခမဲ့ စမ်းသပ်အသုံးပြုနိုင်ပါသည်။";
    }
  }

  function renderKey(boot) {
    const st = boot.status;
    const emptyCard = document.getElementById("key-empty-card");
    const contentCard = document.getElementById("key-content-card");
    if (!st.has_key) {
      emptyCard.classList.remove("hidden");
      contentCard.classList.add("hidden");
      return;
    }
    emptyCard.classList.add("hidden");
    contentCard.classList.remove("hidden");

    const srvContainer = document.getElementById("key-servers-list");
    srvContainer.innerHTML = "";
    const keysList = st.keys && st.keys.length ? st.keys : [st];
    const availServers = boot.available_servers || [];

    keysList.forEach((k, idx) => {
      const kCard = document.createElement("div");
      kCard.style.padding = "10px 0";
      if (idx > 0) {
        kCard.style.borderTop = "1px solid var(--border)";
        kCard.style.marginTop = "10px";
      }

      const dataDesc = k.unlimited
        ? "♾️ Unlimited Data (1 Server)"
        : "🌐 Shared GB: ကျန် " +
          fmtBytes(k.remaining_bytes != null ? k.remaining_bytes : Math.max(0, k.quota_bytes - k.used_bytes)) +
          " / " +
          fmtBytes(k.quota_bytes);

      const hdr = document.createElement("div");
      hdr.style.marginBottom = "8px";
      hdr.innerHTML =
        '<div style="font-weight:700;font-size:0.96rem;">🔑 Key #' +
        (idx + 1) +
        " (<code>" +
        (k.email || "") +
        "</code>)</div>" +
        '<div style="font-size:0.86rem;color:var(--text-muted);">' +
        dataDesc +
        " • လက်ကျန် " +
        k.days_left +
        " ရက်</div>";
      kCard.appendChild(hdr);

      const servers =
        k.servers && k.servers.length
          ? k.servers
          : [{ panel_id: k.panel_id || 0, name: "Server 1", link: k.link }];
      servers.forEach((srv) => {
        const wrap = document.createElement("div");
        wrap.style.marginBottom = "8px";
        const title = document.createElement("div");
        title.style.fontWeight = "600";
        title.style.fontSize = "0.9rem";
        title.textContent = "🖧 " + srv.name + " (နှိပ်၍ ကူးယူပါ):";
        const box = document.createElement("div");
        box.className = "mono-box";
        box.textContent = srv.link;
        box.addEventListener("click", () => copyText(srv.link, srv.name));
        wrap.appendChild(title);
        wrap.appendChild(box);
        kCard.appendChild(wrap);
      });

      if (k.multi_server && availServers.length > 1 && k.id) {
        const swRow = document.createElement("div");
        swRow.className = "btn-row";
        swRow.style.marginTop = "6px";
        availServers.forEach((asrv) => {
          const btn = document.createElement("button");
          btn.type = "button";
          const isCur = Number(asrv.id) === Number(k.panel_id || 0);
          btn.className = "btn btn-sm " + (isCur ? "btn-primary" : "btn-secondary");
          btn.textContent = (isCur ? "✅ " : "🔄 ") + asrv.name;
          btn.addEventListener("click", async () => {
            try {
              const res = await api("/api/keys/" + k.id + "/server", {
                method: "POST",
                body: { panel_id: asrv.id },
              });
              showToast(res.message);
              await refreshBootstrap();
            } catch (err) {
              showToast(err.message);
            }
          });
          swRow.appendChild(btn);
        });
        kCard.appendChild(swRow);
      }

      srvContainer.appendChild(kCard);
    });

    const subWrap = document.getElementById("key-sub-wrap");
    if (subWrap) {
      subWrap.classList.add("hidden");
    }

    const regenBtn = document.getElementById("btn-regen-key");
    if (regenBtn) {
      regenBtn.classList.add("hidden");
    }
  }

  function renderPlans(boot) {
    const coCard = document.getElementById("checkout-card");
    const ord = boot.open_order;
    const store = boot.store || {};
    if (ord) {
      coCard.classList.remove("hidden");
      document.getElementById("co-plan").textContent = ord.plan_name + " (" + ord.days + " ရက်)";
      document.getElementById("co-amount").textContent = ord.amount_text;
      document.getElementById("co-code").textContent = ord.code;
      const numEl = document.getElementById("co-kbz-num");
      numEl.textContent = store.kbz_number || "09688220563";
      numEl.onclick = () => copyText(numEl.textContent, "KBZ Pay နံပါတ်");
      document.getElementById("co-kbz-name").textContent = store.kbz_name || "Exabyte Store";
    } else {
      coCard.classList.add("hidden");
    }

    const container = document.getElementById("plans-container");
    container.innerHTML = "";

    const st = boot.status || {};
    const existingKeys = st.keys || [];
    const availServers = boot.available_servers || [];

    if (existingKeys.length > 0) {
      const modeCard = document.createElement("div");
      modeCard.className = "card";
      modeCard.innerHTML =
        '<div style="font-weight:700;font-size:0.95rem;margin-bottom:8px;">🔑 ဝယ်ယူမည့် ပုံစံ ရွေးချယ်ပါ:</div>';
      const sel = document.createElement("select");
      sel.className = "input";
      const optNew = document.createElement("option");
      optNew.value = "0";
      optNew.textContent = "➕ Key အသစ်ဝယ်မည် (နောက်ထပ် Key 1 ခု ထပ်ယူမည်)";
      sel.appendChild(optNew);
      existingKeys.forEach((k, idx) => {
        const opt = document.createElement("option");
        opt.value = String(k.id);
        opt.textContent =
          "🔄 လက်ရှိ Key #" + (idx + 1) + " သက်တမ်းတိုးမည် (" + k.email + ")";
        sel.appendChild(opt);
      });
      sel.value = String(state.selectedTargetSubId || 0);
      sel.addEventListener("change", () => {
        state.selectedTargetSubId = Number(sel.value);
      });
      modeCard.appendChild(sel);

      if (availServers.length > 1) {
        const srvLbl = document.createElement("div");
        srvLbl.style.fontWeight = "700";
        srvLbl.style.fontSize = "0.92rem";
        srvLbl.style.margin = "10px 0 6px";
        srvLbl.textContent = "🖧 Unlimited Plan အတွက် ဆာဗာ ရွေးပါ:";
        const srvSel = document.createElement("select");
        srvSel.className = "input";
        availServers.forEach((s) => {
          const o = document.createElement("option");
          o.value = String(s.id);
          o.textContent = "🌐 " + s.name + " (" + s.host + ")";
          srvSel.appendChild(o);
        });
        srvSel.value = String(state.selectedPanelId || 0);
        srvSel.addEventListener("change", () => {
          state.selectedPanelId = Number(srvSel.value);
        });
        modeCard.appendChild(srvLbl);
        modeCard.appendChild(srvSel);
      }
      container.appendChild(modeCard);
    }

    (boot.plans || []).forEach((p) => {
      const cls = p.months === 1 ? "plan-1m" : p.months === 3 ? "plan-3m" : "plan-6m";
      const card = document.createElement("div");
      card.className = "plan-card " + cls;

      let ribbonHtml = "";
      if (p.best_value) {
        ribbonHtml =
          '<div class="plan-ribbon">✨ ' +
          p.badge_text +
          " • " +
          p.discount_text +
          " သက်သာ</div>";
      } else if (p.discount_mmk > 0) {
        ribbonHtml = '<div class="plan-ribbon">🏷️ ' + p.badge_text + "</div>";
      }

      const oldPriceHtml =
        p.discount_mmk > 0
          ? '<span class="plan-old-price">' + p.original_price_text + "</span>"
          : "";

      const featHtml = p.unlimited
        ? "📶 Data အကန့်အသတ်မရှိ (1 Server) • 📱 စက် " + p.devices + " လုံး • ⏳ " + p.days + " ရက်"
        : "🌐 " + p.quota_gb + " GB (ဆာဗာအားလုံး ပြောင်းသုံးနိုင်သည် • Shared Data) • ⏳ " + p.days + " ရက်";

      card.innerHTML =
        ribbonHtml +
        '<div class="plan-head">' +
        '<div class="plan-name">' + (p.unlimited ? "🛡️ " : "🌐 ") +
        p.name +
        "</div>" +
        '<div class="plan-price-wrap">' +
        oldPriceHtml +
        '<span class="plan-price">' +
        p.price_text +
        "</span></div>" +
        "</div>" +
        '<div class="plan-features">' + featHtml + "</div>";

      const buyBtn = document.createElement("button");
      buyBtn.type = "button";
      buyBtn.className = "btn " + (p.best_value ? "btn-primary" : "btn-secondary");
      buyBtn.textContent = "💳 " + p.name + " ဝယ်ယူမည် (" + p.price_text + ")";
      buyBtn.addEventListener("click", () => startOrder(p.id));
      card.appendChild(buyBtn);
      container.appendChild(card);
    });
  }

  async function startOrder(planId) {
    haptic("medium");
    try {
      const existingKeys = (state.boot && state.boot.status && state.boot.status.keys) || [];
      const targetSubId = existingKeys.length > 0 ? Number(state.selectedTargetSubId || 0) : null;
      const ord = await api("/api/orders", {
        method: "POST",
        body: {
          plan_id: planId,
          target_sub_id: targetSubId,
          panel_id: Number(state.selectedPanelId || 0),
        },
      });
      state.boot.open_order = ord;
      renderPlans(state.boot);
      window.scrollTo({ top: 0, behavior: "smooth" });
      showToast("💳 အော်ဒါ " + ord.code + " ဖန်တီးပြီးပါပြီ။");
    } catch (e) {
      haptic("error");
      showToast(e.message);
    }
  }

  async function refreshBootstrap() {
    try {
      const boot = await api("/api/bootstrap");
      state.boot = boot;
      document.getElementById("loading-view").classList.add("hidden");
      document.getElementById("hdr-tagline").textContent =
        (boot.store && boot.store.tagline) || "လုံခြုံ မြန်ဆန် စိတ်ချရသော ဒစ်ဂျစ်တယ်ဆိုင်";
      const supLink = document.getElementById("btn-support-link");
      if (supLink && boot.store && boot.store.support_url) {
        supLink.href = boot.store.support_url;
      }

      const admTab = document.getElementById("dock-admin-tab");
      if (boot.user && boot.user.is_admin) {
        admTab.classList.remove("hidden");
      } else {
        admTab.classList.add("hidden");
      }

      // Show dev role toggle on localhost for quick Customer <-> Admin preview
      if (window.location.hostname === "127.0.0.1" || window.location.hostname === "localhost") {
        document.getElementById("dev-role-btn").classList.remove("hidden");
      }

      renderHome(boot);
      renderKey(boot);
      renderPlans(boot);
      switchTab(state.devAdmin && boot.user && boot.user.is_admin ? "admin" : state.activeTab);
    } catch (e) {
      document.getElementById("loading-view").innerHTML =
        '<div class="card"><h3>⚠️ ' + e.message + "</h3></div>";
    } finally {
      setTimeout(() => {
        const sp = document.getElementById("splash");
        if (sp) sp.classList.add("hidden");
      }, 280);
    }
  }

  // ---------------- Web Admin Panel Rendering ----------------
  async function loadAdminOverview() {
    try {
      const data = await api("/api/admin/overview");
      const st = data.stats;
      const grid = document.getElementById("adm-stats-grid");
      grid.innerHTML =
        '<div class="stat-tile"><div class="stat-tile-num">' +
        st.total_users +
        '</div><div class="stat-tile-lbl">စုစုပေါင်း သုံးစွဲသူ</div></div>' +
        '<div class="stat-tile"><div class="stat-tile-num">' +
        st.active_paid +
        '</div><div class="stat-tile-lbl">Paid Active</div></div>' +
        '<div class="stat-tile"><div class="stat-tile-num">' +
        st.active_trials +
        '</div><div class="stat-tile-lbl">Trial Active</div></div>' +
        '<div class="stat-tile"><div class="stat-tile-num">' +
        st.pending_orders +
        '</div><div class="stat-tile-lbl">စစ်ဆေးရန် အော်ဒါ</div></div>' +
        '<div class="stat-tile"><div class="stat-tile-num">' +
        st.today_revenue_text +
        '</div><div class="stat-tile-lbl">ယနေ့ ဝင်ငွေ</div></div>' +
        '<div class="stat-tile"><div class="stat-tile-num">' +
        st.month_revenue_text +
        '</div><div class="stat-tile-lbl">ယခုလ ဝင်ငွေ</div></div>';

      // Orders list
      const ordList = document.getElementById("adm-orders-list");
      ordList.innerHTML = "";
      if (!data.orders.length) {
        ordList.innerHTML = '<p style="color:var(--text-muted);">အော်ဒါ မရှိသေးပါ။</p>';
      }
      data.orders.forEach((o) => {
        const box = document.createElement("div");
        box.style.borderTop = "1px solid var(--border)";
        box.style.paddingTop = "10px";
        box.style.marginTop = "10px";

        const tokenQuery = state.adminToken ? "?token=" + encodeURIComponent(state.adminToken) : "";
        const shotUrl = o.screenshot
          ? (o.screenshot.startsWith("http") || o.screenshot.startsWith("/")
              ? o.screenshot + tokenQuery
              : o.screenshot)
          : "";
        const shotHtml =
          shotUrl && (shotUrl.startsWith("data:image") || shotUrl.startsWith("/"))
            ? '<div style="margin:8px 0;"><a href="' +
              shotUrl +
              '" target="_blank" rel="noopener"><img class="shot-preview" src="' +
              shotUrl +
              '" alt="Payment Screenshot" style="max-height:160px;border-radius:8px;border:1px solid var(--border);"></a><div style="font-size:0.75rem;color:var(--text-muted);margin-top:2px;">(Click to view full screenshot)</div></div>'
            : o.screenshot
            ? '<div class="mono-box">Telegram Photo ID: ' + o.screenshot + "</div>"
            : "";

        box.innerHTML =
          "<div><b>" +
          o.code +
          "</b> • User <code>" +
          o.user_id +
          "</code> (" +
          o.username +
          ")</div>" +
          '<div style="font-size:0.9rem;color:var(--text-muted);">Package: <b>' +
          o.plan_id +
          "</b> (" +
          o.amount_text +
          ") • State: <b>" +
          o.state +
          "</b> • Key: <code>" +
          o.key_email +
          "</code> (" +
          o.key_status +
          ")</div>" +
          shotHtml;

        const row = document.createElement("div");
        row.className = "btn-row";
        if (o.state === "awaiting_review") {
          const btnPaid = document.createElement("button");
          btnPaid.className = "btn btn-jade btn-sm";
          btnPaid.textContent = "✅ Paid";
          btnPaid.onclick = () => adminOrderAct(o.code, "approve");

          const btnUnpaid = document.createElement("button");
          btnUnpaid.className = "btn btn-danger btn-sm";
          btnUnpaid.textContent = "❌ Unpaid (Key ပိတ်မည်)";
          btnUnpaid.onclick = () => adminOrderAct(o.code, "reject");
          row.appendChild(btnPaid);
          row.appendChild(btnUnpaid);
        }

        const btnSusp = document.createElement("button");
        btnSusp.className = "btn btn-secondary btn-sm";
        btnSusp.textContent = o.key_enabled ? "⏸️ Key ယာယီပိတ်" : "▶️ Key ပြန်ဖွင့်";
        btnSusp.onclick = () =>
          adminUserAct(o.user_id, o.key_enabled ? "suspend" : "resume");
        row.appendChild(btnSusp);

        box.appendChild(row);
        ordList.appendChild(box);
      });

      // Users list
      const uList = document.getElementById("adm-users-list");
      uList.innerHTML = "";
      data.users.forEach((u) => {
        const div = document.createElement("div");
        div.style.borderTop = "1px solid var(--border)";
        div.style.paddingTop = "10px";
        div.style.marginTop = "10px";
        const k = u.key;
        const kTxt = k
          ? k.kind + " (" + k.status + ") • exp " + k.expiry_date
          : "Key မရှိပါ";
        div.innerHTML =
          "<div><b>ID: <code>" +
          u.user_id +
          "</code></b> (@" +
          u.username +
          ") " +
          (u.banned ? "🚫 Banned" : "") +
          '</div><div style="font-size:0.88rem;color:var(--text-muted);">' +
          kTxt +
          "</div>";

        const r = document.createElement("div");
        r.className = "btn-row";
        [
          ["+7d", "add7d"],
          ["-7d", "sub7d"],
          ["+30d", "add30d"],
          ["+5GB", "add5g"],
          [k && k.enabled ? "⏸️ ပိတ်" : "▶️ ဖွင့်", k && k.enabled ? "suspend" : "resume"],
          ["🗑️ ဖျက်", "revoke"],
        ].forEach(([lbl, act]) => {
          const b = document.createElement("button");
          b.className = "btn btn-secondary btn-sm";
          b.textContent = lbl;
          b.onclick = () => adminUserAct(u.user_id, act);
          r.appendChild(b);
        });
        div.appendChild(r);
        uList.appendChild(div);
      });

      // Panels list
      const pList = document.getElementById("adm-panels-list");
      pList.innerHTML = "";
      data.panels.forEach((p) => {
        const item = document.createElement("div");
        item.style.padding = "8px 0";
        item.style.borderBottom = "1px solid var(--border)";
        item.innerHTML =
          "<b>🖧 " +
          p.name +
          (p.is_primary ? " (Primary)" : "") +
          "</b> — <code>" +
          p.server_host +
          ":" +
          p.port +
          "</code> (" +
          p.method +
          ") [" +
          (p.enabled ? "Active" : "Disabled") +
          "]";
        if (!p.is_primary) {
          const pr = document.createElement("div");
          pr.className = "btn-row";
          const tBtn = document.createElement("button");
          tBtn.className = "btn btn-secondary btn-sm";
          tBtn.textContent = p.enabled ? "⏸️ Disable" : "▶️ Enable";
          tBtn.onclick = async () => {
            await api("/api/admin/panels/" + p.id + "/toggle", {
              method: "POST",
              body: { enabled: !p.enabled },
            });
            loadAdminOverview();
          };
          const dBtn = document.createElement("button");
          dBtn.className = "btn btn-danger btn-sm";
          dBtn.textContent = "🗑️ ဖျက်မည်";
          dBtn.onclick = async () => {
            await api("/api/admin/panels/" + p.id, { method: "DELETE" });
            loadAdminOverview();
          };
          pr.appendChild(tBtn);
          pr.appendChild(dBtn);
          item.appendChild(pr);
        }
        pList.appendChild(item);
      });

      // Populate store customization inputs
      const stCfg = data.store || {};
      document.getElementById("cfg-kbz-num").value = stCfg.kbz_number || "";
      document.getElementById("cfg-kbz-name").value = stCfg.kbz_name || "";
      document.getElementById("cfg-support").value = stCfg.support_url || "";
      document.getElementById("cfg-tagline").value = stCfg.tagline || "";
      document.getElementById("cfg-maint").checked = Boolean(stCfg.maintenance);
    } catch (e) {
      showToast(e.message);
    }
  }

  async function adminOrderAct(code, act) {
    haptic("medium");
    try {
      const res = await api("/api/admin/orders/" + code + "/" + act, {
        method: "POST",
        body: act === "reject" ? { reason: "ငွေလွှဲပြေစာ အတည်မပြုနိုင်ပါ" } : {},
      });
      showToast(res.message);
      await loadAdminOverview();
      await refreshBootstrap();
    } catch (e) {
      showToast(e.message);
    }
  }

  async function adminUserAct(uid, action) {
    haptic("light");
    try {
      const res = await api("/api/admin/users/" + uid + "/action", {
        method: "POST",
        body: { action: action },
      });
      showToast(res.message);
      await loadAdminOverview();
      await refreshBootstrap();
    } catch (e) {
      showToast(e.message);
    }
  }

  function readFileAsDataUrl(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const result = String(reader.result || "");
        if (file.size > 1.2 * 1024 * 1024 && file.type && file.type.startsWith("image/")) {
          const img = new Image();
          img.onload = () => {
            const maxDim = 1600;
            let w = img.width;
            let h = img.height;
            if (w > maxDim || h > maxDim) {
              if (w > h) {
                h = Math.round((h * maxDim) / w);
                w = maxDim;
              } else {
                w = Math.round((w * maxDim) / h);
                h = maxDim;
              }
            }
            const canvas = document.createElement("canvas");
            canvas.width = w;
            canvas.height = h;
            const ctx = canvas.getContext("2d");
            if (ctx) {
              ctx.drawImage(img, 0, 0, w, h);
              resolve(canvas.toDataURL("image/jpeg", 0.85));
              return;
            }
            resolve(result);
          };
          img.onerror = () => resolve(result);
          img.src = result;
        } else {
          resolve(result);
        }
      };
      reader.onerror = () => reject(new Error("ပုံဖတ်၍ မရပါ။"));
      reader.readAsDataURL(file);
    });
  }

  // ---------------- Wire UI Events ----------------
  document.addEventListener("DOMContentLoaded", () => {
    if (tg) {
      try {
        tg.ready();
        tg.expand();
      } catch (_) {
        /* ignore */
      }
    }
    initTheme();

    document.getElementById("theme-toggle").addEventListener("click", () => {
      haptic("light");
      const cur = document.documentElement.getAttribute("data-theme") || "dark";
      applyTheme(cur === "dark" ? "light" : "dark");
    });

    document.getElementById("dev-role-btn").addEventListener("click", () => {
      state.devAdmin = !state.devAdmin;
      showToast(state.devAdmin ? "👑 Admin View" : "👤 Customer View");
      refreshBootstrap();
    });

    document.querySelectorAll(".dock-tab").forEach((btn) => {
      btn.addEventListener("click", () => switchTab(btn.getAttribute("data-tab")));
    });

    document.querySelectorAll("[data-go-tab]").forEach((btn) => {
      btn.addEventListener("click", () => switchTab(btn.getAttribute("data-go-tab")));
    });

    document.querySelectorAll("[data-acc]").forEach((btn) => {
      btn.addEventListener("click", () => {
        haptic("light");
        const target = document.getElementById(btn.getAttribute("data-acc"));
        if (target) target.classList.toggle("hidden");
      });
    });

    document.getElementById("btn-claim-trial").addEventListener("click", async () => {
      haptic("medium");
      try {
        const res = await api("/api/trial/claim", { method: "POST" });
        haptic("success");
        showToast(res.message);
        await refreshBootstrap();
        switchTab("key");
      } catch (e) {
        haptic("error");
        showToast(e.message);
      }
    });

    document.getElementById("btn-regen-key").addEventListener("click", async () => {
      haptic("medium");
      try {
        const res = await api("/api/key/regenerate", { method: "POST" });
        haptic("success");
        showToast(res.message);
        await refreshBootstrap();
      } catch (e) {
        haptic("error");
        showToast(e.message);
      }
    });

    document.getElementById("btn-cancel-order").addEventListener("click", async () => {
      const ord = state.boot && state.boot.open_order;
      if (!ord) return;
      try {
        const res = await api("/api/orders/" + ord.code + "/cancel", { method: "POST" });
        showToast(res.message);
        await refreshBootstrap();
      } catch (e) {
        showToast(e.message);
      }
    });

    document.getElementById("btn-submit-shot").addEventListener("click", async () => {
      const ord = state.boot && state.boot.open_order;
      const input = document.getElementById("shot-input");
      if (!ord) return;
      if (!input.files || !input.files[0]) {
        showToast("📸 ကျေးဇူးပြု၍ ငွေလွှဲပြေစာ Screenshot ပုံ ရွေးပေးပါ။");
        return;
      }
      haptic("medium");
      try {
        const dataUrl = await readFileAsDataUrl(input.files[0]);
        const res = await api("/api/orders/" + ord.code + "/screenshot", {
          method: "POST",
          body: { image_data_url: dataUrl },
        });
        haptic("success");
        showToast("✨ Key ချက်ချင်း ထုတ်ပေးပြီးပါပြီ!");
        input.value = "";
        await refreshBootstrap();
        switchTab("key");
      } catch (e) {
        haptic("error");
        showToast(e.message);
      }
    });

    document.getElementById("btn-adm-refresh").addEventListener("click", loadAdminOverview);

    document.getElementById("btn-add-panel").addEventListener("click", async () => {
      try {
        const body = {
          name: document.getElementById("p-name").value.trim(),
          base_url: document.getElementById("p-url").value.trim(),
          server_host: document.getElementById("p-host").value.trim(),
          username: document.getElementById("p-user").value.trim(),
          password: document.getElementById("p-pass").value,
          inbound_remark: document.getElementById("p-remark").value.trim() || "exabytetgbot",
        };
        const res = await api("/api/admin/panels", { method: "POST", body: body });
        showToast(res.message);
        loadAdminOverview();
      } catch (e) {
        showToast(e.message);
      }
    });

    document.getElementById("btn-save-cfg").addEventListener("click", async () => {
      try {
        const body = {
          kbz_number: document.getElementById("cfg-kbz-num").value,
          kbz_name: document.getElementById("cfg-kbz-name").value,
          support_url: document.getElementById("cfg-support").value,
          tagline: document.getElementById("cfg-tagline").value,
          maintenance: document.getElementById("cfg-maint").checked,
        };
        const res = await api("/api/admin/settings", { method: "POST", body: body });
        showToast(res.message);
        refreshBootstrap();
      } catch (e) {
        showToast(e.message);
      }
    });

    document.getElementById("btn-send-bcast").addEventListener("click", async () => {
      const txt = document.getElementById("bcast-input").value.trim();
      if (!txt) return;
      try {
        const res = await api("/api/admin/broadcast", { method: "POST", body: { text: txt } });
        document.getElementById("bcast-input").value = "";
        showToast(res.message);
      } catch (e) {
        showToast(e.message);
      }
    });

    refreshBootstrap();
  });
})();
