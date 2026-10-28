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

// Tải file có báo % (fetch không báo được tiến độ upload).
function uploadXhr(path, form, onPct) {
  return new Promise((resolve, reject) => {
    const x = new XMLHttpRequest();
    x.open("POST", path);
    x.withCredentials = true;
    x.upload.onprogress = (e) => { if (e.lengthComputable) onPct(Math.round(e.loaded / e.total * 100)); };
    x.onload = () => {
      let data = {};
      try { data = JSON.parse(x.responseText); } catch { /* không phải JSON */ }
      if (x.status >= 200 && x.status < 300) resolve(data);
      else reject(new Error(errText(data, { statusText: x.statusText || String(x.status) })));
    };
    x.onerror = () => reject(new Error("Mất kết nối tới tool — kiểm tra cửa sổ tool còn chạy không"));
    x.send(form);
  });
}

const clamp = (v, lo, hi) => Math.round(Math.min(Math.max(v, lo), hi));
// Trường dùng chung giữa các video trong nhóm (vị trí chữ + vùng che thì tuỳ ô tick "dùng cùng vị trí").
const SHARED = ["app", "concept", "source_lang", "glossary", "captions", "voice", "cover_mode", "audio_mode", "voice_offset"];
const STYLE_SHARED = ["font", "text_color", "outline_color", "glow", "glow_color", "uppercase", "max_lines"];

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
    upload: { name: "", files: [] },
    uploads: [], group: [], keep: null, samePos: false, drag: null,
    draftId: "", draftReady: false, draftTimer: 0,
    tpl: null,
    frameT: 1, previewUrl: "", showPreview: false, previewBusy: false,
    picked: [], gender: "f",
    tr: {}, hooksPerLang: 3, pasteReply: "", voiceVer: 0,
    job: { status: "idle", done: 0, total: 0, items: [] },

    async init() {
      document.documentElement.dataset.theme = this.theme;
      await this.setLang(this.lang);
      try {
        [this.caps, this.langs, this.templates] = await Promise.all([
          api("/api/capabilities"), api("/api/langs").then(r => r.items), api("/api/templates").then(r => r.items)]);
      } catch (e) { this.error = e.message; }
      this.$watch("picked", () => this.ensureTr());
      await this.restoreDraft();
      this.$watch("draftJson", () => this.queueDraft());
      this.connect();
    },

    t(key) { return this.dict[key] ?? key; },

    // ---------- bản nháp: chỉ mất khi bấm Reset ----------
    get draftJson() {
      return JSON.stringify({ step: Math.min(this.step, 3), tpl: this.tpl, keep: this.keep, group: this.group,
        picked: this.picked, tr: this.tr, gender: this.gender, hooksPerLang: this.hooksPerLang, samePos: this.samePos });
    },
    queueDraft() {
      if (!this.draftReady) return;
      clearTimeout(this.draftTimer);
      this.draftTimer = setTimeout(() => this.saveDraft(), 500);
    },
    async saveDraft() {
      try { await api(`/api/drafts/${this.draftId}`, { method: "PUT", body: JSON.parse(this.draftJson) }); }
      catch (e) { this.error = this.t("draft.saveFail") + " " + e.message; }
    },
    async restoreDraft() {
      this.draftId = LS.get("draftId", "");
      if (!/^[a-z0-9]{12}$/.test(this.draftId)) {
        this.draftId = Array.from(crypto.getRandomValues(new Uint8Array(6)), b => b.toString(16).padStart(2, "0")).join("");
        LS.set("draftId", this.draftId);
      }
      try {
        const d = await api(`/api/drafts/${this.draftId}`);
        const alive = new Set(this.templates.map(x => x.id));
        this.group = (d.group || []).filter(g => alive.has(g.id));
        this.picked = d.picked || []; this.tr = d.tr || {};
        this.gender = d.gender || this.gender; this.hooksPerLang = d.hooksPerLang || this.hooksPerLang;
        this.samePos = !!d.samePos;
        this.keep = d.keep && alive.has(d.keep.id) ? d.keep : null;
        if (d.tpl && alive.has(d.tpl.id)) {
          this.setTemplate(d.tpl);
          this.ensureTr();
          if (d.step > 1 && this.canGo(d.step)) this.step = d.step;
          this.notice = this.t("draft.restored");
        }
      } catch { /* chưa có bản nháp */ }
      this.draftReady = true;
    },
    async resetAll() {
      if (!confirm(this.t("draft.confirmReset"))) return;
      this.startBlank();
      this.step = 1; this.gender = "f"; this.samePos = false; this.upload = { name: "", files: [] };
      this.error = ""; this.notice = this.t("draft.wasReset");
      try { await api(`/api/drafts/${this.draftId}`, { method: "DELETE" }); } catch { /* lần lưu sau sẽ ghi đè */ }
    },
    get hasWork() { return !!(this.tpl || this.keep || this.picked.length); },
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
    get usesVoice() {
      return !!this.tpl && ["separate", "music_file", "none"].includes(this.tpl.audio_mode) && this.tpl.voice.length > 0;
    },
    needsSep(m) { return m === "separate" || m === "uploaded_voice"; },
    canGo(s) {
      if (s === 1) return true;
      if (s === 2) return !!this.tpl && this.tpl.captions.length > 0;
      if (s === 3) return this.canGo(2) && this.picked.length > 0;
      return !!this.job.batch_id;
    },
    go(s) { if (this.canGo(s)) { this.error = ""; this.notice = ""; this.step = s; window.scrollTo(0, 0); } },

    // ---------- bước 1 ----------
    // Tải 1 hoặc nhiều video. Đang mở video (hoặc vừa bấm "Đổi video") → video mới nhận lại chữ đã nhập.
    async uploadVideos(fileList) {
      const files = [...(fileList || [])];
      if (!files.length) return;
      this.error = ""; this.notice = ""; this.busy = true;
      let from = this.tpl || this.keep;
      try { if (this.tpl) from = await this.persist(this.tpl); } catch (e) { this.error = e.message; this.busy = false; return; }
      this.uploads = files.map(f => ({ name: f.name, pct: 0, state: "wait", msg: "" }));
      let first = null;
      for (const [i, f] of files.entries()) {
        const u = this.uploads[i];
        u.state = "up";
        try {
          const fd = new FormData();
          fd.append("video", f);
          fd.append("name", files.length === 1 && this.upload.name ? this.upload.name : f.name.replace(/\.[^.]+$/, ""));
          if (from) fd.append("copy_from", from.id);
          const t = await uploadXhr("/api/templates", fd, (pct) => { u.pct = pct; });
          u.state = "ok"; u.pct = 100; u.msg = (t.warnings || []).join(" · ");
          delete t.warnings;
          if (!this.tpl && !first) this.group = [];
          this.group.push({ id: t.id, name: t.name });
          first = first || t;
          from = from || t;
        } catch (e) { u.state = "err"; u.msg = e.message; }
      }
      if (!this.tpl && first) this.setTemplate(first);
      if (first) this.keep = null;
      this.upload = { name: "", files: [] };
      if (this.$refs.fileIn) this.$refs.fileIn.value = "";
      try { this.templates = (await api("/api/templates")).items; } catch { /* danh sách cập nhật sau */ }
      this.busy = false;
    },
    async openTemplate(id) {
      try {
        const t = await api(`/api/templates/${id}`);
        const src = this.tpl || this.keep;
        this.group = [{ id: t.id, name: t.name }]; this.keep = null;
        // Đang có chữ đã nhập → video mở ra dùng lại chữ đó (chỉ nút Reset mới xoá chữ).
        const has = src && src.captions.some(c => (c.text || "").trim());
        this.setTemplate(has && src.id !== t.id ? this.applyShared(src, t) : t);
      } catch (e) { this.error = e.message; }
    },
    setTemplate(t) {
      // Video mới chưa có caption: tạo sẵn 1 dòng (0 → 4 giây) để người dùng chỉ việc gõ chữ gốc.
      if (!t.captions.length) t.captions.push({ start: 0, end: +Math.min(4, t.duration).toFixed(2), text: "" });
      if (!this.group.some(g => g.id === t.id)) this.group.push({ id: t.id, name: t.name });
      this.tpl = t;
      this.frameT = Math.min(1, t.duration / 2);
      this.showPreview = false;
      this.refreshFrame();
    },
    // "Đổi video": giữ chữ, kiểu chữ, bản dịch để video tải lên sau dùng lại.
    async closeTemplate() {
      try { this.keep = await this.persist(this.tpl); } catch { this.keep = this.tpl; }
      this.tpl = null; this.group = []; this.uploads = [];
    },
    startBlank() { this.keep = null; this.tpl = null; this.group = []; this.uploads = []; this.picked = []; this.tr = {}; },
    async persist(t) {
      return api(`/api/templates/${t.id}`, { method: "PUT", body: t });
    },
    // Chép phần dùng chung từ video đang sửa sang video khác (vị trí co giãn theo độ phân giải).
    applyShared(src, dst) {
      const out = JSON.parse(JSON.stringify(dst));
      for (const k of SHARED) out[k] = JSON.parse(JSON.stringify(src[k]));
      out.captions = out.captions.filter(c => c.start < dst.duration - 0.05).map(c => ({ ...c, end: Math.min(c.end, +dst.duration.toFixed(2)) }));
      out.voice = out.voice.filter(c => c.start < dst.duration - 0.05).map(c => ({ ...c, end: Math.min(c.end, +dst.duration.toFixed(2)) }));
      const kx = dst.width / src.width, ky = dst.height / src.height;
      for (const k of STYLE_SHARED) out.style[k] = src.style[k];
      out.style.size = clamp(src.style.size * ky, 10, 300);
      out.style.outline = Math.min(20, +(src.style.outline * ky).toFixed(1));
      if (this.samePos) {
        out.style.center_x = clamp(src.style.center_x * kx, 0, dst.width);
        out.style.center_y = clamp(src.style.center_y * ky, 0, dst.height);
        out.style.max_width = clamp(src.style.max_width * kx, 1, dst.width * 4);
        if (src.cover) {
          const x = clamp(src.cover.x * kx, 0, dst.width - 1), y = clamp(src.cover.y * ky, 0, dst.height - 1);
          out.cover = { x, y, w: clamp(src.cover.w * kx, 1, dst.width - x), h: clamp(src.cover.h * ky, 1, dst.height - y) };
        } else out.cover = null;
      }
      return out;
    },
    async syncGroup() {
      for (const g of this.group) {
        if (g.id === this.tpl.id) continue;
        try {
          const other = await api(`/api/templates/${g.id}`);
          await this.persist(this.applyShared(this.tpl, other));
        } catch (e) { throw new Error(`${g.name}: ${e.message}`); }
      }
    },
    async switchTo(id) {
      if (!this.tpl || id === this.tpl.id) return;
      this.error = "";
      try {
        const cur = await this.persist(this.tpl);
        const next = await api(`/api/templates/${id}`);
        this.setTemplate(this.applyShared(cur, next));
      } catch (e) { this.error = e.message; }
    },
    removeFromGroup(id) {
      if (this.group.length < 2) return;
      this.group = this.group.filter(g => g.id !== id);
      if (this.tpl.id === id) this.openOther(this.group[0].id);
    },
    async openOther(id) {
      try { this.setTemplate(this.applyShared(this.tpl, await api(`/api/templates/${id}`))); } catch (e) { this.error = e.message; }
    },

    // ---------- kéo thả khung chữ mới / vùng che ----------
    capRect() {
      const s = this.tpl.style, h = s.size * 1.3 * Math.min(s.max_lines, 2);
      return { x: s.center_x - s.max_width / 2, y: s.center_y - h / 2, w: s.max_width, h };
    },
    boxStyle(b) {
      const W = this.tpl.width, H = this.tpl.height;
      return `left:${b.x / W * 100}%;top:${b.y / H * 100}%;width:${b.w / W * 100}%;height:${b.h / H * 100}%`;
    },
    startDrag(e, what, mode) {
      const rect = this.$refs.frame.getBoundingClientRect();
      const s = this.tpl.style;
      this.drag = { what, mode, sx: e.clientX, sy: e.clientY, k: this.tpl.width / rect.width,
        o: what === "cap" ? { cx: s.center_x, cy: s.center_y, w: s.max_width } : { ...this.tpl.cover } };
    },
    onDrag(e) {
      const d = this.drag;
      if (!d || !this.tpl) return;
      this.move(d.what, d.mode, (e.clientX - d.sx) * d.k, (e.clientY - d.sy) * d.k, d.o);
    },
    move(what, mode, dx, dy, o) {
      const W = this.tpl.width, H = this.tpl.height, s = this.tpl.style, c = this.tpl.cover;
      if (what === "cap" && mode === "move") {
        // Giữ cả khung chữ nằm trong video, không để chữ bị cắt ở mép.
        const r = this.capRect(), hw = Math.min(r.w, W) / 2, hh = Math.min(r.h, H) / 2;
        s.center_x = clamp(o.cx + dx, hw, W - hw); s.center_y = clamp(o.cy + dy, hh, H - hh);
      } else if (what === "cap") {
        s.max_width = clamp(o.w + 2 * dx, 40, 2 * Math.min(s.center_x, W - s.center_x));
      }
      else if (mode === "move") { c.x = clamp(o.x + dx, 0, W - o.w); c.y = clamp(o.y + dy, 0, H - o.h); }
      else { c.w = clamp(o.w + dx, 10, W - o.x); c.h = clamp(o.h + dy, 10, H - o.y); }
    },
    endDrag() {
      if (!this.drag) return;
      this.drag = null;
      if (this.showPreview) this.previewCaption();
    },
    nudge(e, what) {
      const step = e.shiftKey ? 20 : 4;
      const dir = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] }[e.key];
      if (!dir) return;
      e.preventDefault();
      const s = this.tpl.style;
      this.move(what, "move", dir[0], dir[1], what === "cap" ? { cx: s.center_x, cy: s.center_y } : { ...this.tpl.cover });
    },
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
    addLine(kind) {
      const arr = this.tpl[kind];
      const start = arr.length ? arr[arr.length - 1].end : 0;
      arr.push({ start: +start.toFixed(2), end: +Math.min(start + 3, this.tpl.duration).toFixed(2), text: "" });
    },
    async saveTemplate(next) {
      this.error = "";
      try {
        this.tpl = await this.persist(this.tpl);
        await this.syncGroup();
        this.notice = this.group.length > 1 ? this.t("group.savedAll").replace("{n}", this.group.length) : this.t("common.saved");
        this.ensureTr();
        if (next) this.go(next);
      } catch (e) { this.error = e.message; }
    },
    async uploadVoice(file) {
      if (!file) return;
      this.error = "";
      try {
        let saved;
        for (const id of [this.tpl.id, ...this.group.map(g => g.id).filter(x => x !== this.tpl.id)]) {
          const f = new FormData(); f.append("file", file);
          const r = await upload(`/api/templates/${id}/voicefile`, f);  // dùng chung cho mọi video trong nhóm
          saved = saved || r;
        }
        this.tpl.voice_file = saved.voice_file; this.tpl.audio_mode = "uploaded_voice"; this.voiceVer++;
        this.notice = this.t("audio.voiceUploaded");
      } catch (e) { this.error = e.message; }
    },
    async uploadMusic(file) {
      if (!file) return;
      try {
        let saved;
        for (const id of [this.tpl.id, ...this.group.map(g => g.id).filter(x => x !== this.tpl.id)]) {
          const f = new FormData(); f.append("file", file);
          const r = await upload(`/api/templates/${id}/music`, f);
          saved = saved || r;
        }
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
        this.tpl = await this.persist(this.tpl);
        await this.syncGroup();
        const ids = this.group.map(g => g.id);
        const r = await api("/api/jobs", { method: "POST", body: { template_id: this.tpl.id, template_ids: ids, variants } });
        this.job = { status: "running", batch_id: r.batch_id, done: 0, total: variants.length * ids.length, items: [] };
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
