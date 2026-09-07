// GitHub Analytics - front end.
// No build step and no framework: three screens that read the JSON the API
// already returns. State lives in one object; every change re-renders.

const PER_PAGE = 5;

// sized to look distinct on the navy ground, cycled if a user has more languages
const LANG_COLORS = ["#d9a441", "#7fb2d9", "#c98a8a", "#8fbf9f", "#b39ddb", "#d4b483"];

const state = {
  view: "dashboard",   // "dashboard" | "repo"
  repoName: null,      // set when view === "repo"
  page: 1,
  language: null,
  data: null,
};

const app = document.getElementById("app");

// ---------- helpers ----------

const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );

// "2026-08-01T00:00:00+00:00" -> "2026-08"
const monthLabel = (iso) => String(iso).slice(0, 7);

const dateLabel = (iso) =>
  new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });

async function getJSON(url) {
  const res = await fetch(url, { credentials: "same-origin" });
  return res.json();
}

// ---------- pagination window ----------
// Always at most three numbers, current one centred, clamped to the real range.
// 5 pages, on page 1 -> [1,2,3];  on page 3 -> [2,3,4];  on page 5 -> [3,4,5]
function pageWindow(current, total) {
  if (total <= 3) return Array.from({ length: total }, (_, i) => i + 1);
  let start = Math.min(Math.max(current - 1, 1), total - 2);
  return [start, start + 1, start + 2];
}

function renderPager(current, total, onGo) {
  if (total <= 1) return "";
  const win = pageWindow(current, total);
  const parts = [];

  parts.push(
    `<button data-page="${current - 1}" ${current === 1 ? "disabled" : ""} aria-label="Previous page">&lt;</button>`
  );
  if (win[0] > 1) parts.push(`<span class="gap">...</span>`);

  for (const p of win) {
    parts.push(
      `<button data-page="${p}" ${p === current ? 'aria-current="page"' : ""}>${p}</button>`
    );
  }

  if (win[win.length - 1] < total) parts.push(`<span class="gap">...</span>`);
  parts.push(
    `<button data-page="${current + 1}" ${current === total ? "disabled" : ""} aria-label="Next page">&gt;</button>`
  );

  return `<div class="pager">${parts.join("")}</div>`;
}

// ---------- screens ----------

function renderLoggedOut() {
  app.innerHTML = `
    <div class="wrap">
      <div id="landing">
        <h1>GitHub Analytics</h1>
        <p class="bio">Sign in to see your repositories, languages, and commit activity.</p>
        <p style="margin-top:1rem"><a class="login-cta" href="/auth/github">Log in with GitHub</a></p>
      </div>
    </div>`;
}

function renderLanguageBar(languages) {
  if (!languages.length) return `<p class="empty">No languages detected.</p>`;
  const total = languages.reduce((sum, l) => sum + l.repo_count, 0);

  const segs = languages
    .map((l, i) => {
      const pct = (l.repo_count / total) * 100;
      const color = LANG_COLORS[i % LANG_COLORS.length];
      // hide the label on slivers too narrow to read
      const label = pct >= 12 ? `${esc(l.language)} ${Math.round(pct)}%` : "";
      return `<div class="seg" style="width:${pct}%;background:${color}"
                   title="${esc(l.language)} - ${l.repo_count} repo(s)">${label}</div>`;
    })
    .join("");

  const key = languages
    .map(
      (l, i) =>
        `<span><i style="background:${LANG_COLORS[i % LANG_COLORS.length]}"></i>${esc(l.language)} (${l.repo_count})</span>`
    )
    .join("");

  return `<div class="langbar">${segs}</div><div class="langkey">${key}</div>`;
}

function renderActivity(activities) {
  if (!activities.length) return `<p class="empty">No commit activity yet.</p>`;

  // API returns newest first; take the six most recent months present, show oldest -> newest.
  // Months with no commits simply are not in the data, so every bar is labelled with its
  // real month rather than assuming the six are consecutive.
  const months = activities.slice(0, 6).reverse();
  const max = Math.max(...months.map((m) => m.commit_count));

  const cols = months
    .map((m) => {
      const h = (m.commit_count / max) * 100;
      return `<div class="col">
                <span class="count">${m.commit_count}</span>
                <div class="bar" style="height:${h}%"></div>
                <span class="month">${monthLabel(m.month)}</span>
              </div>`;
    })
    .join("");

  return `<div class="chart">${cols}</div>`;
}

function renderRepoList(repos) {
  if (!repos.length) return `<p class="empty">No repositories match.</p>`;
  return repos
    .map(
      (r) => `
      <button class="repo" data-repo="${esc(r.name)}">
        <span>
          <span class="name">${esc(r.name)}</span>
          ${r.language ? `<div class="desc">${esc(r.language)}</div>` : ""}
        </span>
        <span class="meta"><b>${r.commit_count}</b> commits &nbsp; ★ ${r.stars}</span>
      </button>`
    )
    .join("");
}

function renderDashboard(d) {
  const totalPages = Math.max(1, Math.ceil(d.pagination.total / d.pagination.per_page));
  const langOptions = d.languages
    .map(
      (l) =>
        `<option value="${esc(l.language)}" ${state.language === l.language ? "selected" : ""}>${esc(l.language)}</option>`
    )
    .join("");

  app.innerHTML = `
    <div class="wrap">
      <div class="topbar"><button id="logout">Log out</button></div>

      <div id="landing">
        <img class="avatar" src="${esc(d.avatar_url)}" alt="" />
        <h1>${esc(d.name || d.login)}</h1>
        <div class="login-name">@${esc(d.login)}</div>
        ${d.bio ? `<p class="bio">${esc(d.bio)}</p>` : ""}
        <button class="scroll-cue" id="scroll-cue">
          <span>Scroll for analytics</span><span class="arrow">&#8595;</span>
        </button>
      </div>

      <section id="summary">
        <h2>Languages by repository</h2>
        ${renderLanguageBar(d.languages)}
      </section>

      <section>
        <h2>Commit activity</h2>
        ${renderActivity(d.activities)}
      </section>

      <section>
        <h2>Repositories</h2>
        <div class="filter">
          <select id="lang-filter">
            <option value="">All languages</option>
            ${langOptions}
          </select>
        </div>
        ${renderRepoList(d.repos)}
        ${renderPager(d.pagination.page, totalPages)}
      </section>
    </div>`;

  document.getElementById("scroll-cue").onclick = () =>
    document.getElementById("summary").scrollIntoView({ behavior: "smooth" });

  document.getElementById("lang-filter").onchange = (e) => {
    state.language = e.target.value || null;
    state.page = 1;
    load();
  };

  bindPager();
  bindRepoButtons();
  bindLogout();
}

function renderRepoDetail(d) {
  const totalPages = Math.max(1, Math.ceil(d.pagination.total / d.pagination.per_page));
  const r = d.repo;

  const commits = d.commits.length
    ? d.commits
        .map(
          (c) => `
        <div class="commit">
          <div class="msg">${esc(c.message)}</div>
          <div class="meta">
            <span>${esc(c.author_name)}</span>
            <span>${dateLabel(c.committed_at)}</span>
            <a href="${esc(c.html_url)}" target="_blank" rel="noopener">${esc(c.sha).slice(0, 7)}</a>
          </div>
        </div>`
        )
        .join("")
    : `<p class="empty">No commits stored for this repository.</p>`;

  app.innerHTML = `
    <div class="wrap">
      <div class="topbar"><button id="logout">Log out</button></div>
      <section>
        <button class="backbtn" id="back">&larr; Back to dashboard</button>
        <div class="detail-head">
          <h1>${esc(r.name)}</h1>
          ${r.description ? `<p class="desc">${esc(r.description)}</p>` : ""}
          <div class="stats">
            <span><b>${r.commit_count}</b> commits</span>
            <span><b>${r.stars}</b> stars</span>
            ${r.language ? `<span>${esc(r.language)}</span>` : ""}
            ${r.pushed_at ? `<span>last push ${dateLabel(r.pushed_at)}</span>` : ""}
            <a href="${esc(r.url)}" target="_blank" rel="noopener">View on GitHub</a>
          </div>
        </div>
        ${commits}
        ${renderPager(d.pagination.page, totalPages)}
      </section>
    </div>`;

  document.getElementById("back").onclick = () => {
    state.view = "dashboard";
    state.repoName = null;
    state.page = 1;
    load();
  };

  bindPager();
  bindLogout();
}

// ---------- wiring ----------

function bindPager() {
  document.querySelectorAll(".pager button[data-page]").forEach((btn) => {
    btn.onclick = () => {
      state.page = Number(btn.dataset.page);
      load();
      window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
    };
  });
}

function bindRepoButtons() {
  document.querySelectorAll(".repo[data-repo]").forEach((btn) => {
    btn.onclick = () => {
      state.view = "repo";
      state.repoName = btn.dataset.repo;
      state.page = 1;
      load();
      window.scrollTo({ top: 0 });
    };
  });
}

function bindLogout() {
  document.getElementById("logout").onclick = async () => {
    await fetch("/logout", { credentials: "same-origin" });
    location.reload();
  };
}

// ---------- entry ----------

async function load() {
  const url =
    state.view === "repo"
      ? `/dashboard/${encodeURIComponent(state.repoName)}?page=${state.page}&per_page=${PER_PAGE}`
      : `/dashboard?page=${state.page}&per_page=${PER_PAGE}` +
        (state.language ? `&language=${encodeURIComponent(state.language)}` : "");

  const data = await getJSON(url);

  if (data.error === "Not Logged In") return renderLoggedOut();
  if (data.error) {
    app.innerHTML = `<div class="wrap"><section><p class="empty">${esc(data.error)}</p></section></div>`;
    return;
  }

  state.data = data;
  state.view === "repo" ? renderRepoDetail(data) : renderDashboard(data);
}

load();
