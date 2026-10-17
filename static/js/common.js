/**
 * The Summit of Realms - shared helpers for every page:
 * procedural sound effects, toasts, formatting and HTML escaping.
 * Loaded before the page-specific script (realm.js, projector.js or admin.js).
 */
'use strict';

// -----------------------------------------------------------------------------
// Web Audio API Procedural Sound Synthesizer (Zero External Audio Files)
// -----------------------------------------------------------------------------
class AudioSynthesizer {
  constructor() {
    this.ctx = null;
    this.unlocked = false;
  }

  _initContext() {
    if (!this.ctx) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (AudioCtx) {
        this.ctx = new AudioCtx();
      }
    }
    if (this.ctx && this.ctx.state === 'suspended') {
      this.ctx.resume();
    }
    this.unlocked = true;
  }

  playGong() {
    this._initContext();
    if (!this.ctx) return;

    const now = this.ctx.currentTime;
    const freqs = [220, 330, 440, 587, 880];
    
    freqs.forEach((freq, idx) => {
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      
      osc.type = idx % 2 === 0 ? 'sine' : 'triangle';
      osc.frequency.setValueAtTime(freq, now);
      
      const initialGain = 0.25 / (idx + 1);
      gain.gain.setValueAtTime(initialGain, now);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + 3.0);
      
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      
      osc.start(now);
      osc.stop(now + 3.0);
    });
  }

  playChime() {
    this._initContext();
    if (!this.ctx) return;

    const now = this.ctx.currentTime;
    const notes = [523.25, 659.25, 783.99];
    
    notes.forEach((freq, i) => {
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      const noteTime = now + (i * 0.1);
      
      osc.type = 'sine';
      osc.frequency.setValueAtTime(freq, noteTime);
      
      gain.gain.setValueAtTime(0.2, noteTime);
      gain.gain.exponentialRampToValueAtTime(0.0001, noteTime + 1.2);
      
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      
      osc.start(noteTime);
      osc.stop(noteTime + 1.2);
    });
  }

  playAlert() {
    this._initContext();
    if (!this.ctx) return;

    const now = this.ctx.currentTime;
    [0, 0.25].forEach((offset, idx) => {
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      const time = now + offset;
      
      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(idx === 0 ? 880 : 660, time);
      
      gain.gain.setValueAtTime(0.25, time);
      gain.gain.exponentialRampToValueAtTime(0.001, time + 0.22);
      
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      
      osc.start(time);
      osc.stop(time + 0.22);
    });
  }
}

const synth = new AudioSynthesizer();
document.addEventListener('click', () => synth._initContext(), { once: true });
document.addEventListener('touchstart', () => synth._initContext(), { once: true });

// -----------------------------------------------------------------------------
// Toast Notification Utility
// -----------------------------------------------------------------------------
function showToast(message, type = 'info') {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerText = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.25s ease';
    setTimeout(() => toast.remove(), 250);
  }, 4000);
}

function formatSeconds(secs) {
  if (secs === null || secs === undefined || secs < 0) secs = 0;
  const mins = Math.floor(secs / 60);
  const rem = Math.floor(secs % 60);
  return `${mins.toString().padStart(2, '0')}:${rem.toString().padStart(2, '0')}`;
}

const RESOURCE_ICONS = { grain: '🌾', cores: '⚙️', silk: '🧵', military: '⚔️' };
const RESOURCE_SHORT = { grain: 'Grain', cores: 'Cores', silk: 'Silk', military: 'Military', standing: 'Standing', stability: 'Stability' };

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}


// -----------------------------------------------------------------------------
// Keep the screen awake (projector, phones, facilitator laptop)
// Uses the Screen Wake Lock API. Browsers only allow it on https or localhost,
// so it works on the hosted site; on a plain-http LAN it quietly does nothing.
// -----------------------------------------------------------------------------
function keepScreenAwake() {
  if (!('wakeLock' in navigator)) return;
  let lock = null;
  const request = async () => {
    if (document.visibilityState !== 'visible' || lock) return;
    try {
      lock = await navigator.wakeLock.request('screen');
      lock.addEventListener('release', () => { lock = null; });
    } catch (err) { /* not allowed right now (e.g. battery saver); retried on the next tap or focus */ }
  };
  request();
  // Locks are dropped when the tab is hidden; take a new one when it comes back.
  document.addEventListener('visibilitychange', request);
  // Some browsers only grant the lock after a user gesture.
  document.addEventListener('click', request);
  document.addEventListener('touchend', request);
}

window.synth = synth;
window.showToast = showToast;
window.keepScreenAwake = keepScreenAwake;
