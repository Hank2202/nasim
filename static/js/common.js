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
    this.muted = false;
    try { this.muted = localStorage.getItem('summit_muted') === '1'; } catch (e) { /* private window: sounds stay on */ }
  }

  setMuted(muted) {
    this.muted = !!muted;
    try { localStorage.setItem('summit_muted', muted ? '1' : '0'); } catch (e) { /* not remembered, that is all */ }
  }

  // Is there anything to play on? Also wakes the audio context up.
  _ready() {
    if (this.muted) return false;
    this._initContext();
    return !!this.ctx;
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
    if (!this._ready()) return;

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
    if (!this._ready()) return;

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

  // War horn and drums: a battle has been fought.
  playBattle() {
    if (!this._ready()) return;
    const now = this.ctx.currentTime;
    [0, 0.32, 0.64, 0.96].forEach((offset, i) => {            // drums
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(110 - i * 8, now + offset);
      osc.frequency.exponentialRampToValueAtTime(48, now + offset + 0.25);
      gain.gain.setValueAtTime(0.45, now + offset);
      gain.gain.exponentialRampToValueAtTime(0.001, now + offset + 0.3);
      osc.connect(gain); gain.connect(this.ctx.destination);
      osc.start(now + offset); osc.stop(now + offset + 0.32);
    });
    [196, 294].forEach((freq, i) => {                          // horn
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(freq, now + 1.1);
      gain.gain.setValueAtTime(0.0001, now + 1.1);
      gain.gain.exponentialRampToValueAtTime(0.16 / (i + 1), now + 1.3);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + 2.4);
      osc.connect(gain); gain.connect(this.ctx.destination);
      osc.start(now + 1.1); osc.stop(now + 2.5);
    });
  }

  playAlert() {
    if (!this._ready()) return;

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

  // A rising and falling wail: a disaster has struck.
  playSiren() {
    if (!this._ready()) return;
    const now = this.ctx.currentTime;
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();
    osc.type = 'sawtooth';
    osc.frequency.setValueAtTime(440, now);
    [0.45, 0.9, 1.35, 1.8].forEach((t, i) => osc.frequency.linearRampToValueAtTime(i % 2 ? 440 : 880, now + t));
    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.exponentialRampToValueAtTime(0.18, now + 0.1);
    gain.gain.setValueAtTime(0.18, now + 1.6);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 2.0);
    osc.connect(gain);
    gain.connect(this.ctx.destination);
    osc.start(now);
    osc.stop(now + 2.05);
  }

  // The sound for a cue sent by the server (meta.audio_cue.type).
  playCue(type) {
    const play = { gong: 'playGong', turn: 'playGong', chime: 'playChime', trade: 'playChime', decree: 'playChime',
                   alert: 'playAlert', siren: 'playSiren', battle: 'playBattle' }[type];
    if (play) this[play]();
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

// "just now", "3 min ago" or "2 h ago" for a moment given in seconds since 1970 (as the server sends it).
function timeAgo(epochSeconds) {
  const secs = Math.max(0, Date.now() / 1000 - epochSeconds);
  if (secs < 60) return 'just now';
  if (secs < 3600) return `${Math.floor(secs / 60)} min ago`;
  return `${Math.floor(secs / 3600)} h ago`;
}

// Where the working-session clock stands. Screens use this to say what is going on, not only how much time is left.
//   other         the game is not in a working session (a vote, the results...)
//   intermission  the short pause before a turn
//   ready         the clock is full and stopped: the session has not begun (Turn 1: the game has not begun)
//   running, paused, timeup
function clockStage(meta) {
  if (meta.phase !== 'working') return 'other';
  if (meta.intermission_end) return 'intermission';
  if (meta.is_timer_running) return 'running';
  if (meta.turn_timer_remaining === meta.turn_timer_total) return 'ready';
  return meta.turn_timer_remaining > 0 ? 'paused' : 'timeup';
}

const RESOURCE_ICONS = { grain: '🌾', cores: '⚙️', silk: '🧵', military: '⚔️' };
const RESOURCE_SHORT = { grain: 'Grain', cores: 'Cores', silk: 'Silk', military: 'Military', vitality: 'Vitality', standing: 'Standing', stability: 'Stability' };

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

// Screens poll once a second. Rebuilding a list that has not changed closes an open "Read the terms", shuts a
// dropdown and can swallow a tap that falls between press and release, so a list is only rebuilt when it changes.
function setHtml(el, html) {
  if (el && el._shownHtml !== html) {
    el.innerHTML = html;
    el._shownHtml = html;
  }
}


// -----------------------------------------------------------------------------
// Ask before doing something: a themed confirmation instead of the browser's plain dialog.
//   if (!(await confirmAction({ title, message, details: ['…'], confirmLabel, tone: 'danger' }))) return;
// Resolves true on Confirm and false on Cancel, Escape or a tap outside the card.
// -----------------------------------------------------------------------------
function confirmAction(opts) {
  opts = typeof opts === 'string' ? { message: opts } : (opts || {});
  return new Promise(resolve => {
    const previous = document.activeElement;
    const overlay = document.createElement('div');
    overlay.className = 'confirm-overlay';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    const items = (opts.details || []).map(d => `<li>${escapeHtml(d)}</li>`).join('');
    overlay.innerHTML = `<div class="confirm-card ${opts.tone === 'danger' ? 'danger' : ''}">
      <div class="confirm-title">${escapeHtml(opts.title || 'Are you sure?')}</div>
      ${opts.message ? `<p class="confirm-msg">${escapeHtml(opts.message)}</p>` : ''}
      ${items ? `<ul class="confirm-list">${items}</ul>` : ''}
      <div class="confirm-actions">
        <button type="button" class="btn btn-secondary confirm-no">${escapeHtml(opts.cancelLabel || 'Cancel')}</button>
        <button type="button" class="btn ${opts.tone === 'danger' ? 'btn-danger' : 'btn-primary'} confirm-yes">${escapeHtml(opts.confirmLabel || 'Confirm')}</button>
      </div></div>`;
    const onKey = e => { if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); close(false); } };
    const close = answer => {
      document.removeEventListener('keydown', onKey, true);
      overlay.remove();
      if (previous && previous.focus) { try { previous.focus(); } catch (e) { /* element is gone */ } }
      resolve(answer);
    };
    overlay.addEventListener('click', e => { if (e.target === overlay) close(false); });
    // A tap or key that opened the dialog must not also answer it (the same Enter key, or a double tap on a phone):
    // answers are ignored for the first moments after it appears.
    const openedAt = Date.now();
    const settled = () => Date.now() - openedAt > 350;
    overlay.querySelector('.confirm-no').addEventListener('click', () => { if (settled()) close(false); });
    overlay.querySelector('.confirm-yes').addEventListener('click', () => { if (settled()) close(true); });
    document.addEventListener('keydown', onKey, true);
    document.body.appendChild(overlay);
    setTimeout(() => { const yes = overlay.querySelector('.confirm-yes'); if (yes && overlay.isConnected) yes.focus(); }, 360);
  });
}

// -----------------------------------------------------------------------------
// A panel that slides up from the bottom: help texts and explanations, nothing that needs an answer.
//   const close = showSheet({ title, html });
// Closes with its button, Escape or a tap outside.
// -----------------------------------------------------------------------------
function showSheet({ title, html }) {
  const overlay = document.createElement('div');
  overlay.className = 'sheet-overlay';
  overlay.setAttribute('role', 'dialog');
  overlay.setAttribute('aria-modal', 'true');
  overlay.innerHTML = `<div class="sheet-card">
    <div class="sheet-head"><h2 class="sheet-title">${escapeHtml(title || '')}</h2>
      <button type="button" class="sheet-close" aria-label="Close">&times;</button></div>
    <div class="sheet-body">${html}</div></div>`;
  const onKey = e => { if (e.key === 'Escape') close(); };
  const close = () => { document.removeEventListener('keydown', onKey); overlay.remove(); };
  overlay.addEventListener('click', e => { if (e.target === overlay) close(); });
  overlay.querySelector('.sheet-close').addEventListener('click', close);
  document.addEventListener('keydown', onKey);
  document.body.appendChild(overlay);
  return close;
}

// -----------------------------------------------------------------------------
// Say so when the server cannot be reached, instead of showing a frozen screen.
// Pages call connectionWatch.ok() or .failed() after every poll.
// -----------------------------------------------------------------------------
const connectionWatch = {
  fails: 0,
  ok() {
    this.fails = 0;
    const bar = document.getElementById('connection-bar');
    if (bar) bar.remove();
  },
  failed() {
    this.fails += 1;
    if (this.fails < 3 || document.getElementById('connection-bar')) return;
    const bar = document.createElement('div');
    bar.id = 'connection-bar';
    bar.className = 'connection-bar';
    bar.setAttribute('role', 'status');
    bar.textContent = 'Not connected to the game. Trying again… Check the Wi-Fi if this stays.';
    document.body.appendChild(bar);
  },
};

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
window.setHtml = setHtml;
window.timeAgo = timeAgo;
window.clockStage = clockStage;
window.showSheet = showSheet;
window.connectionWatch = connectionWatch;
window.confirmAction = confirmAction;
window.showToast = showToast;
window.keepScreenAwake = keepScreenAwake;
