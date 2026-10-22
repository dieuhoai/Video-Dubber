// Alpine component chính. Quy tắc: không inline script (CSP), mọi chuỗi hiển thị đi qua t().
const LS = {
  get(k, d) { try { return localStorage.getItem(k) ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* private mode */ } },
};

async function api(path, opts = {}) {
  const r = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    const d = data.detail;
    throw new Error(typeof d === "string" ? d : (Array.isArray(d) ? d.map(e => e.msg).join("; ") : r.statusText));
  }
  return data;
}

function app() {
  return {
    lang: LS.get("lang", navigator.language.startsWith("vi") ? "vi" : "en"),
    theme: LS.get("theme", matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"),
    dict: {},
    presets: [],
    form: { input_dir: "", output_dir: "", preset: "default" },
    job: { status: "idle", done: 0, total: 0, failed: [] },
    error: "",

    get canRun() { return this.form.input_dir && this.form.output_dir && this.form.preset; },

    async init() {
      document.documentElement.dataset.theme = this.theme;
      await this.setLang(this.lang);
      try { this.presets = (await api("/api/presets")).names; } catch (e) { this.error = e.message; }
      this.connect();
    },

    t(key) { return this.dict[key] ?? key; },

    async setLang(l) {
      this.lang = l; LS.set("lang", l);
      document.documentElement.lang = l;
      this.dict = await (await fetch(`/static/i18n/${l}.json`)).json();
    },

    toggleTheme() {
      this.theme = this.theme === "dark" ? "light" : "dark";
      document.documentElement.dataset.theme = this.theme; LS.set("theme", this.theme);
    },

    connect() {
      const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
      ws.onmessage = (m) => {
        const ev = JSON.parse(m.data);
        if (ev.job) this.job = { failed: [], ...ev.job };
      };
      ws.onclose = () => setTimeout(() => this.connect(), 1500);
    },

    async pick(field) {
      try {
        const r = await api("/api/fs/pick", { method: "POST", body: { kind: "dir", initial: this.form[field] } });
        if (r.path) this.form[field] = r.path;
      } catch (e) { this.error = e.message; }
    },

    async run() {
      this.error = "";
      try {
        const preset = await api(`/api/presets/${encodeURIComponent(this.form.preset)}`);
        await api("/api/jobs", { method: "POST", body: { input_dir: this.form.input_dir, output_dir: this.form.output_dir, preset } });
      } catch (e) { this.error = e.message; }
    },

    async stop() { await api("/api/jobs/stop", { method: "POST" }); },
  };
}
