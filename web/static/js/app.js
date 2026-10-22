// Alpine component chính. Quy tắc: không inline script (CSP), mọi chuỗi hiển thị đi qua t().
const LS = {
  get(k, d) { try { return localStorage.getItem(k) ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* private mode */ } },
};

function errText(data, r) {
  const d = data.detail;
  return typeof d === "string" ? d : (Array.isArray(d) ? d.map(e => e.msg).join("; ") : r.statusText);
}

async function api(path, opts = {}) {
  const r = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(errText(data, r));
  return data;
}

async function upload(path, form) {
  const r = await fetch(path, { method: "POST", credentials: "same-origin", body: form });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(errText(data, r));
  return data;
}

const baseName = (p) => String(p || "").split(/[\\/]/).pop();
const lines = (s) => String(s || "").split("\n").map(x => x.trim()).filter(Boolean);

function app() {
  return {
    lang: LS.get("lang", navigator.language.startsWith("vi") ? "vi" : "en"),
    theme: LS.get("theme", matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"),
    dict: {},
    step: 1,
    error: "", notice: "", busy: false,
    caps: { offline_voice: false, separate: false, translate_api: false },
    langs: [], templates: [],
    upload: { name: "", file: null },
    tpl: null,
    frameT: 1, previewUrl: "", showPreview: false, previewBusy: false,
    picked: [], gender: "f",
    tr: {}, hooksPerLang: 3, pasteReply: "",
    job: { status: "idle", done: 0, total: 0, items: [] },

    async init() {
      document.documentElement.dataset.theme = this.theme;
      await this.setLang(this.lang);
      try {
        [this.caps, this.langs, this.templates] = await Promise.all([
          api("/api/capabilities"), api("/api/langs").then(r => r.items), api("/api/templates").then(r => r.items)]);
      } catch (e) { this.error = e.message; }
      this.$watch("picked", () => this.ensureTr());
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
        // Máy chủ dùng chung: chỉ hiện tiến độ của batch do chính mình bấm chạy.
        if (ev.job && ev.job.batch_id && ev.job.batch_id === this.job.batch_id) this.job = { items: [], ...ev.job };
      };
      ws.onclose = () => setTimeout(() => this.connect(), 1500);
    },

    // ---------- điều hướng ----------
    get usesVoice() { return !!this.tpl && this.tpl.audio_mode !== "original" && this.tpl.voice.length > 0; },
    canGo(s) {
      if (s === 1) return true;
      if (s === 2) return !!this.tpl && this.tpl.captions.length > 0;
      if (s === 3) return this.canGo(2) && this.picked.length > 0;
      return !!this.job.batch_id;
    },
    go(s) { if (this.canGo(s)) { this.error = ""; this.notice = ""; this.step = s; window.scrollTo(0, 0); } },

    // ---------- bước 1 ----------
    async uploadVideo() {
      this.error = ""; this.busy = true;
      try {
        const f = new FormData();
        f.append("video", this.upload.file);
        f.append("name", this.upload.name);
        this.setTemplate(await upload("/api/templates", f));
        this.templates = (await api("/api/templates")).items;
      } catch (e) { this.error = e.message; }
      this.busy = false;
    },
    async openTemplate(id) {
      try { this.setTemplate(await api(`/api/templates/${id}`)); } catch (e) { this.error = e.message; }
    },
    setTemplate(t) {
      // Video mới chưa có caption: tạo sẵn 1 dòng (0 → 4 giây) để người dùng chỉ việc gõ chữ gốc.
      if (!t.captions.length) t.captions.push({ start: 0, end: +Math.min(4, t.duration).toFixed(2), text: "" });
      this.tpl = t;
      this.frameT = Math.min(1, t.duration / 2);
      this.showPreview = false;
      this.refreshFrame();
    },
    closeTemplate() { this.tpl = null; this.picked = []; this.tr = {}; },
    refreshFrame() {
      if (!this.tpl) return;
      if (this.showPreview) return this.previewCaption();
      this.previewUrl = `/api/templates/${this.tpl.id}/frame?t=${this.frameT.toFixed(1)}`;
    },
    async previewCaption() {
      this.error = ""; this.previewBusy = true;
      try {
        const r = await fetch(`/api/templates/${this.tpl.id}/preview`, {
          method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ template: this.tpl, t: this.frameT, text: this.firstHook() }),
        });
        if (!r.ok) throw new Error(errText(await r.json().catch(() => ({})), r));
        if (this.previewUrl.startsWith("blob:")) URL.revokeObjectURL(this.previewUrl);
        this.previewUrl = URL.createObjectURL(await r.blob());
        this.showPreview = true;
      } catch (e) { this.error = e.message; this.previewBusy = false; }
    },
    firstHook() {
      for (const code of this.picked) { const h = lines(this.tr[code]?.hooks)[0]; if (h) return h; }
      return this.tpl.captions[0]?.text || "Caption";
    },
    coverStyle() {
      if (!this.tpl || !this.tpl.cover) return "";
      const c = this.tpl.cover, W = this.tpl.width, H = this.tpl.height;
      return `left:${c.x / W * 100}%;top:${c.y / H * 100}%;width:${c.w / W * 100}%;height:${c.h / H * 100}%`;
    },
    addLine(kind) {
      const arr = this.tpl[kind];
      const start = arr.length ? arr[arr.length - 1].end : 0;
      arr.push({ start: +start.toFixed(2), end: +Math.min(start + 3, this.tpl.duration).toFixed(2), text: "" });
    },
    async saveTemplate(next) {
      this.error = "";
      try {
        this.tpl = await api(`/api/templates/${this.tpl.id}`, { method: "PUT", body: this.tpl });
        this.notice = this.t("common.saved");
        this.ensureTr();
        if (next) this.go(next);
      } catch (e) { this.error = e.message; }
    },
    async uploadMusic(file) {
      if (!file) return;
      try {
        const f = new FormData(); f.append("file", file);
        const saved = await upload(`/api/templates/${this.tpl.id}/music`, f);
        this.tpl.music = saved.music; this.tpl.audio_mode = "music_file";
      } catch (e) { this.error = e.message; }
    },

    // ---------- bước 2–3 ----------
    langName(code) { return this.langs.find(l => l.code === code)?.name || code; },
    isRtl(code) { return !!this.langs.find(l => l.code === code)?.rtl; },
    ensureTr() {
      if (!this.tpl) return;
      for (const code of this.picked) {
        const cur = this.tr[code] || { hooks: "", captions: [], voice: [], syncHook: true };
        cur.captions.length = Math.max(cur.captions.length, this.tpl.captions.length);
        cur.voice.length = Math.max(cur.voice.length, this.tpl.voice.length);
        this.tr[code] = cur;
      }
    },
    hookWarnings(code) {
      const src = this.tpl?.captions[0]?.text || "";
      return lines(this.tr[code]?.hooks)
        .filter(h => src && h.length > src.length * 1.3)
        .map(h => this.t("tr.tooLong").replace("{text}", h.slice(0, 40)));
    },
    variants() {
      if (!this.tpl) return [];
      const out = [];
      for (const code of this.picked) {
        const x = this.tr[code];
        if (!x) continue;
        lines(x.hooks).forEach((hook, i) => {
          const captions = [hook, ...this.tpl.captions.slice(1).map((_, k) => (x.captions[k + 1] || "").trim())];
          const voice = this.usesVoice
            ? this.tpl.voice.map((_, k) => (k === 0 && x.syncHook ? hook : (x.voice[k] || "").trim()))
            : [];
          out.push({ lang: code, gender: this.gender, hook: `h${i + 1}`, captions, voice });
        });
      }
      return out;
    },
    async copyPrompt() {
      try {
        const r = await api("/api/translate/prompt", { method: "POST",
          body: { template_id: this.tpl.id, langs: this.picked, hooks: this.hooksPerLang } });
        await navigator.clipboard.writeText(r.prompt);
        this.notice = this.t("tr.copied");
      } catch (e) { this.error = e.message; }
    },
    fill(result) {
      for (const [code, v] of Object.entries(result)) {
        if (!this.picked.includes(code)) this.picked.push(code);
        this.ensureTr();
        const x = this.tr[code];
        x.hooks = (v.hooks || []).map(h => h[0]).join("\n");
        (v.hooks?.[0] || []).slice(1).forEach((c, k) => { x.captions[k + 1] = c; });
        (v.voice || []).forEach((s, k) => { x.voice[k] = s; });
        x.syncHook = false;
      }
      this.notice = this.t("tr.filled");
    },
    async applyReply() {
      this.error = "";
      try { this.fill((await api("/api/translate/parse", { method: "POST", body: { text: this.pasteReply } })).result); }
      catch (e) { this.error = e.message; }
    },
    async autoTranslate() {
      this.error = ""; this.busy = true;
      try {
        this.fill((await api("/api/translate/auto", { method: "POST",
          body: { template_id: this.tpl.id, langs: this.picked, hooks: this.hooksPerLang } })).result);
      } catch (e) { this.error = e.message; }
      this.busy = false;
    },

    // ---------- bước 4 ----------
    async run(only) {
      this.error = "";
      const variants = only || this.variants();
      const empty = variants.find(v => v.voice.some(s => !s));
      if (empty) { this.error = this.t("tr.missingVoice").replace("{lang}", this.langName(empty.lang)); return; }
      try {
        const r = await api("/api/jobs", { method: "POST", body: { template_id: this.tpl.id, variants } });
        this.job = { status: "running", batch_id: r.batch_id, done: 0, total: variants.length, items: [] };
        this.step = 4;
      } catch (e) { this.error = e.message; }
    },
    async stop() { await api("/api/jobs/stop", { method: "POST" }); },
    fileUrl(it) { return `/api/batches/${this.job.batch_id}/files/${encodeURIComponent(baseName(it.output))}`; },
    fixOne(it) {
      const code = it.lang.split(" ")[0];
      this.go(3);
      this.notice = this.t("res.fixHint").replace("{lang}", this.langName(code));
    },
  };
}
