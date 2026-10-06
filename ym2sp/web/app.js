"use strict";

const $ = (id) => document.getElementById(id);
const api = () => window.pywebview.api;

const STATUS_LABELS = {
  added: "Добавлен",
  exists: "Уже был",
  duplicate: "Дубликат",
  not_found: "Не найден",
  error: "Ошибка",
};
const MAX_ROWS = 2000;

const state = {
  busy: false,
  hasLibrary: false,
  spotifyUser: null,
  playlists: [],
  results: [],
  filter: "all",
  dryRun: false,
};

function escapeHtml(text) {
  return String(text ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

function formatDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return isNaN(d) ? "—" : d.toLocaleString("ru-RU", { dateStyle: "medium", timeStyle: "short" });
}

let toastTimer;
function toast(message, isError = false) {
  const el = $("toast");
  el.textContent = message;
  el.classList.toggle("error", isError);
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 4500);
}

async function call(method, ...args) {
  try {
    const res = await api()[method](...args);
    if (res && res.ok === false && res.error) toast(res.error, true);
    return res;
  } catch (e) {
    toast(String(e), true);
    return { ok: false };
  }
}

// ---------- журнал и прогресс ----------

function log(message, level = "info", time = new Date().toLocaleTimeString("ru-RU")) {
  const list = $("log");
  const li = document.createElement("li");
  li.className = level;
  li.innerHTML = `<time>${escapeHtml(time)}</time>${escapeHtml(message)}`;
  const atBottom = list.scrollHeight - list.scrollTop - list.clientHeight < 40;
  list.appendChild(li);
  if (atBottom) list.scrollTop = list.scrollHeight;
}

function setProgress(current, total, text) {
  const bar = $("progress-bar");
  bar.classList.remove("indeterminate");
  bar.style.width = total ? `${Math.min(100, (current / total) * 100)}%` : "0";
  $("progress-text").textContent = total ? `${current} / ${total} · ${text || ""}` : (text || "");
}

// ---------- состояние UI ----------

function render() {
  const busy = state.busy;
  $("btn-fetch").disabled = busy;
  $("btn-connect").disabled = busy;
  $("btn-connect").textContent = state.spotifyUser ? "Переподключить" : "Подключить Spotify";
  $("btn-logout").hidden = !state.spotifyUser;
  $("sp-user").textContent = state.spotifyUser || "не подключен";
  $("sync-form").disabled = busy || !state.spotifyUser;
  $("btn-sync").disabled = busy || !state.hasLibrary;
  $("btn-sync").textContent = $("opt-dry").checked ? "Проверить (пробный запуск)" : "Перенести";
  $("btn-cancel").hidden = !busy;

  const mode = document.querySelector("input[name=mode]:checked").value;
  document.querySelectorAll("[data-mode]").forEach((el) => { el.hidden = el.dataset.mode !== mode; });
}

function renderLibrary(library) {
  state.hasLibrary = Boolean(library && library.count);
  $("ya-account").textContent = library?.account || "—";
  $("ya-count").textContent = library ? library.count : "—";
  $("ya-date").textContent = formatDate(library?.fetched_at);
  render();
}

function renderPlaylists() {
  const select = $("playlist-select");
  const previous = select.value;
  select.innerHTML = state.playlists.length
    ? state.playlists.map((p) => `<option value="${escapeHtml(p.id)}">${escapeHtml(p.name)} (${p.total})</option>`).join("")
    : '<option value="">Нет доступных плейлистов</option>';
  if (state.playlists.some((p) => p.id === previous)) select.value = previous;
}

function renderStats(summary) {
  $("stats").hidden = false;
  for (const key of ["total", "added", "exists", "duplicate", "not_found", "error"]) {
    $(`st-${key}`).textContent = summary[key];
  }
  $("st-added-label").textContent = summary.dry_run ? "будет добавлено" : "добавлено";
}

function trackCell(t, url) {
  if (!t) return '<span class="sub">—</span>';
  const name = `${escapeHtml(t.artists.join(", "))} — ${escapeHtml(t.title)}`;
  const main = url ? `<a href="#" data-open="${escapeHtml(url)}">${name}</a>` : name;
  return `${main}<div class="sub">${escapeHtml(t.album || "")}</div>`;
}

function renderResults() {
  const query = $("filter-text").value.trim().toLowerCase();
  const rows = state.results.filter((r) => {
    if (state.filter !== "all" && r.status !== state.filter) return false;
    if (!query) return true;
    const hay = [r.yandex.title, ...r.yandex.artists, r.spotify?.title, ...(r.spotify?.artists || [])]
      .join(" ").toLowerCase();
    return hay.includes(query);
  });

  const label = (r) => (r.status === "added" && state.dryRun ? "Будет добавлен" : STATUS_LABELS[r.status]);
  $("results-body").innerHTML = rows.slice(0, MAX_ROWS).map((r) => `
    <tr>
      <td><span class="status ${r.status}">${label(r)}</span></td>
      <td>${trackCell(r.yandex)}</td>
      <td>${r.error ? `<span class="sub">${escapeHtml(r.error)}</span>` : trackCell(r.spotify, r.spotify?.url)}</td>
    </tr>`).join("");

  const empty = $("results-empty");
  empty.hidden = rows.length > 0 && rows.length <= MAX_ROWS;
  empty.textContent = rows.length > MAX_ROWS
    ? `Показаны первые ${MAX_ROWS} из ${rows.length}. Уточните поиск.`
    : (state.results.length ? "Ничего не найдено" : "Результатов пока нет");
}

function switchTab(name) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  $("tab-log").hidden = name !== "log";
  $("tab-results").hidden = name !== "results";
}

// ---------- события из Python ----------

window.app = {
  onEvent(e) {
    switch (e.event) {
      case "log":
        log(e.message, e.level, e.time);
        break;
      case "progress":
        setProgress(e.current, e.total, e.text);
        break;
      case "busy":
        state.busy = e.busy;
        if (e.busy) {
          $("progress-bar").classList.add("indeterminate");
          $("progress-text").textContent = "Выполняется…";
        } else if ($("progress-bar").classList.contains("indeterminate")) {
          $("progress-bar").classList.remove("indeterminate");
          $("progress-text").textContent = "Готов к работе";
        }
        render();
        break;
      case "library":
        renderLibrary(e.library);
        break;
      case "spotify":
        state.spotifyUser = e.user;
        state.playlists = e.playlists || [];
        renderPlaylists();
        render();
        break;
      case "result":
        state.results = e.results;
        state.dryRun = e.summary.dry_run;
        renderStats(e.summary);
        renderResults();
        $("results-badge").hidden = false;
        $("results-badge").textContent = e.results.length;
        switchTab("results");
        toast(e.summary.dry_run ? "Пробный запуск завершен" : "Готово!");
        break;
      case "error":
        toast(e.message, true);
        break;
    }
  },
};

// ---------- настройки ----------

function openSettings(creds) {
  const form = $("settings-form");
  for (const [key, value] of Object.entries(creds)) {
    if (form.elements[key]) form.elements[key].value = value || "";
  }
  $("settings-error").textContent = "";
  $("settings-dialog").showModal();
}

async function saveSettings(event) {
  event.preventDefault();
  const form = $("settings-form");
  const data = Object.fromEntries(
    ["yandex_token", "spotify_client_id", "spotify_client_secret", "spotify_redirect_uri"]
      .map((k) => [k, form.elements[k].value])
  );
  const res = await api().save_settings(data);
  if (!res.ok) {
    $("settings-error").textContent = res.error;
    return;
  }
  $("settings-dialog").close();
  state.spotifyUser = res.state.spotify_user;
  render();
  toast("Настройки сохранены");
}

// ---------- инициализация ----------

function bindUi() {
  $("btn-fetch").onclick = () => { switchTab("log"); call("fetch_yandex"); };
  $("btn-connect").onclick = () => { switchTab("log"); call("connect_spotify"); };
  $("btn-refresh").onclick = (e) => { e.preventDefault(); call("refresh_playlists"); };
  $("btn-cancel").onclick = () => call("cancel");
  $("btn-data").onclick = () => call("open_data_dir");
  $("btn-logout").onclick = async () => {
    const res = await call("logout_spotify");
    if (res.ok) {
      state.spotifyUser = null;
      state.playlists = [];
      renderPlaylists();
      render();
      log("Выход из Spotify выполнен");
    }
  };

  $("btn-sync").onclick = () => {
    const mode = document.querySelector("input[name=mode]:checked").value;
    const selected = state.playlists.find((p) => p.id === $("playlist-select").value);
    switchTab("log");
    call("start_sync", {
      mode,
      playlist_id: mode === "existing" ? $("playlist-select").value : "",
      playlist_name: mode === "existing" ? (selected?.name || "") : $("playlist-name").value,
      public: $("opt-public").checked,
      to_top: $("opt-top").checked,
      dry_run: $("opt-dry").checked,
      use_cache: $("opt-cache").checked,
    });
  };

  document.querySelectorAll("input[name=mode], #opt-dry").forEach((el) => { el.onchange = render; });
  document.querySelectorAll(".tab").forEach((t) => { t.onclick = () => switchTab(t.dataset.tab); });
  document.querySelectorAll(".chip").forEach((chip) => {
    chip.onclick = () => {
      state.filter = chip.dataset.filter;
      document.querySelectorAll(".chip").forEach((c) => c.classList.toggle("active", c === chip));
      renderResults();
    };
  });
  $("filter-text").oninput = renderResults;

  $("btn-settings").onclick = async () => openSettings((await api().get_state()).credentials);
  $("settings-form").onsubmit = saveSettings;
  $("settings-cancel").onclick = () => $("settings-dialog").close();
  $("show-secrets").onchange = (e) => {
    for (const name of ["yandex_token", "spotify_client_secret"]) {
      $("settings-form").elements[name].type = e.target.checked ? "text" : "password";
    }
  };

  // Внешние ссылки открываем в системном браузере, а не внутри окна
  document.addEventListener("click", (e) => {
    const link = e.target.closest("[data-open]");
    if (link) {
      e.preventDefault();
      call("open_url", link.dataset.open);
    }
  });
}

window.addEventListener("pywebviewready", async () => {
  bindUi();
  const s = await api().get_state();
  state.busy = s.busy;
  state.spotifyUser = s.spotify_user;
  renderLibrary(s.library);
  renderPlaylists();
  render();
  log(`Yandex Music → Spotify v${s.version}`);

  const c = s.credentials;
  if (!c.yandex_token || !c.spotify_client_id || !c.spotify_client_secret) {
    log("Заполните токены в «Настройках»", "warn");
    openSettings(c);
  }
});
