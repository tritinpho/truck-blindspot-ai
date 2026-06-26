// Web Audio alert engine (06 §6.3, 05 §5.5). No asset files — tones are synthesized.
//
//   CAUTION → slow intermittent beep (~1.5 Hz)
//   DANGER  → fast beep (~6 Hz, near-continuous)
//   new fault (zone → UNKNOWN, or SIGNAL LOST) → one-shot chime, rate-limited (≥10 s)
//
// Policy decisions (what to sound) live in select.ts; this module only PRODUCES sound. The
// single worst severity sounds at a time (the caller passes one target). Timed mute and
// park-standby resolve to SILENT upstream — they silence audio without ever touching visuals.

import type { AudioTarget } from "./select";

interface Pattern { periodMs: number; onMs: number; freq: number; }

const PATTERNS: Record<Exclude<AudioTarget, "SILENT">, Pattern> = {
  CAUTION: { periodMs: 660, onMs: 130, freq: 660 },
  DANGER: { periodMs: 150, onMs: 95, freq: 920 },
};

const CHIME_MIN_INTERVAL_MS = 10_000; // matches fusion fault_chime_min_interval_ms (05 §5.3)

export class AudioEngine {
  private ctx: AudioContext | null = null;
  private osc: OscillatorNode | null = null;
  private beepGain: GainNode | null = null;
  private masterGain: GainNode | null = null;

  private volume = 0.7;
  private current: AudioTarget = "SILENT";
  private cycleStart = 0;
  private lastChimeMs = -Infinity;

  /** Lazily build + resume the audio graph. Must be called from a user gesture (autoplay policy). */
  ensure(): void {
    if (!this.ctx) {
      const Ctor: typeof AudioContext | undefined =
        window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (!Ctor) return; // no Web Audio — engine degrades to silent, visuals unaffected
      this.ctx = new Ctor();
      this.masterGain = this.ctx.createGain();
      this.masterGain.gain.value = this.volume;
      this.masterGain.connect(this.ctx.destination);

      this.beepGain = this.ctx.createGain();
      this.beepGain.gain.value = 0;
      this.beepGain.connect(this.masterGain);

      this.osc = this.ctx.createOscillator();
      this.osc.type = "square";
      this.osc.frequency.value = PATTERNS.CAUTION.freq;
      this.osc.connect(this.beepGain);
      this.osc.start();
    }
    if (this.ctx.state === "suspended") void this.ctx.resume();
  }

  /** True when the context exists but is blocked by autoplay policy (show a "tap for sound" hint). */
  get suspended(): boolean {
    return this.ctx != null && this.ctx.state === "suspended";
  }

  setVolume(v: number): void {
    this.volume = Math.max(0, Math.min(1, v));
    if (this.masterGain && this.ctx) {
      this.masterGain.gain.setTargetAtTime(this.volume, this.ctx.currentTime, 0.01);
    }
  }

  /** Drive the beep pattern for the current target. Call every frame with performance.now(). */
  update(target: AudioTarget, nowMs: number): void {
    if (!this.ctx || !this.osc || !this.beepGain) return;

    if (target !== this.current) {
      this.current = target;
      this.cycleStart = nowMs;
      if (target !== "SILENT") this.osc.frequency.value = PATTERNS[target].freq;
    }

    if (target === "SILENT") {
      this.gate(false);
      return;
    }
    const p = PATTERNS[target];
    let elapsed = nowMs - this.cycleStart;
    if (elapsed >= p.periodMs) {
      this.cycleStart += Math.floor(elapsed / p.periodMs) * p.periodMs;
      elapsed = nowMs - this.cycleStart;
    }
    this.gate(elapsed < p.onMs);
  }

  /** One-shot two-tone fault chime, rate-limited so Wi-Fi jitter can't nag (05 §5.3). */
  chime(nowMs: number): void {
    if (!this.ctx || !this.masterGain) return;
    if (nowMs - this.lastChimeMs < CHIME_MIN_INTERVAL_MS) return;
    this.lastChimeMs = nowMs;

    const now = this.ctx.currentTime;
    const g = this.ctx.createGain();
    g.gain.value = 0;
    g.connect(this.masterGain);
    const o = this.ctx.createOscillator();
    o.type = "sine";
    o.connect(g);
    // two descending blips: 988 Hz then 740 Hz
    o.frequency.setValueAtTime(988, now);
    o.frequency.setValueAtTime(740, now + 0.12);
    g.gain.setTargetAtTime(0.5, now, 0.01);
    g.gain.setTargetAtTime(0.0, now + 0.1, 0.02);
    g.gain.setTargetAtTime(0.5, now + 0.12, 0.01);
    g.gain.setTargetAtTime(0.0, now + 0.22, 0.03);
    o.start(now);
    o.stop(now + 0.35);
  }

  private gate(on: boolean): void {
    if (!this.beepGain || !this.ctx) return;
    const peak = on ? this.volume * 0.6 : 0;
    this.beepGain.gain.setTargetAtTime(peak, this.ctx.currentTime, 0.005);
  }
}
