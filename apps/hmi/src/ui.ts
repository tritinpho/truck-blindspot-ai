// DOM chrome + view router (ADR-0009: hand-rolled, no framework). Owns the status bar (title,
// alive pip, health, mute, settings/diagnostics access), the primary-alert banner, the warming-up
// overlay, and the two secondary views: Settings/Calibration (FR-12) and hidden Diagnostics (NFR-11).
// The Canvas scene is rendered separately (scene.ts); this module is everything around it.

import type { Health, Lang, ObjectClass, Severity, SystemPhase, ThemeMode, ViewName } from "./types";
import type { SceneConfig } from "./config";
import type { AppState } from "./store";
import { SEVERITY, THEME, getThemeMode } from "./theme";
import { className, t, zoneName } from "./i18n";

export interface UICallbacks {
  toggleMute(): void;
  setVolume(v: number): void;
  setLang(l: Lang): void;
  setTheme(m: ThemeMode): void;
  setView(v: ViewName): void;
  setThreshold(zoneId: string, caution_m: number, danger_m: number): void;
  setZoneEnabled(zoneId: string, enabled: boolean): void;
  userGesture(): void;
}

export interface BannerVM {
  severity: Severity;
  zoneId: string;
  rangeM: number | null;
  objectClass: ObjectClass;
}

export interface RenderVM {
  phase: SystemPhase;
  live: boolean;
  animMs: number;
  banner: BannerVM | null;
  health: Health | null;
  muted: boolean;
  muteRemainingS: number;
  audioSuspended: boolean;
}

function el<T extends HTMLElement>(id: string): T {
  const e = document.getElementById(id);
  if (!e) throw new Error(`missing #${id}`);
  return e as T;
}

/** HTML-escape a wire-derived string before it goes into innerHTML. The broker is anonymous, so
 * any node can publish a sensor_id / modality / health / reason; without this they would inject
 * markup into the kiosk DOM (the diagnostics table is built with innerHTML). */
function esc(v: unknown): string {
  return String(v ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
}

export class UI {
  private cfg: SceneConfig;
  private cb: UICallbacks;
  private state: AppState;

  private pip = el("pip");
  private health = el("health");
  private soundHint = el("soundHint");
  private muteBtn = el<HTMLButtonElement>("mute");
  private banner = el("banner");
  private overlay = el("overlay");
  private diagBody = el("diagBody");
  private diagRate = el("diagRate");
  private titleEl = el("title");

  private lpTimer = 0;

  constructor(cfg: SceneConfig, state: AppState, cb: UICallbacks) {
    this.cfg = cfg;
    this.state = state;
    this.cb = cb;
    this.buildSettings();
    this.wireChrome();
    this.applyStaticText();
    this.showView("drive");
  }

  // --- static labels that depend on language ---
  private applyStaticText(): void {
    el("warmingTitle").textContent = t("warming");
    el("warmingSub").textContent = t("warming_sub");
    el("settingsTitle").textContent = t("settings");
    el("diagTitle").textContent = t("diagnostics");
    el("settingsBack").textContent = `‹ ${t("back")}`;
    el("diagBack").textContent = `‹ ${t("back")}`;
    el("volLabel").textContent = t("volume");
    el("langLabel").textContent = t("language");
    el("themeLabel").textContent = t("theme");
    el<HTMLSelectElement>("theme").querySelectorAll("option").forEach(
      (o) => { o.textContent = t(`theme_${o.value}`); });
    el("thresholdsLabel").textContent = t("thresholds");
    this.soundHint.textContent = `🔇 ${t("sound_hint")}`;
    // diagnostics header
    const cells = [t("zone"), t("severity"), t("range"), t("age"), t("present"), t("health")];
    el("diagHead").innerHTML = cells.map((c) => `<th>${c}</th>`).join("");
    this.rebuildSettingsLabels();
  }

  // --- view routing ---
  showView(v: ViewName): void {
    el("stage").classList.toggle("hidden", v !== "drive");
    el("banner").classList.toggle("hidden", v !== "drive");
    el("settings").classList.toggle("hidden", v !== "settings");
    el("diagnostics").classList.toggle("hidden", v !== "diagnostics");
  }

  private wireChrome(): void {
    el("gear").addEventListener("click", () => this.cb.setView("settings"));
    el("settingsBack").addEventListener("click", () => this.cb.setView("drive"));
    el("diagBack").addEventListener("click", () => this.cb.setView("drive"));
    this.muteBtn.addEventListener("click", () => this.cb.toggleMute());

    // hidden diagnostics: long-press the title, or press "d"
    const startLp = () => { this.lpTimer = window.setTimeout(() => this.cb.setView("diagnostics"), 700); };
    const cancelLp = () => window.clearTimeout(this.lpTimer);
    this.titleEl.addEventListener("pointerdown", startLp);
    this.titleEl.addEventListener("pointerup", cancelLp);
    this.titleEl.addEventListener("pointerleave", cancelLp);
    window.addEventListener("keydown", (e) => {
      if (e.key === "d" || e.key === "D") this.cb.setView("diagnostics");
      if (e.key === "Escape") this.cb.setView("drive");
    });

    // first user gesture unlocks Web Audio (autoplay policy)
    const gesture = () => this.cb.userGesture();
    window.addEventListener("pointerdown", gesture, { once: true });
    window.addEventListener("keydown", gesture, { once: true });

    // volume + language controls
    const vol = el<HTMLInputElement>("vol");
    vol.value = String(this.state.audio.volume);
    vol.addEventListener("input", () => this.cb.setVolume(Number(vol.value)));
    el<HTMLSelectElement>("lang").addEventListener("change", (e) => {
      this.cb.setLang((e.target as HTMLSelectElement).value as Lang);
    });

    // theme: night / day / auto (S6 polish). Reflects the persisted choice on open.
    const theme = el<HTMLSelectElement>("theme");
    theme.value = getThemeMode();
    theme.addEventListener("change", () => this.cb.setTheme(theme.value as ThemeMode));
  }

  // --- settings panel: per-zone threshold sliders + enable toggle ---
  private buildSettings(): void {
    const host = el("zoneRows");
    host.innerHTML = "";
    for (const z of this.cfg.zones) {
      const row = document.createElement("div");
      row.className = "zoneRow";
      row.dataset.zone = z.id;

      const name = document.createElement("div");
      name.className = "zoneRowName";
      name.dataset.role = "name";
      name.textContent = zoneName(z.id);

      const enable = document.createElement("input");
      enable.type = "checkbox";
      enable.checked = z.enabled;
      enable.addEventListener("change", () => this.cb.setZoneEnabled(z.id, enable.checked));

      const caution = this.slider(z.caution_m, 0.3, 4.0);
      const danger = this.slider(z.danger_m, 0.2, 3.0);
      // danger_m is the inner threshold and must stay <= caution_m (fusion rejects an inverted
      // pair, 05 §5.2). Couple the sliders so the UI can't emit one: nudge danger down to meet
      // caution before publishing, and keep both value labels in step.
      const push = () => {
        const c = Number(caution.input.value);
        if (Number(danger.input.value) > c) danger.input.value = String(c);
        caution.sync();
        danger.sync();
        this.cb.setThreshold(z.id, c, Number(danger.input.value));
      };
      caution.input.addEventListener("input", push);
      danger.input.addEventListener("input", push);

      row.append(enable, name, this.labeled("caution", caution.wrap), this.labeled("danger", danger.wrap));
      host.appendChild(row);
    }
  }

  private slider(value: number, min: number, max: number) {
    const wrap = document.createElement("div");
    wrap.className = "sliderWrap";
    const input = document.createElement("input");
    input.type = "range";
    input.min = String(min);
    input.max = String(max);
    input.step = "0.1";
    input.value = String(value);
    const out = document.createElement("span");
    out.className = "sliderOut";
    const sync = () => { out.textContent = `${Number(input.value).toFixed(1)} m`; };
    sync();
    wrap.append(input, out);
    return { wrap, input, sync };
  }

  private labeled(key: string, child: HTMLElement): HTMLElement {
    const w = document.createElement("label");
    w.className = "field";
    const span = document.createElement("span");
    span.className = "fieldLabel";
    span.dataset.key = key;
    span.textContent = t(key);
    w.append(span, child);
    return w;
  }

  private rebuildSettingsLabels(): void {
    document.querySelectorAll<HTMLElement>("[data-role=name]").forEach((n) => {
      const row = n.closest<HTMLElement>(".zoneRow");
      if (row?.dataset.zone) n.textContent = zoneName(row.dataset.zone);
    });
    document.querySelectorAll<HTMLElement>(".fieldLabel").forEach((s) => {
      if (s.dataset.key) s.textContent = t(s.dataset.key);
    });
  }

  /** Re-localize everything after a language switch. */
  relocalize(): void { this.applyStaticText(); }

  // --- per-frame render of the dynamic chrome ---
  render(vm: RenderVM): void {
    this.renderPip(vm);
    this.renderHealth(vm);
    this.renderBanner(vm);
    this.renderMute(vm);
    this.overlay.classList.toggle("hidden", vm.phase !== "WARMING_UP");
    this.soundHint.classList.toggle("hidden", !vm.audioSuspended);
    if (this.state.view === "diagnostics") this.renderDiagnostics(vm.animMs);
  }

  private renderPip(vm: RenderVM): void {
    // Animated only while live → a frozen browser freezes the pip (the whole-Pi-freeze tell, ADR-0006)
    if (vm.live) {
      const p = 0.35 + 0.65 * (0.5 + 0.5 * Math.sin(vm.animMs / 320));
      this.pip.style.opacity = p.toFixed(2);
      this.pip.style.background = THEME.pipLive;
      this.pip.style.transform = `scale(${(0.85 + 0.25 * p).toFixed(2)})`;
    } else {
      this.pip.style.opacity = "1";
      this.pip.style.transform = "scale(1)";
      this.pip.style.background = vm.phase === "WARMING_UP" ? THEME.pipWarming : THEME.pipLost;
    }
  }

  private renderHealth(vm: RenderVM): void {
    let txt = "";
    if (vm.phase === "MONITORING") txt = `● ${t("live")}`;
    else if (vm.phase === "WARMING_UP") txt = "○ …";
    else txt = "○ —";
    this.health.textContent = txt;
    this.health.style.color = vm.phase === "MONITORING" ? THEME.pipLive
      : vm.phase === "WARMING_UP" ? THEME.pipWarming : THEME.pipLost;
  }

  private renderBanner(vm: RenderVM): void {
    const b = this.banner;
    if (vm.phase === "WARMING_UP") {
      // not monitoring yet → neutral, never a misleading "all clear" (NFR-12)
      b.style.background = "transparent";
      b.style.borderColor = "rgba(120,128,140,0.25)";
      b.style.color = THEME.textDim;
      b.innerHTML = `<span class="sub">${t("warming_sub")}</span>`;
      return;
    }
    if (vm.phase === "SIGNAL_LOST") {
      b.style.background = SEVERITY.UNKNOWN.fill;
      b.style.borderColor = THEME.pipLost;
      b.style.color = THEME.pipLost;
      b.innerHTML = `<strong>⚠ ${t("signal_lost")}</strong><span class="sub">${t("signal_lost_sub")}</span>`;
      return;
    }
    if (!vm.banner) {
      b.style.background = "transparent";
      b.style.borderColor = "rgba(120,128,140,0.25)";
      b.style.color = THEME.textDim;
      b.innerHTML = `<span class="sub">✓ ${t("all_clear")}</span>`;
      return;
    }
    const s = SEVERITY[vm.banner.severity];
    const cls = className(vm.banner.objectClass);
    const rng = vm.banner.rangeM != null ? `${vm.banner.rangeM.toFixed(1)} ${t("unit_m")}` : "";
    const detail = [cls, rng].filter(Boolean).join(", ");
    b.style.background = s.fill;
    b.style.borderColor = s.stroke;
    b.style.color = s.accent;
    b.innerHTML =
      `<strong>${s.glyph || "⚠"} ${zoneName(vm.banner.zoneId)}</strong>` +
      (detail ? `<span class="sub">${detail}</span>` : "");
  }

  private renderMute(vm: RenderVM): void {
    if (vm.muted) {
      this.muteBtn.textContent = `🔇 ${Math.ceil(vm.muteRemainingS)}s`;
      this.muteBtn.title = t("unmute");
    } else {
      this.muteBtn.textContent = "🔊";
      this.muteBtn.title = t("mute");
    }
  }

  private renderDiagnostics(nowMs: number): void {
    const rows: string[] = [];
    for (const z of this.cfg.zones) {
      const rec = this.state.zones.get(z.id);
      const st = rec?.state;
      const sev = st?.severity ?? "—";
      const age = rec ? Math.round(nowMs - rec.receiptMono) : "—";
      const rng = st?.nearest_range_m != null ? st.nearest_range_m.toFixed(2) : "—";
      const present = st?.nearest_range_m != null ? "✓" : "";
      const color = st ? SEVERITY[st.severity].accent : THEME.textDim;
      const flags = [st?.stale ? "stale" : "", st?.standby ? "standby" : ""].filter(Boolean).join(" ");
      rows.push(
        `<tr><td>${esc(zoneName(z.id))}</td>` +
        `<td style="color:${color}">${esc(sev)}${flags ? ` <em>${flags}</em>` : ""}</td>` +
        `<td>${rng}</td><td>${age}</td><td>${present}</td><td>${esc(st?.reason ?? "")}</td></tr>`,
      );
    }
    // raw per-sensor feed (lazy-subscribed)
    if (this.state.sensors.size) {
      rows.push(`<tr class="sep"><td colspan="6">${t("sensor")}</td></tr>`);
      for (const [id, rec] of this.state.sensors) {
        const r = rec.reading;
        const age = Math.round(nowMs - rec.receiptMono);
        const rng = r.range_m != null ? r.range_m.toFixed(2) : "—";
        rows.push(
          `<tr><td>${esc(id)}</td><td>${esc(r.modality ?? "")}</td><td>${rng}</td>` +
          `<td>${age}</td><td>${r.present ? "✓" : ""}</td><td>${esc(r.health ?? "")}</td></tr>`,
        );
      }
    } else {
      rows.push(`<tr><td colspan="6" class="muted">${t("no_sensors")}</td></tr>`);
    }
    this.diagBody.innerHTML = rows.join("");

    const recent = this.state.sensorMsgTimes.filter((tm) => nowMs - tm <= 1000).length;
    this.state.sensorMsgTimes = this.state.sensorMsgTimes.filter((tm) => nowMs - tm <= 2000);
    this.diagRate.textContent = `${recent} ${t("msg_per_s")}`;
  }
}
