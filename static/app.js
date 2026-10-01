/**
 * The Summit of Realms - Master Client Engine & Audio Synthesizer
 * 100% Offline Vanilla JavaScript.
 * Supports:
 *   - News-Dominant Projector Layout with Hero Breaking News & Qualitative Intel
 *   - Fog of War (Qualitative Tiers: Abundant, Normal, Scant)
 *   - Delegation 4-Digit Passcode Authentication
 *   - Functional Facilitator Command Deck with Direct Time Editing & PIN Management
 *   - Structured Between-Round Plenary Sessions & 5-Minute Floor Debate
 */

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

const RESOURCE_FRIENDLY = {
  grain: 'Alchemical Grain',
  cores: 'Aether Cores',
  silk: 'Echo Silk'
};

// -----------------------------------------------------------------------------
// Participant Mobile Cockpit App (RealmApp)
// -----------------------------------------------------------------------------
class RealmApp {
  constructor(realmId) {
    this.realmId = realmId;
    this.lastAudioSeq = null;
    this.isPolling = false;
    window.realmApp = this;
  }

  start() {
    this.pollState();
    setInterval(() => this.pollState(), 1000);
    this.bindEvents();
    this.bindBottomNav();
  }

  switchView(viewId) {
    document.querySelectorAll('.bottom-nav-item').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.view === viewId);
    });
    document.querySelectorAll('.mobile-view').forEach(v => {
      v.classList.toggle('active', v.id === viewId);
    });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  bindBottomNav() {
    document.querySelectorAll('.bottom-nav-item').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const targetViewId = btn.dataset.view;
        if (targetViewId) this.switchView(targetViewId);
      });
    });
  }

  handleEndorsementModeChange(mode) {
    const group = document.getElementById('proposal-target-realm-group');
    if (group) {
      group.style.display = mode === 'targeted' ? 'block' : 'none';
    }
  }

  async handleDraftProposal(e) {
    e.preventDefault();
    const title = document.getElementById('proposal-title').value;
    const effectType = document.getElementById('proposal-type').value;
    const mode = document.getElementById('proposal-target-mode').value;
    const targetRealmSelect = document.getElementById('proposal-target-realm');
    const targetSeconderId = (mode === 'targeted' && targetRealmSelect) ? targetRealmSelect.value : null;
    const description = document.getElementById('proposal-desc').value;

    try {
      const resp = await fetch('/api/proposal/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          proposer_id: this.realmId,
          title,
          effect_type: effectType,
          description,
          target_seconder_id: targetSeconderId
        })
      });
      const res = await resp.json();
      if (res.success) {
        showToast('Resolution filed on floor', 'info');
        synth.playChime();
        document.getElementById('proposal-form').reset();
        this.handleEndorsementModeChange('open');
        this.pollState();
      } else {
        showToast(res.message, 'danger');
      }
    } catch (err) {
      showToast('Failed to file motion', 'danger');
    }
  }

  async pollState() {
    if (this.isPolling) return;
    this.isPolling = true;

    try {
      const resp = await fetch('/api/state');
      if (!resp.ok) throw new Error('State fetch failed');
      const state = await resp.json();
      this.renderState(state);
    } catch (err) {
      console.warn('Polling error:', err);
    } finally {
      this.isPolling = false;
    }
  }

  renderState(state) {
    const { meta, realms, trades, proposals, news_feed } = state;
    const realm = realms.find(r => r.id === this.realmId);

    // Audio cues
    if (meta.audio_cue && meta.audio_cue.seq !== undefined) {
      if (this.lastAudioSeq !== null && meta.audio_cue.seq > this.lastAudioSeq) {
        if (meta.audio_cue.type === 'gong' || meta.audio_cue.type === 'turn') synth.playGong();
        else if (meta.audio_cue.type === 'chime' || meta.audio_cue.type === 'trade') synth.playChime();
        else if (meta.audio_cue.type === 'alert') synth.playAlert();
        if (meta.audio_cue.message) showToast(meta.audio_cue.message, 'info');
      }
      this.lastAudioSeq = meta.audio_cue.seq;
    }

    // Header updates
    const turnElem = document.getElementById('turn-display');
    if (turnElem) turnElem.innerText = `TURN ${meta.current_turn}`;
    const timerElem = document.getElementById('timer-display');
    if (timerElem) timerElem.innerText = formatSeconds(meta.turn_timer_remaining);

    // Mini Breaking News Banner
    if (news_feed && news_feed.length > 0) {
      const latestNews = news_feed[0];
      const headlineEl = document.getElementById('news-headline');
      const bodyEl = document.getElementById('news-body');
      if (headlineEl && bodyEl) {
        headlineEl.innerText = latestNews.headline;
        bodyEl.innerText = latestNews.detail;
      }
    }

    // Full News Stream (Tab 2)
    this.renderNewsFeed(news_feed);

    if (!realm) return;

    // Telemetry - Exact values for own country
    this._setVal('grain-val', realm.alchemical_grain);
    this._setVal('cores-val', realm.aether_cores);
    this._setVal('silk-val', realm.echo_silk);
    this._setVal('military-val', realm.military_power || 50);

    // Metrics
    this._setMetric('vitality', realm.public_vitality);
    this._setMetric('standing', realm.diplomatic_standing);
    this._setMetric('stability', realm.civil_stability);

    // Assembly votes
    const votesBadge = document.getElementById('votes-badge');
    if (votesBadge) {
      let voteText = `${realm.assembly_votes} ASSEMBLY VOTE${realm.assembly_votes > 1 ? 'S' : ''}`;
      if (realm.is_plutocrat) voteText += ` (+1 PLUTOCRAT)`;
      votesBadge.innerText = voteText;
    }

    // Flags
    this.renderFlags(realm);

    // Trades
    this.renderTrades(trades, realm);

    // Motions Tab
    this.renderProposals(proposals, realm);

    // Plenary Session Callout on Mobile
    this.renderPlenarySessionCallout(meta, proposals, realm);

    // Summit Concluded Personal Evaluation Callout
    this.renderConcludedDebrief(state, realm);

    // Lore Encyclopedia & Knowledge Bounties
    this.rawLoreEncyclopedia = state.lore_encyclopedia || [];
    this.currentRealm = realm;
    this.renderLoreArchive(this.rawLoreEncyclopedia, realm);
  }

  _setVal(id, val) {
    const el = document.getElementById(id);
    if (el) el.innerText = val;
  }

  _setMetric(name, val) {
    const valEl = document.getElementById(`${name}-val`);
    const barEl = document.getElementById(`${name}-bar`);
    if (valEl) valEl.innerText = `${val}/100`;
    if (barEl) barEl.style.width = `${val}%`;
  }

  filterNews(category, btn) {
    document.querySelectorAll('.news-filter-btn').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
    this.activeNewsCategory = category;
    this.renderNewsFeed(this.rawNewsFeed || []);
  }

  renderNewsFeed(news_feed) {
    this.rawNewsFeed = news_feed;
    const newsContainer = document.getElementById('mobile-news-feed');
    if (!newsContainer || !news_feed) return;

    const filtered = (this.activeNewsCategory && this.activeNewsCategory !== 'all') ?
      news_feed.filter(n => n.type === this.activeNewsCategory) :
      news_feed;

    if (filtered.length === 0) {
      newsContainer.innerHTML = '<p class="text-muted" style="font-size:0.8rem; font-family:var(--font-mono); padding:10px 0;">No dispatches in this category.</p>';
      return;
    }

    newsContainer.innerHTML = filtered.map(n => `
      <div style="background: var(--bg-surface-sunken); border: 1px solid var(--border-subtle); box-shadow: var(--shadow-sunken); border-radius: 4px; padding: 10px 12px;">
        <div style="display:flex; justify-content:space-between; font-size: 0.72rem; font-family: var(--font-mono); color: var(--text-muted);">
          <strong style="color: var(--text-primary);">[${n.type.toUpperCase()}] ${n.headline}</strong>
          <span>${n.time_str}</span>
        </div>
        <p style="color: var(--text-secondary); font-size: 0.8rem; margin-top: 4px; line-height: 1.4;">${n.detail}</p>
      </div>
    `).join('');
  }

  renderConcludedDebrief(state, realm) {
    const container = document.getElementById('mobile-concluded-callout');
    if (!container) return;

    if (state.meta.phase !== 'summit_concluded' || !state.summit_outcome) {
      container.style.display = 'none';
      return;
    }

    const outcome = state.summit_outcome;
    const myEval = (outcome.realm_evaluations || []).find(e => e.realm_id === this.realmId);
    if (!myEval) return;

    container.style.display = 'block';
    container.innerHTML = `
      <div class="card" style="border: 2px solid var(--border-white); padding: 16px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
          <span class="badge" style="background:#fff; color:#000; font-weight:800;">SUMMIT CONCLUDED</span>
          <span class="badge" style="font-size:0.75rem;">SCORE: ${myEval.score} PTS</span>
        </div>

        <h2 style="font-size:1.25rem; font-weight:900; margin-bottom:4px; text-transform:uppercase;">
          ${outcome.continental_verdict}
        </h2>
        <p style="font-size:0.82rem; color:var(--text-secondary); line-height:1.4; margin-bottom:12px;">
          ${outcome.continental_desc}
        </p>

        <div style="background:var(--bg-surface-sunken); border:1px solid var(--border-subtle); padding:12px; border-radius:var(--radius-sm); margin-bottom:10px;">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <strong style="font-size:0.88rem;">${myEval.directive_title}</strong>
            ${myEval.directive_achieved ? 
              '<span class="badge" style="background:#10b981; color:#fff; font-weight:800;">[DIRECTIVE ACHIEVED (+100 PTS)]</span>' : 
              '<span class="badge" style="background:#ef4444; color:#fff; font-weight:800;">[DIRECTIVE FAILED]</span>'}
          </div>
          <div style="font-size:0.75rem; font-family:var(--font-mono); color:var(--text-muted); margin-top:4px;">
            ${myEval.directive_explanation}
          </div>
        </div>

        <p style="font-size:0.82rem; color:var(--text-primary); line-height:1.4; font-style:italic;">
          "${myEval.epilogue}"
        </p>
      </div>
    `;
  }

  filterLore(category, btn) {
    document.querySelectorAll('.lore-filter-btn').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
    this.activeLoreCategory = category;
    this.renderLoreArchive(this.rawLoreEncyclopedia || [], this.currentRealm);
  }

  renderLoreArchive(encyclopedia, realm) {
    const container = document.getElementById('lore-encyclopedia-container');
    if (!container || !encyclopedia) return;

    const filtered = (this.activeLoreCategory && this.activeLoreCategory !== 'all') ?
      encyclopedia.filter(e => e.category === this.activeLoreCategory) :
      encyclopedia;

    if (filtered.length === 0) {
      container.innerHTML = '<p class="text-muted" style="font-size:0.8rem; font-family:var(--font-mono); padding:10px 0;">No dossiers found in this category.</p>';
      return;
    }

    const claimed = (realm && realm.claimed_lore) ? realm.claimed_lore : [];
    const failed = (realm && realm.failed_lore) ? realm.failed_lore : [];

    container.innerHTML = filtered.map(t => {
      const isClaimed = claimed.includes(t.id);
      const isFailed = failed.includes(t.id);

      let quizHtml = '';
      if (isClaimed) {
        quizHtml = `
          <div style="background:var(--bg-surface); border:1px solid #10b981; padding:10px 12px; border-radius:var(--radius-xs); margin-top:10px;">
            <span class="badge" style="background:#10b981; color:#fff; font-weight:800; font-size:0.75rem;">[✓ INTEL VERIFIED: ${t.quiz.reward_label}]</span>
            <p style="font-size:0.76rem; color:var(--text-secondary); margin-top:6px; line-height:1.35;">
              <strong style="color:var(--text-primary);">Historical Fact:</strong> ${t.quiz.explanation}
            </p>
          </div>
        `;
      } else if (isFailed) {
        quizHtml = `
          <div style="background:var(--bg-surface); border:1px solid #ef4444; padding:10px 12px; border-radius:var(--radius-xs); margin-top:10px;">
            <span class="badge" style="background:#ef4444; color:#fff; font-weight:800; font-size:0.75rem;">[❌ ASSESSMENT FAILED: ACCESS LOCKED (-5 STANDING)]</span>
            <p style="font-size:0.76rem; color:var(--text-secondary); margin-top:6px; line-height:1.35;">
              A flawed intelligence report was submitted on this subject. Access to this knowledge bounty is permanently suspended.
            </p>
          </div>
        `;
      } else {
        quizHtml = `
          <div style="background:var(--bg-surface); border:1px solid var(--border-white); padding:12px; border-radius:var(--radius-xs); margin-top:10px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
              <span class="badge" style="background:#fff; color:#000; font-weight:800; font-size:0.72rem;">SOVEREIGN INTELLIGENCE INQUIRY</span>
              <span class="badge" style="font-size:0.72rem;">BOUNTY: ${t.quiz.reward_label}</span>
            </div>
            <p style="font-size:0.82rem; font-weight:700; color:var(--text-primary); margin-bottom:10px; line-height:1.35;">
              ${t.quiz.question}
            </p>
            <div style="display:flex; flex-direction:column; gap:6px;">
              ${t.quiz.options.map((opt, idx) => `
                <button type="button" class="btn btn-secondary btn-sm btn-block" style="text-align:left; font-size:0.78rem; padding:8px 10px; font-weight:600;" onclick="realmApp.submitLoreQuiz('${t.id}', ${idx}, this)">
                  ${String.fromCharCode(65 + idx)}. ${opt}
                </button>
              `).join('')}
            </div>
            <div style="font-size:0.7rem; color:var(--text-muted); font-family:var(--font-mono); margin-top:8px;">
              ⚠️ Flawed report incurs a -5 Diplomatic Standing penalty and locks this dossier.
            </div>
          </div>
        `;
      }

      return `
        <div class="card" style="padding:14px 16px;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
            <span class="badge" style="font-size:0.7rem; color:var(--text-muted);">${(t.category_label || t.category).toUpperCase()}</span>
            ${isClaimed ? '<span class="badge" style="color:#10b981; border-color:#10b981;">CLAIMED</span>' : isFailed ? '<span class="badge" style="color:#ef4444; border-color:#ef4444;">LOCKED</span>' : '<span class="badge">[READY]</span>'}
          </div>
          <h3 style="font-size:0.95rem; font-weight:900; margin-bottom:6px; color:var(--text-primary); text-transform:uppercase;">
            ${t.title}
          </h3>
          <p style="font-size:0.82rem; color:var(--text-secondary); line-height:1.45;">
            ${t.snippet}
          </p>
          ${quizHtml}
        </div>
      `;
    }).join('');
  }

  async submitLoreQuiz(topicId, answerIndex, btnEl) {
    if (btnEl) {
      btnEl.disabled = true;
      btnEl.innerText += ' (Verifying...)';
    }

    try {
      const resp = await fetch('/api/lore/quiz', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          realm_id: this.realmId,
          topic_id: topicId,
          answer_index: answerIndex
        })
      });
      const res = await resp.json();
      if (res.success) {
        showToast(res.message, 'info');
        synth.playChime();
      } else {
        showToast(res.message, 'danger');
        synth.playAlert();
      }
      this.pollState();
    } catch(err) {
      showToast('Connection failed during intelligence dispatch', 'danger');
    }
  }

  renderFlags(realm) {
    const container = document.getElementById('status-tags-container');
    if (!container) return;

    let html = '';
    if (realm.is_starving) html += `<span class="badge badge-danger">[STARVING]</span>`;
    if (realm.complacency_warning) html += `<span class="badge">[COMPLACENCY RISK]</span>`;
    if (realm.is_plutocrat) html += `<span class="badge">[PLUTOCRAT: +1 VOTE]</span>`;
    if (realm.tech_efficiency_unlocked) html += `<span class="badge">[EFFICIENCY: -25% GRAIN]</span>`;
    if (realm.is_quarantined) html += `<span class="badge badge-danger">[QUARANTINED]</span>`;
    if (realm.is_striking) html += `<span class="badge badge-danger">[STRIKE ACTIVE]</span>`;

    container.innerHTML = html;
  }

  renderTrades(trades, realm) {
    const incomingContainer = document.getElementById('incoming-trades-list');
    const outgoingContainer = document.getElementById('outgoing-trades-list');

    const incoming = trades.filter(t => t.receiver_id === this.realmId && t.status === 'pending');
    const outgoing = trades.filter(t => t.sender_id === this.realmId && t.status === 'pending');

    const badgeEl = document.getElementById('nav-trade-badge');
    if (badgeEl) {
      if (incoming.length > 0) {
        badgeEl.innerText = incoming.length;
        badgeEl.style.display = 'inline-block';
      } else {
        badgeEl.style.display = 'none';
      }
    }

    if (incomingContainer) {
      if (incoming.length === 0) {
        incomingContainer.innerHTML = '<p class="text-muted" style="font-size:0.8rem; font-family:var(--font-mono);">No pending incoming proposals.</p>';
      } else {
        incomingContainer.innerHTML = incoming.map(t => {
          const offName = RESOURCE_FRIENDLY[t.offer_resource] || t.offer_resource;
          const reqName = RESOURCE_FRIENDLY[t.request_resource] || t.request_resource;
          return `
            <div class="trade-card">
              <div class="trade-header">
                <span>FROM: <strong>${t.sender_name}</strong></span>
                <span>${t.time_str}</span>
              </div>
              <div class="trade-details">
                <span>Offers: ${t.offer_amount} ${offName}</span>
                <span style="color:var(--text-muted);">for</span>
                <span>Demands: ${t.request_amount} ${reqName}</span>
              </div>
              ${t.note ? `<div style="font-size:0.75rem; font-style:italic; color:var(--text-secondary); margin-top:4px; margin-bottom:8px; padding:6px 10px; background:var(--bg-surface); border-radius:3px; border-left: 2px solid var(--border-white);">"${t.note}"</div>` : ''}
              <div class="trade-actions">
                <button class="btn btn-primary btn-sm btn-block" onclick="realmApp.respondTrade('${t.id}', 'accept')">Accept Treaty</button>
                <button class="btn btn-secondary btn-sm btn-block" onclick="realmApp.respondTrade('${t.id}', 'decline')">Decline</button>
              </div>
            </div>
          `;
        }).join('');
      }
    }

    if (outgoingContainer) {
      if (outgoing.length === 0) {
        outgoingContainer.innerHTML = '<p class="text-muted" style="font-size:0.8rem; font-family:var(--font-mono);">No active outgoing proposals.</p>';
      } else {
        outgoingContainer.innerHTML = outgoing.map(t => {
          const offName = RESOURCE_FRIENDLY[t.offer_resource] || t.offer_resource;
          const reqName = RESOURCE_FRIENDLY[t.request_resource] || t.request_resource;
          return `
            <div class="trade-card">
              <div class="trade-header">
                <span>TO: <strong>${t.receiver_name}</strong></span>
                <span>PENDING</span>
              </div>
              <div class="trade-details">
                <span>Offering ${t.offer_amount} ${offName} for ${t.request_amount} ${reqName}</span>
              </div>
              ${t.note ? `<div style="font-size:0.75rem; font-style:italic; color:var(--text-muted); margin-top:4px; margin-bottom:8px;">"${t.note}"</div>` : ''}
              <button class="btn btn-secondary btn-sm" onclick="realmApp.respondTrade('${t.id}', 'cancel')">Cancel Offer</button>
            </div>
          `;
        }).join('');
      }
    }
  }

  renderProposals(proposals, realm) {
    const motionsBadge = document.getElementById('nav-motions-badge');
    if (motionsBadge) {
      const pendingEndorsement = proposals.filter(p => {
        const supportList = p.support_list || [];
        const hasSupported = supportList.includes(this.realmId);
        const isTargetedToMe = p.target_seconder_id === this.realmId;
        return !hasSupported && (!p.target_seconder_id || isTargetedToMe);
      });
      if (pendingEndorsement.length > 0) {
        motionsBadge.innerText = pendingEndorsement.length;
        motionsBadge.style.display = 'inline-block';
      } else {
        motionsBadge.style.display = 'none';
      }
    }

    const container = document.getElementById('pending-motions-list');
    if (!container) return;

    if (proposals.length === 0) {
      container.innerHTML = '<p class="text-muted" style="font-size:0.8rem; font-family:var(--font-mono);">No motions currently on the floor.</p>';
      return;
    }

    container.innerHTML = proposals.map(p => {
      const supportList = p.support_list || [];
      const hasSupported = supportList.includes(this.realmId);
      const isTargetedToMe = p.target_seconder_id === this.realmId;
      const isQualified = supportList.length >= 2 || p.is_qualified;

      let targetBadge = '';
      if (p.target_seconder_id) {
        if (isTargetedToMe) {
          targetBadge = '<span class="badge" style="background:#ffffff; color:#000000; margin-bottom:6px;">[DIRECT ENVOY: YOUR ENDORSEMENT REQUESTED]</span>';
        } else {
          targetBadge = `<span class="badge" style="margin-bottom:6px;">[DIRECT ENVOY TO: ${p.target_seconder_name}]</span>`;
        }
      }

      let qualBadge = isQualified ?
        '<span class="badge" style="border-color:#ffffff; color:#ffffff;">[QUALIFIED FOR PLENARY BALLOT]</span>' :
        `<span class="badge" style="color:var(--text-muted);">[AWAITING SUPPORT: ${supportList.length}/2]</span>`;

      return `
        <div class="motion-card">
          <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:8px;">
            <div class="motion-title">${p.title}</div>
            ${qualBadge}
          </div>
          ${targetBadge ? `<div>${targetBadge}</div>` : ''}
          <div class="motion-sponsor">SPONSOR: ${p.proposer_name} • ${p.effect_type.toUpperCase()}</div>
          <div class="motion-desc">${p.description}</div>
          
          <div style="font-size:0.75rem; font-family:var(--font-mono); color:var(--text-secondary); margin-bottom:8px;">
            Endorsers (${supportList.length}): ${(p.supporters || []).map(s => s.name).join(', ')}
          </div>

          ${hasSupported ? 
            `<span class="badge">[YOUR ENDORSEMENT LOCKED]</span>` :
            (!p.target_seconder_id || isTargetedToMe) ?
              `<button class="btn btn-primary btn-block btn-sm" onclick="realmApp.supportProposal('${p.id}')">
                ENDORSE RESOLUTION (+1 CO-SPONSOR)
              </button>` :
              `<span class="badge" style="color:var(--text-muted);">[TARGETED TO ANOTHER SOVEREIGN]</span>`
          }
        </div>
      `;
    }).join('');
  }

  renderPlenarySessionCallout(meta, proposals, realm) {
    const callout = document.getElementById('plenary-session-callout');
    if (!callout) return;

    const phase = meta.phase;
    if (phase === 'working') {
      callout.style.display = 'none';
      return;
    }

    callout.style.display = 'block';

    const titleEl = document.getElementById('plenary-callout-title');
    const descEl = document.getElementById('plenary-callout-desc');
    const timerEl = document.getElementById('plenary-timer-display');
    const actionsContainer = document.getElementById('plenary-voting-actions-container');

    if (phase === 'plenary_quick') {
      titleEl.innerText = `BETWEEN-ROUNDS PLENARY: QUICK VOTE`;
      descEl.innerText = `Cast your sovereign weighted ballots on the qualified resolutions.`;
      timerEl.innerText = `VOTING ACTIVE`;

      const docket = meta.plenary_docket || [];
      const docketProps = proposals.filter(p => docket.includes(p.id));

      if (docketProps.length === 0) {
        actionsContainer.innerHTML = '<p class="text-muted" style="font-size:0.8rem; font-family:var(--font-mono);">No resolutions qualified for this plenary.</p>';
      } else {
        actionsContainer.innerHTML = docketProps.map(p => {
          const votes = p.votes || {};
          const myVote = votes[this.realmId];
          return `
            <div style="background:var(--bg-surface-sunken); border:1px solid var(--border-subtle); border-radius:4px; padding:10px; margin-bottom:8px;">
              <strong style="color:#fff; font-size:0.9rem;">${p.title}</strong>
              <p style="font-size:0.75rem; color:var(--text-secondary); margin:2px 0 8px 0;">${p.description}</p>
              
              ${myVote ? `
                <div class="badge" style="border-color:#fff; color:#fff;">BALLOT CAST: ${myVote.choice.toUpperCase()} (${myVote.weight} VOTES)</div>
              ` : `
                <div style="display:flex; gap:6px;">
                  <button class="btn btn-sm btn-primary" onclick="realmApp.castPlenaryVote('${p.id}', 'support')">SUPPORT (+${realm.assembly_votes})</button>
                  <button class="btn btn-sm btn-danger" onclick="realmApp.castPlenaryVote('${p.id}', 'oppose')">OPPOSE (+${realm.assembly_votes})</button>
                  <button class="btn btn-sm btn-secondary" onclick="realmApp.castPlenaryVote('${p.id}', 'abstain')">ABSTAIN</button>
                </div>
              `}
            </div>
          `;
        }).join('');
      }
    } else if (phase === 'grand_plenary_discussion') {
      const docket = meta.plenary_docket || [];
      const idx = meta.current_motion_index || 0;
      const activeProp = proposals.find(p => p.id === docket[idx]);

      titleEl.innerText = `GRAND PLENARY: MOTION ${idx + 1} OF ${docket.length}`;
      descEl.innerText = `5 minutes allocated for floor discussion before voting opens.`;
      timerEl.innerText = `DEBATE: ${formatSeconds(meta.discussion_timer_remaining)}`;

      if (activeProp) {
        actionsContainer.innerHTML = `
          <div style="background:var(--bg-surface-sunken); border:1px solid var(--border-subtle); border-radius:4px; padding:12px;">
            <strong style="color:#fff; font-size:1rem;">${activeProp.title}</strong>
            <div style="font-size:0.72rem; font-family:var(--font-mono); color:var(--text-muted); margin:4px 0;">SPONSOR: ${activeProp.proposer_name}</div>
            <p style="font-size:0.8rem; color:var(--text-secondary); line-height:1.4;">${activeProp.description}</p>
            <div style="margin-top:10px; font-size:0.78rem; font-family:var(--font-mono); color:#ffffff;">
              [FLOOR OPEN FOR VERBAL DELIBERATION]
            </div>
          </div>
        `;
      }
    } else if (phase === 'grand_plenary_voting') {
      const docket = meta.plenary_docket || [];
      const idx = meta.current_motion_index || 0;
      const activeProp = proposals.find(p => p.id === docket[idx]);

      titleEl.innerText = `GRAND PLENARY: VOTE ACTIVE ON MOTION ${idx + 1}`;
      descEl.innerText = `Debate concluded. Cast your sovereign weighted ballots.`;
      timerEl.innerText = `VOTE IN PROGRESS`;

      if (activeProp) {
        const votes = activeProp.votes || {};
        const myVote = votes[this.realmId];
        actionsContainer.innerHTML = `
          <div style="background:var(--bg-surface-sunken); border:1px solid var(--border-subtle); border-radius:4px; padding:12px;">
            <strong style="color:#fff; font-size:1rem;">${activeProp.title}</strong>
            <p style="font-size:0.8rem; color:var(--text-secondary); margin:4px 0 10px 0;">${activeProp.description}</p>
            
            ${myVote ? `
              <div class="badge" style="border-color:#fff; color:#fff;">BALLOT LOCKED: ${myVote.choice.toUpperCase()} (${myVote.weight} VOTES)</div>
            ` : `
              <div style="display:flex; gap:8px;">
                <button class="btn btn-primary btn-block" onclick="realmApp.castPlenaryVote('${activeProp.id}', 'support')">SUPPORT (+${realm.assembly_votes})</button>
                <button class="btn btn-danger btn-block" onclick="realmApp.castPlenaryVote('${activeProp.id}', 'oppose')">OPPOSE (+${realm.assembly_votes})</button>
                <button class="btn btn-secondary btn-block" onclick="realmApp.castPlenaryVote('${activeProp.id}', 'abstain')">ABSTAIN</button>
              </div>
            `}
          </div>
        `;
      }
    } else if (phase === 'turn_summary') {
      titleEl.innerText = `PLENARY CONCLUDED`;
      descEl.innerText = `All resolutions decided. Facilitator will process end of turn cycles.`;
      timerEl.innerText = `ROUND END`;
      actionsContainer.innerHTML = '';
    }
  }

  bindEvents() {
    const toggleAgendaBtn = document.getElementById('toggle-agenda-btn');
    const agendaContent = document.getElementById('agenda-content');
    if (toggleAgendaBtn && agendaContent) {
      toggleAgendaBtn.addEventListener('click', () => {
        agendaContent.classList.toggle('open');
        const isOpen = agendaContent.classList.contains('open');
        toggleAgendaBtn.querySelector('.toggle-indicator').innerText = isOpen ? '▲' : '▼';
      });
    }

    const tradeForm = document.getElementById('trade-form');
    if (tradeForm) {
      tradeForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const receiverId = document.getElementById('trade-receiver').value;
        const offerRes = document.getElementById('trade-offer-res').value;
        const offerAmt = parseInt(document.getElementById('trade-offer-amt').value, 10);
        const reqRes = document.getElementById('trade-req-res').value;
        const reqAmt = parseInt(document.getElementById('trade-req-amt').value, 10);
        const noteEl = document.getElementById('trade-note');
        const note = noteEl ? noteEl.value : '';

        try {
          const resp = await fetch('/api/trade/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              sender_id: this.realmId,
              receiver_id: receiverId,
              offer_resource: offerRes,
              offer_amount: offerAmt,
              request_resource: reqRes,
              request_amount: reqAmt,
              note: note
            })
          });
          const res = await resp.json();
          if (res.success) {
            showToast('Treaty proposal transmitted', 'info');
            synth.playChime();
            tradeForm.reset();
            this.pollState();
          } else {
            showToast(res.message, 'danger');
          }
        } catch (err) {
          showToast('Failed to connect to server', 'danger');
        }
      });
    }
  }

  adjustTradeInput(inputId, delta) {
    const el = document.getElementById(inputId);
    if (!el) return;
    let val = parseInt(el.value, 10) || 0;
    val = Math.max(1, Math.min(100, val + delta));
    el.value = val;
    this.updateTradePreview();
  }

  updateTradePreview() {
    const offerRes = document.getElementById('trade-offer-res');
    const offerAmt = document.getElementById('trade-offer-amt');
    const reqRes = document.getElementById('trade-req-res');
    const reqAmt = document.getElementById('trade-req-amt');
    const previewEl = document.getElementById('trade-preview-text');
    if (offerRes && offerAmt && reqRes && reqAmt && previewEl) {
      const resLabels = { grain: 'GRAIN', cores: 'CORES', silk: 'SILK', military: 'MILITARY' };
      const offLabel = resLabels[offerRes.value] || offerRes.value.toUpperCase();
      const reqLabel = resLabels[reqRes.value] || reqRes.value.toUpperCase();
      previewEl.innerText = `${offerAmt.value} ${offLabel} ⇄ ${reqAmt.value} ${reqLabel}`;
    }
  }

  async respondTrade(tradeId, action) {
    try {
      const resp = await fetch(`/api/trade/${tradeId}/respond`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, realm_id: this.realmId })
      });
      const res = await resp.json();
      if (res.success) {
        showToast(res.message, 'info');
        if (action === 'accept') synth.playChime();
        this.pollState();
      } else {
        showToast(res.message, 'danger');
      }
    } catch (err) {
      showToast('Action failed', 'danger');
    }
  }

  async supportProposal(propId) {
    try {
      const resp = await fetch(`/api/proposal/${propId}/support`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ supporter_id: this.realmId })
      });
      const res = await resp.json();
      if (res.success) {
        showToast(res.message, 'info');
        synth.playChime();
        this.pollState();
      } else {
        showToast(res.message, 'danger');
      }
    } catch (err) {
      showToast('Endorsement failed', 'danger');
    }
  }

  async castPlenaryVote(propId, choice) {
    try {
      const resp = await fetch('/api/plenary/vote', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ realm_id: this.realmId, proposal_id: propId, choice })
      });
      const res = await resp.json();
      if (res.success) {
        showToast(res.message, 'info');
        this.pollState();
      } else {
        showToast(res.message, 'danger');
      }
    } catch (err) {
      showToast('Failed to cast vote', 'danger');
    }
  }

  async executeDomesticAction(actionType) {
    try {
      const resp = await fetch('/api/realm/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ realm_id: this.realmId, action: actionType })
      });
      const res = await resp.json();
      if (res.success) {
        showToast(res.message, 'info');
        synth.playChime();
        this.pollState();
      } else {
        showToast(res.message, 'danger');
        synth.playAlert();
      }
    } catch (err) {
      showToast('Failed to enact policy', 'danger');
    }
  }
}

// -----------------------------------------------------------------------------
// Projector Overview Screen Logic (ProjectorApp)
// -----------------------------------------------------------------------------
class ProjectorApp {
  constructor() {
    this.isPolling = false;
    this.lastAudioSeq = null;
  }

  start() {
    if (typeof window !== 'undefined' && window.World3DMap && document.getElementById('world-3d-canvas')) {
      this.world3d = new window.World3DMap('world-3d-canvas');
    }
    this.pollState();
    setInterval(() => this.pollState(), 1000);
  }

  async pollState() {
    if (this.isPolling) return;
    this.isPolling = true;

    try {
      const resp = await fetch('/api/state');
      if (!resp.ok) throw new Error('State fetch failed');
      const state = await resp.json();
      this.renderState(state);
    } catch (err) {
      console.warn('Projector polling error:', err);
    } finally {
      this.isPolling = false;
    }
  }

  renderState(state) {
    const { meta, realms, proposals, news_feed } = state;

    // Update 3D World Map
    if (this.world3d) {
      this.world3d.updateState(state);
    }

    // Header
    const turnEl = document.getElementById('proj-turn');
    if (turnEl) {
      let phaseLabel = 'WORKING SESSION';
      if (meta.phase === 'plenary_quick') phaseLabel = 'BETWEEN-ROUNDS PLENARY';
      else if (meta.phase === 'grand_plenary_discussion') phaseLabel = 'GRAND PLENARY: DEBATE';
      else if (meta.phase === 'grand_plenary_voting') phaseLabel = 'GRAND PLENARY: VOTE';
      else if (meta.phase === 'turn_summary') phaseLabel = 'PLENARY CONCLUDED';
      turnEl.innerText = `TURN ${meta.current_turn} • ${phaseLabel}`;
    }

    const timerEl = document.getElementById('proj-timer');
    if (timerEl) {
      timerEl.innerText = formatSeconds(meta.turn_timer_remaining);
    }

    // Audio cues
    if (meta.audio_cue && meta.audio_cue.seq !== undefined) {
      if (this.lastAudioSeq !== null && meta.audio_cue.seq > this.lastAudioSeq) {
        if (meta.audio_cue.type === 'gong' || meta.audio_cue.type === 'turn') synth.playGong();
        else if (meta.audio_cue.type === 'chime' || meta.audio_cue.type === 'trade') synth.playChime();
        else if (meta.audio_cue.type === 'alert') synth.playAlert();
      }
      this.lastAudioSeq = meta.audio_cue.seq;
    }

    // Phase Layout Dispatcher
    const mainLayout = document.getElementById('proj-main-layout');
    const quickStage = document.getElementById('proj-quick-plenary-stage');
    const grandStage = document.getElementById('proj-grand-plenary-stage');
    const concludedStage = document.getElementById('proj-concluded-stage');

    if (meta.phase === 'summit_concluded') {
      if (mainLayout) mainLayout.style.display = 'none';
      if (quickStage) quickStage.style.display = 'none';
      if (grandStage) grandStage.style.display = 'none';
      if (concludedStage) {
        concludedStage.style.display = 'block';
        this.renderSummitConcluded(state.summit_outcome, proposals, news_feed);
      }
    } else if (meta.phase === 'plenary_quick') {
      if (concludedStage) concludedStage.style.display = 'none';
      if (mainLayout) mainLayout.style.display = 'none';
      if (grandStage) grandStage.style.display = 'none';
      if (quickStage) {
        quickStage.style.display = 'block';
        this.renderQuickPlenary(meta, proposals, realms);
      }
    } else if (meta.phase === 'grand_plenary_discussion' || meta.phase === 'grand_plenary_voting') {
      if (concludedStage) concludedStage.style.display = 'none';
      if (mainLayout) mainLayout.style.display = 'none';
      if (quickStage) quickStage.style.display = 'none';
      if (grandStage) {
        grandStage.style.display = 'block';
        this.renderGrandPlenary(meta, proposals, realms);
      }
    } else {
      if (concludedStage) concludedStage.style.display = 'none';
      if (quickStage) quickStage.style.display = 'none';
      if (grandStage) grandStage.style.display = 'none';
      if (mainLayout) mainLayout.style.display = 'flex';
      this.renderWorkingSession(meta, proposals, realms, news_feed);
    }
  }

  renderSummitConcluded(outcome, proposals, news_feed) {
    if (!outcome) return;

    const verdictTitle = document.getElementById('proj-verdict-title');
    const verdictDesc = document.getElementById('proj-verdict-desc');
    const timestampEl = document.getElementById('proj-concluded-timestamp');
    const badgesEl = document.getElementById('proj-verdict-badges');

    if (verdictTitle) verdictTitle.innerText = outcome.continental_verdict;
    if (verdictDesc) verdictDesc.innerText = outcome.continental_desc;
    if (timestampEl) timestampEl.innerText = `CONCLUDED: ${outcome.concluded_time_str}`;

    if (badgesEl) {
      badgesEl.innerHTML = `
        <span class="badge" style="background:#fff; color:#000; padding:4px 10px;">AVERAGE VITALITY: ${outcome.avg_vitality}%</span>
        <span class="badge" style="background:#fff; color:#000; padding:4px 10px;">AVERAGE STABILITY: ${outcome.avg_stability}%</span>
        <span class="badge" style="${outcome.starving_count > 0 ? 'background:#ef4444; color:#fff;' : 'background:#fff; color:#000;'} padding:4px 10px;">
          STARVING REALMS: ${outcome.starving_count}
        </span>
        <span class="badge" style="background:#fff; color:#000; padding:4px 10px;">TREATIES RATIFIED: ${outcome.passed_proposals_count}</span>
      `;
    }

    const realmsList = document.getElementById('proj-debrief-realms-list');
    if (realmsList && outcome.realm_evaluations) {
      realmsList.innerHTML = outcome.realm_evaluations.map((r, idx) => `
        <div style="background:var(--bg-surface-sunken); border:1px solid var(--border-subtle); padding:10px 12px; border-radius:var(--radius-sm);">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <div style="display:flex; align-items:center; gap:8px;">
              <span style="font-family:var(--font-mono); font-weight:900; font-size:1rem; color:var(--text-muted);">#${idx + 1}</span>
              <strong style="font-size:0.95rem; text-transform:uppercase;">${r.name}</strong>
              <span class="badge" style="font-size:0.75rem;">${r.score} PTS</span>
            </div>
            ${r.directive_achieved ? 
              '<span class="badge" style="background:#10b981; color:#fff; font-weight:800; padding:2px 8px;">[DIRECTIVE ACHIEVED (+100)]</span>' : 
              '<span class="badge" style="background:#ef4444; color:#fff; font-weight:800; padding:2px 8px;">[DIRECTIVE FAILED]</span>'}
          </div>
          <div style="font-size:0.75rem; font-family:var(--font-mono); color:var(--text-muted); margin-top:4px;">
            ${r.directive_title}: <span style="color:var(--text-primary); font-weight:600;">${r.directive_explanation}</span>
          </div>
          <p style="font-size:0.8rem; color:var(--text-secondary); margin-top:4px; line-height:1.35;">
            ${r.epilogue}
          </p>
        </div>
      `).join('');
    }

    const honorsEl = document.getElementById('proj-debrief-honors');
    if (honorsEl && outcome.honors) {
      honorsEl.innerHTML = `
        <div style="background:var(--bg-surface-sunken); padding:8px 12px; border-radius:var(--radius-xs); border:1px solid var(--border-subtle);">
          <div style="font-size:0.72rem; font-family:var(--font-mono); color:var(--text-muted);">ARCH-DIPLOMAT OF THE SPIRE</div>
          <strong style="font-size:0.9rem; color:#fff;">${outcome.honors.arch_diplomat.name}</strong>
          <span style="font-size:0.75rem; font-family:var(--font-mono); color:var(--text-secondary); margin-left:6px;">(${outcome.honors.arch_diplomat.standing}/100 Standing)</span>
        </div>
        <div style="background:var(--bg-surface-sunken); padding:8px 12px; border-radius:var(--radius-xs); border:1px solid var(--border-subtle);">
          <div style="font-size:0.72rem; font-family:var(--font-mono); color:var(--text-muted);">INDUSTRIAL HEGEMON</div>
          <strong style="font-size:0.9rem; color:#fff;">${outcome.honors.industrial_hegemon.name}</strong>
          <span style="font-size:0.75rem; font-family:var(--font-mono); color:var(--text-secondary); margin-left:6px;">(${outcome.honors.industrial_hegemon.cores} Cores)</span>
        </div>
        <div style="background:var(--bg-surface-sunken); padding:8px 12px; border-radius:var(--radius-xs); border:1px solid var(--border-subtle);">
          <div style="font-size:0.72rem; font-family:var(--font-mono); color:var(--text-muted);">BREADBASKET OF THE CONTINENT</div>
          <strong style="font-size:0.9rem; color:#fff;">${outcome.honors.breadbasket.name}</strong>
          <span style="font-size:0.75rem; font-family:var(--font-mono); color:var(--text-secondary); margin-left:6px;">(${outcome.honors.breadbasket.grain} Grain)</span>
        </div>
      `;
    }

    const accordsEl = document.getElementById('proj-debrief-accords');
    if (accordsEl && proposals) {
      const passed = proposals.filter(p => p.status === 'passed');
      if (passed.length === 0) {
        accordsEl.innerHTML = '<p class="text-muted" style="font-size:0.78rem; font-family:var(--font-mono);">No multilateral treaties were passed into law.</p>';
      } else {
        accordsEl.innerHTML = passed.map(p => `
          <div style="border-left:2px solid #fff; padding-left:8px; margin-bottom:6px;">
            <strong style="font-size:0.82rem;">${p.title}</strong>
            <div style="font-size:0.72rem; font-family:var(--font-mono); color:var(--text-muted);">SPONSORS: ${p.proposer_name} • ${p.effect_type.toUpperCase()}</div>
          </div>
        `).join('');
      }
    }
  }

  renderWorkingSession(meta, proposals, realms, news_feed) {
    // 1. Dominant Hero Breaking Bulletin
    if (news_feed && news_feed.length > 0) {
      const topNews = news_feed[0];
      const heroHead = document.getElementById('proj-hero-headline');
      const heroDetail = document.getElementById('proj-hero-detail');
      const heroTime = document.getElementById('proj-hero-time');
      if (heroHead) heroHead.innerText = topNews.headline;
      if (heroDetail) heroDetail.innerText = topNews.detail;
      if (heroTime) heroTime.innerText = topNews.time_str;
    }

    // 2. Chronological Wire Stream (Compact for zero scrolling)
    const newsList = document.getElementById('projector-news-list');
    if (newsList && news_feed) {
      newsList.innerHTML = news_feed.slice(0, 4).map(n => `
        <div style="border-bottom: 1px solid var(--border-subtle); padding: 6px 0;">
          <div style="display:flex; justify-content:space-between; font-size:0.72rem; font-family:var(--font-mono); color:var(--text-muted);">
            <strong style="color:var(--text-primary); font-size:0.78rem;">[${n.type.toUpperCase()}] ${n.headline}</strong>
            <span>${n.time_str}</span>
          </div>
          <p style="color:var(--text-secondary); font-size:0.8rem; margin-top:2px; line-height:1.35;">${n.detail}</p>
        </div>
      `).join('');
    }

    // 3. Qualitative Continental Intel (Fog of War: Zero exact numbers leaked!)
    const realmsList = document.getElementById('projector-realms-list');
    if (realmsList) {
      realmsList.innerHTML = realms.map(r => `
        <div style="background:var(--bg-surface-sunken); border:1px solid var(--border-subtle); padding:6px 10px; border-radius:var(--radius-xs);">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <strong style="font-size:0.85rem; text-transform:uppercase;">${r.name}</strong>
            <span class="badge" style="font-size:0.68rem; padding:2px 6px;">${r.assembly_votes} VOTE${r.assembly_votes > 1 ? 'S' : ''}</span>
          </div>
          <div style="font-size:0.7rem; color:var(--text-secondary); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; margin-top:1px;">${r.ethos}</div>
          <div style="display:flex; gap:8px; font-size:0.68rem; font-family:var(--font-mono); margin-top:3px; color:var(--text-muted);">
            <span>GRAIN: <strong style="color:var(--text-primary);">${r.grain_tier}</strong></span>
            <span>CORES: <strong style="color:var(--text-primary);">${r.cores_tier}</strong></span>
            <span>SILK: <strong style="color:var(--text-primary);">${r.silk_tier}</strong></span>
          </div>
          <div style="display:flex; gap:8px; font-size:0.68rem; font-family:var(--font-mono); margin-top:2px; color:var(--text-muted);">
            <span>STAND: <strong style="color:var(--text-primary);">${r.standing_tier}</strong></span>
            <span>VIT: <strong style="color:var(--text-primary);">${r.vitality_tier}</strong></span>
            <span>STAB: <strong style="color:var(--text-primary);">${r.stability_tier}</strong></span>
            ${r.is_starving ? '<span class="badge badge-danger" style="font-size:0.65rem; padding:1px 4px;">FAMINE</span>' : ''}
          </div>
        </div>
      `).join('');
    }

    // 4. Qualified Motions Ticker
    const motionsTicker = document.getElementById('projector-qualified-motions-list');
    if (motionsTicker) {
      const qualified = proposals.filter(p => (p.support_list && p.support_list.length >= 2) || p.is_qualified);
      if (qualified.length === 0) {
        motionsTicker.innerHTML = '<p class="text-muted" style="font-size:0.78rem; font-family:var(--font-mono);">No resolutions have qualified for the plenary docket yet.</p>';
      } else {
        motionsTicker.innerHTML = qualified.map(p => `
          <div style="background:var(--bg-surface-sunken); border:1px solid var(--border-subtle); border-radius:4px; padding:8px 12px; display:flex; justify-content:space-between; align-items:center;">
            <div>
              <strong style="font-size:0.85rem;">${p.title}</strong>
              <div style="font-size:0.72rem; color:var(--text-muted); font-family:var(--font-mono);">Sponsor: ${p.proposer_name}</div>
            </div>
            <span class="badge" style="border-color:var(--border-white);">QUALIFIED (${p.support_list.length} CO-SPONSORS)</span>
          </div>
        `).join('');
      }
    }
  }

  renderQuickPlenary(meta, proposals, realms) {
    const list = document.getElementById('proj-quick-plenary-docket-list');
    if (!list) return;

    const docket = meta.plenary_docket || [];
    const docketProps = proposals.filter(p => docket.includes(p.id));

    list.innerHTML = docketProps.map((p, idx) => {
      const tallies = p.tallies || { support_weight: 0, oppose_weight: 0, abstain_weight: 0 };
      const total = tallies.support_weight + tallies.oppose_weight;
      const pct = total > 0 ? (tallies.support_weight / total) * 100 : 50;

      const votes = p.votes || {};
      const ballotsHtml = realms.map(r => {
        const v = votes[r.id];
        let badge = '<span class="badge" style="color:var(--text-muted);">VOTE PENDING</span>';
        if (v) {
          if (v.choice === 'support') badge = `<span class="badge" style="color:var(--text-primary); border-color:var(--border-white);">SUPPORT (+${v.weight})</span>`;
          else if (v.choice === 'oppose') badge = `<span class="badge badge-danger">OPPOSE (+${v.weight})</span>`;
          else badge = `<span class="badge">ABSTAIN</span>`;
        }
        return `
          <div style="background:var(--bg-surface-sunken); border:1px solid var(--border-subtle); padding:6px 10px; border-radius:4px; display:flex; justify-content:space-between; align-items:center; font-size:0.75rem;">
            <strong>${r.name}</strong>
            ${badge}
          </div>
        `;
      }).join('');

      return `
        <div style="background:var(--bg-surface); border:1px solid var(--border-subtle); border-radius:6px; padding:16px;">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <h3 style="font-size:1.15rem; font-weight:800;">#${idx + 1}: ${p.title}</h3>
            <span class="badge" style="font-family:var(--font-mono);">${p.support_list.length} CO-SPONSORS</span>
          </div>
          <p style="font-size:0.85rem; color:var(--text-secondary); margin:6px 0 12px 0;">${p.description}</p>
          
          <div style="display:flex; justify-content:space-between; font-family:var(--font-mono); font-weight:800; font-size:0.85rem; margin-bottom:4px;">
            <span>SUPPORT: ${tallies.support_weight}</span>
            <span>OPPOSE: ${tallies.oppose_weight}</span>
          </div>
          <div style="width:100%; height:8px; background:var(--bg-surface-sunken); border:1px solid var(--border-subtle); border-radius:4px; overflow:hidden; margin-bottom:12px;">
            <div style="height:100%; background:var(--border-white); width:${pct}%;"></div>
          </div>

          <div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(180px, 1fr)); gap:6px;">
            ${ballotsHtml}
          </div>
        </div>
      `;
    }).join('');
  }

  renderGrandPlenary(meta, proposals, realms) {
    const docket = meta.plenary_docket || [];
    const idx = meta.current_motion_index || 0;
    const activeProp = proposals.find(p => p.id === docket[idx]);

    if (!activeProp) return;

    document.getElementById('proj-grand-badge').innerText = `GRAND PLENARY RESOLUTION ${idx + 1} OF ${docket.length}`;
    document.getElementById('proj-grand-phase-label').innerText = meta.phase === 'grand_plenary_discussion' ? '5-MINUTE FLOOR DEBATE' : 'SOVEREIGN ROLL-CALL VOTE';
    document.getElementById('proj-debate-clock').innerText = formatSeconds(meta.discussion_timer_remaining);
    document.getElementById('proj-grand-title').innerText = activeProp.title;
    document.getElementById('proj-grand-sponsors').innerText = `Sponsor: ${activeProp.proposer_name} | Co-Sponsors: ${(activeProp.supporters || []).map(s => s.name).join(', ')}`;
    document.getElementById('proj-grand-desc').innerText = activeProp.description;

    const votingFloor = document.getElementById('proj-grand-voting-floor');
    if (meta.phase === 'grand_plenary_voting') {
      votingFloor.style.display = 'block';
      const tallies = activeProp.tallies || { support_weight: 0, oppose_weight: 0, abstain_weight: 0 };
      document.getElementById('proj-grand-support-tally').innerText = `${tallies.support_weight} Votes`;
      document.getElementById('proj-grand-oppose-tally').innerText = `${tallies.oppose_weight} Votes`;

      const total = tallies.support_weight + tallies.oppose_weight;
      const pct = total > 0 ? (tallies.support_weight / total) * 100 : 50;
      document.getElementById('proj-grand-tally-bar').style.width = `${pct}%`;

      const votes = activeProp.votes || {};
      const grid = document.getElementById('proj-grand-rollcall-grid');
      grid.innerHTML = realms.map(r => {
        const v = votes[r.id];
        let badge = '<span class="badge" style="color:var(--text-muted);">VOTE PENDING</span>';
        if (v) {
          if (v.choice === 'support') badge = `<span class="badge" style="color:var(--text-primary); border-color:var(--border-white);">SUPPORT (+${v.weight})</span>`;
          else if (v.choice === 'oppose') badge = `<span class="badge badge-danger">OPPOSE (+${v.weight})</span>`;
          else badge = `<span class="badge">ABSTAIN</span>`;
        }
        return `
          <div style="background:var(--bg-surface-sunken); border:1px solid var(--border-subtle); padding:8px 12px; border-radius:4px; display:flex; justify-content:space-between; align-items:center; font-size:0.82rem;">
            <strong>${r.name}</strong>
            ${badge}
          </div>
        `;
      }).join('');
    } else {
      votingFloor.style.display = 'none';
    }
  }
}

// -----------------------------------------------------------------------------
// Facilitator / Admin Command Deck Logic (AdminApp)
// -----------------------------------------------------------------------------
class AdminApp {
  constructor() {
    this.isPolling = false;
  }

  start() {
    this.pollState();
    setInterval(() => this.pollState(), 1000);
    this.loadCatalogEvents();
    this.bindEvents();
  }

  async loadCatalogEvents() {
    try {
      const resp = await fetch('/api/events');
      const data = await resp.json();
      const select = document.getElementById('catalog-event-select');
      if (select && data.events) {
        select.innerHTML = data.events.map(e => `
          <option value="${e.id}">[T${e.turn_recommended}] ${e.headline} (${e.category})</option>
        `).join('');
      }
    } catch (err) {
      console.warn('Failed to load events catalog:', err);
    }
  }

  async pollState() {
    if (this.isPolling) return;
    this.isPolling = true;

    try {
      const resp = await fetch('/api/state');
      if (!resp.ok) throw new Error('Failed to fetch state');
      const state = await resp.json();
      this.renderState(state);
    } catch (err) {
      console.warn('Admin polling error:', err);
    } finally {
      this.isPolling = false;
    }
  }

  renderState(state) {
    const { meta, realms, proposals, news_feed } = state;

    // Header Pills
    const turnEl = document.getElementById('admin-turn-display');
    if (turnEl) turnEl.innerText = `TURN ${meta.current_turn}`;

    const timerEl = document.getElementById('admin-timer-display');
    if (timerEl) {
      timerEl.innerText = formatSeconds(meta.turn_timer_remaining);
    }

    // Auto-inject crisis
    const autoCheck = document.getElementById('check-auto-inject-turn');
    if (autoCheck && document.activeElement !== autoCheck) {
      autoCheck.checked = Boolean(meta.auto_inject_crisis);
    }

    // Tab 1: Pacing & Plenary Phase
    const phaseDisplay = document.getElementById('admin-phase-display');
    const controlsContainer = document.getElementById('admin-plenary-controls');

    if (phaseDisplay && controlsContainer) {
      if (meta.phase === 'working') {
        phaseDisplay.innerText = `WORKING SESSION (5 MINUTES)`;
        controlsContainer.innerHTML = `
          <button class="btn btn-primary btn-sm" onclick="adminApp.startPlenary()">
            ⚡ Convene Between-Rounds Plenary
          </button>
        `;
      } else if (meta.phase === 'plenary_quick') {
        phaseDisplay.innerText = `BETWEEN-ROUNDS PLENARY: QUICK VOTE`;
        controlsContainer.innerHTML = `
          <button class="btn btn-primary btn-sm" onclick="adminApp.concludeQuickPlenary()">
            ⏩ Settle Plenary & End Turn
          </button>
        `;
      } else if (meta.phase === 'grand_plenary_discussion') {
        phaseDisplay.innerText = `GRAND PLENARY: 5M FLOOR DEBATE`;
        controlsContainer.innerHTML = `
          <button class="btn btn-secondary btn-sm" onclick="adminApp.controlDiscussionTimer('start')">▶ Start Debate</button>
          <button class="btn btn-secondary btn-sm" onclick="adminApp.controlDiscussionTimer('pause')">⏸ Pause</button>
          <button class="btn btn-primary btn-sm" onclick="adminApp.callGrandVote()">🗳️ Call Sovereign Vote Now</button>
        `;
      } else if (meta.phase === 'grand_plenary_voting') {
        phaseDisplay.innerText = `GRAND PLENARY: SOVEREIGN VOTE ACTIVE`;
        controlsContainer.innerHTML = `
          <button class="btn btn-primary btn-sm" onclick="adminApp.nextGrandMotion()">
            Next Motion in Docket ⏩
          </button>
        `;
      } else if (meta.phase === 'turn_summary') {
        if (meta.current_turn >= 3) {
          phaseDisplay.innerText = `TURN 3 CONCLUDED: READY FOR FINAL DEBRIEF`;
          controlsContainer.innerHTML = `
            <button class="btn btn-primary btn-sm" onclick="adminApp.concludeSummit()">
              🏆 Finalize Summit & Reveal Debrief
            </button>
          `;
        } else {
          phaseDisplay.innerText = `PLENARY CONCLUDED (READY FOR END OF TURN)`;
          controlsContainer.innerHTML = `
            <button class="btn btn-primary btn-sm" onclick="adminApp.advanceTurn()">
              ⏩ Advance to Next Turn
            </button>
          `;
        }
      } else if (meta.phase === 'summit_concluded') {
        phaseDisplay.innerText = `SUMMIT CONCLUDED: CONTINENTAL DEBRIEF ACTIVE`;
        controlsContainer.innerHTML = `
          <a href="/projector" target="_blank" class="btn btn-secondary btn-sm" style="display:inline-flex; align-items:center;">📽️ Open Projector Debrief</a>
          <button class="btn btn-danger btn-sm" onclick="adminApp.openResetModal()">↺ Reset Simulation</button>
        `;
      }
    }

    // Tab 3: Resource Telemetry Table
    const tableBody = document.getElementById('admin-realms-tbody');
    if (tableBody) {
      tableBody.innerHTML = realms.map(r => `
        <tr>
          <td>
            <div style="display:flex; align-items:center; gap: 8px;">
              <strong>${r.name}</strong>
              ${r.is_plutocrat ? '<span class="badge">[PLUTOCRAT]</span>' : ''}
              ${r.is_starving ? '<span class="badge badge-danger">[STARVING]</span>' : ''}
            </div>
          </td>
          <td>
            <div class="inline-num-ctrl">
              <button class="inline-num-btn" onclick="adminApp.adjustStat('${r.id}', 'alchemical_grain', -5)">-</button>
              <span class="inline-num-val">${r.alchemical_grain}</span>
              <button class="inline-num-btn" onclick="adminApp.adjustStat('${r.id}', 'alchemical_grain', 5)">+</button>
            </div>
          </td>
          <td>
            <div class="inline-num-ctrl">
              <button class="inline-num-btn" onclick="adminApp.adjustStat('${r.id}', 'aether_cores', -5)">-</button>
              <span class="inline-num-val">${r.aether_cores}</span>
              <button class="inline-num-btn" onclick="adminApp.adjustStat('${r.id}', 'aether_cores', 5)">+</button>
            </div>
          </td>
          <td>
            <div class="inline-num-ctrl">
              <button class="inline-num-btn" onclick="adminApp.adjustStat('${r.id}', 'echo_silk', -5)">-</button>
              <span class="inline-num-val">${r.echo_silk}</span>
              <button class="inline-num-btn" onclick="adminApp.adjustStat('${r.id}', 'echo_silk', 5)">+</button>
            </div>
          </td>
          <td>
            <div class="inline-num-ctrl">
              <button class="inline-num-btn" onclick="adminApp.adjustStat('${r.id}', 'military_power', -5)">-</button>
              <span class="inline-num-val">${r.military_power || 50}</span>
              <button class="inline-num-btn" onclick="adminApp.adjustStat('${r.id}', 'military_power', 5)">+</button>
            </div>
          </td>
          <td>
            <div class="inline-num-ctrl">
              <button class="inline-num-btn" onclick="adminApp.adjustStat('${r.id}', 'public_vitality', -5)">-</button>
              <span class="inline-num-val">${r.public_vitality}</span>
              <button class="inline-num-btn" onclick="adminApp.adjustStat('${r.id}', 'public_vitality', 5)">+</button>
            </div>
          </td>
          <td>
            <div class="inline-num-ctrl">
              <button class="inline-num-btn" onclick="adminApp.adjustStat('${r.id}', 'diplomatic_standing', -5)">-</button>
              <span class="inline-num-val">${r.diplomatic_standing}</span>
              <button class="inline-num-btn" onclick="adminApp.adjustStat('${r.id}', 'diplomatic_standing', 5)">+</button>
            </div>
          </td>
          <td>
            <div class="inline-num-ctrl">
              <button class="inline-num-btn" onclick="adminApp.adjustStat('${r.id}', 'civil_stability', -5)">-</button>
              <span class="inline-num-val">${r.civil_stability}</span>
              <button class="inline-num-btn" onclick="adminApp.adjustStat('${r.id}', 'civil_stability', 5)">+</button>
            </div>
          </td>
          <td>
            <span class="badge">${r.assembly_votes} VOTES</span>
          </td>
          <td>
            <button class="btn btn-secondary btn-sm" onclick="adminApp.editRealmModal('${r.id}')">Edit</button>
          </td>
        </tr>
      `).join('');
    }

    // Tab 4: Floor Resolutions List
    const resList = document.getElementById('admin-resolutions-list');
    if (resList) {
      if (proposals.length === 0) {
        resList.innerHTML = '<p class="text-muted" style="font-size:0.8rem; font-family:var(--font-mono);">No floor resolutions registered.</p>';
      } else {
        resList.innerHTML = proposals.map(p => {
          const qual = p.support_list.length >= 2 || p.is_qualified;
          return `
            <div style="background:var(--bg-surface-sunken); border:1px solid var(--border-subtle); padding:12px; border-radius:4px;">
              <div style="display:flex; justify-content:space-between; align-items:center;">
                <strong style="font-size:0.95rem;">${p.title}</strong>
                <span class="badge" style="border-color:${qual ? '#fff' : 'var(--border-subtle)'};">
                  ${qual ? 'QUALIFIED FOR PLENARY' : `AWAITING ENDORSEMENT (${p.support_list.length}/2)`}
                </span>
              </div>
              <div style="font-size:0.75rem; font-family:var(--font-mono); color:var(--text-muted); margin:4px 0;">
                Sponsor: ${p.proposer_name} | Co-Sponsors: ${(p.supporters || []).map(s => s.name).join(', ')}
              </div>
              <p style="font-size:0.82rem; color:var(--text-secondary);">${p.description}</p>
              <div style="display:flex; justify-content:space-between; font-size:0.75rem; font-family:var(--font-mono); margin-top:8px; color:var(--text-primary);">
                <span>SUPPORT: ${p.tallies.support_weight}</span>
                <span>OPPOSE: ${p.tallies.oppose_weight}</span>
                <span>STATUS: ${p.status.toUpperCase()}</span>
              </div>
            </div>
          `;
        }).join('');
      }
    }

    // Tab 5: Delegations & PINs Table
    const pinsTbody = document.getElementById('admin-pins-tbody');
    if (pinsTbody) {
      pinsTbody.innerHTML = realms.map(r => `
        <tr>
          <td><strong>${r.name}</strong></td>
          <td style="font-size:0.78rem; color:var(--text-secondary);">${r.ethos}</td>
          <td><span class="badge" style="font-size:0.9rem; font-family:var(--font-mono);">${r.pin || '1001'}</span></td>
          <td>
            <button class="btn btn-secondary btn-sm" onclick="adminApp.promptChangePin('${r.id}', '${r.name}')">Change PIN</button>
          </td>
        </tr>
      `).join('');
    }

    // News Audit Log
    const newsBox = document.getElementById('admin-news-feed');
    if (newsBox && news_feed) {
      newsBox.innerHTML = news_feed.slice(0, 15).map(n => `
        <div style="border-bottom: 1px solid var(--border-subtle); padding: 8px 0; font-size: 0.8rem;">
          <div style="display:flex; justify-content:space-between; font-family:var(--font-mono); font-size:0.72rem; color: var(--text-muted);">
            <strong style="color: #fff;">[${n.type.toUpperCase()}] ${n.headline}</strong>
            <span>${n.time_str}</span>
          </div>
          <p style="color: var(--text-secondary); margin-top: 2px;">${n.detail}</p>
        </div>
      `).join('');
    }
  }

  bindEvents() {
    const chimeBtn = document.getElementById('btn-sound-chime');
    if (chimeBtn) {
      chimeBtn.addEventListener('click', async () => {
        synth.playGong();
        await fetch('/api/admin/chime', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ type: 'gong', message: 'Attention Sovereign Delegates' })
        });
      });
    }
  }

  async setCustomTimer() {
    const mins = parseInt(document.getElementById('input-custom-mins').value || 0, 10);
    const secs = parseInt(document.getElementById('input-custom-secs').value || 0, 10);
    const total = (mins * 60) + secs;
    try {
      await fetch('/api/admin/timer/set', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ seconds: total })
      });
      showToast(`Timer set to ${formatSeconds(total)}`, 'info');
      this.pollState();
    } catch(err) {
      showToast('Failed to set timer', 'danger');
    }
  }

  async adjustTimer(deltaSeconds) {
    try {
      await fetch('/api/admin/timer/adjust', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ delta_seconds: deltaSeconds })
      });
      showToast(`Timer adjusted by ${deltaSeconds > 0 ? '+' : ''}${deltaSeconds}s`, 'info');
      this.pollState();
    } catch(err) {
      showToast('Failed to adjust timer', 'danger');
    }
  }

  async controlTimer(action, total_seconds = null) {
    try {
      await fetch('/api/admin/timer/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, total_seconds })
      });
      this.pollState();
    } catch(err) {
      showToast('Timer action failed', 'danger');
    }
  }

  async advanceTurn() {
    if (!confirm('Execute End of Turn calculations? This will deduct baseline grain, check starvation/complacency, and advance to next turn.')) return;
    try {
      const resp = await fetch('/api/admin/turn/next', { method: 'POST' });
      const res = await resp.json();
      if (res.success) {
        showToast(`Turn ${res.result.new_turn} initiated`, 'info');
        synth.playGong();
        this.pollState();
      }
    } catch (err) {
      showToast('Turn processing failed', 'danger');
    }
  }

  async promptChangePin(realmId, realmName) {
    const newPin = prompt(`Enter new 4-digit PIN for ${realmName}:`);
    if (!newPin || !newPin.trim()) return;

    try {
      const resp = await fetch('/api/admin/pin/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ realm_id: realmId, pin: newPin.trim() })
      });
      const res = await resp.json();
      if (res.success) {
        showToast(`PIN updated for ${realmName}`, 'info');
        this.pollState();
      } else {
        showToast(res.message, 'danger');
      }
    } catch(err) {
      showToast('Failed to update PIN', 'danger');
    }
  }

  async handleBroadcastNews(e) {
    e.preventDefault();
    const headline = document.getElementById('admin-news-headline').value;
    const detail = document.getElementById('admin-news-detail').value;
    try {
      await fetch('/api/admin/news/broadcast', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ headline, detail, type: 'crisis' })
      });
      showToast('Dispatch broadcast to all terminals', 'info');
      synth.playAlert();
      document.getElementById('admin-news-form').reset();
      this.pollState();
    } catch (err) {
      showToast('Broadcast failed', 'danger');
    }
  }

  async startPlenary() {
    try {
      const resp = await fetch('/api/admin/plenary/start', { method: 'POST' });
      const res = await resp.json();
      if (res.success) {
        showToast(res.message, 'info');
        synth.playGong();
        this.pollState();
      } else {
        showToast(res.message, 'danger');
      }
    } catch (err) {
      showToast('Failed to start plenary', 'danger');
    }
  }

  async concludeQuickPlenary() {
    try {
      const resp = await fetch('/api/admin/plenary/conclude_quick', { method: 'POST' });
      const res = await resp.json();
      if (res.success) {
        showToast(res.message, 'info');
        synth.playChime();
        this.pollState();
      } else {
        showToast(res.message, 'danger');
      }
    } catch (err) {
      showToast('Failed to conclude plenary', 'danger');
    }
  }

  async controlDiscussionTimer(action) {
    try {
      await fetch('/api/admin/discussion_timer/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, total_seconds: 300 })
      });
      this.pollState();
    } catch (err) {
      showToast('Timer control failed', 'danger');
    }
  }

  async callGrandVote() {
    try {
      const resp = await fetch('/api/admin/plenary/call_vote', { method: 'POST' });
      const res = await resp.json();
      if (res.success) {
        showToast(res.message, 'info');
        synth.playGong();
        this.pollState();
      } else {
        showToast(res.message, 'danger');
      }
    } catch (err) {
      showToast('Failed to call vote', 'danger');
    }
  }

  async nextGrandMotion() {
    try {
      const resp = await fetch('/api/admin/plenary/next', { method: 'POST' });
      const res = await resp.json();
      if (res.success) {
        showToast(res.message, 'info');
        synth.playGong();
        this.pollState();
      } else {
        showToast(res.message, 'danger');
      }
    } catch (err) {
      showToast('Failed to advance motion', 'danger');
    }
  }

  async triggerAutoNextEvent() {
    try {
      const resp = await fetch('/api/admin/event/auto', { method: 'POST' });
      const res = await resp.json();
      if (res.success) {
        showToast(`Crisis Executed: ${res.event.headline}`, 'info');
        synth.playAlert();
        this.pollState();
      } else {
        showToast(res.message, 'danger');
      }
    } catch (err) {
      showToast('Failed to trigger event', 'danger');
    }
  }

  async triggerSelectedCatalogEvent() {
    const select = document.getElementById('catalog-event-select');
    if (!select || !select.value) return;

    try {
      const resp = await fetch('/api/admin/event/trigger', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ event_id: select.value })
      });
      const res = await resp.json();
      if (res.success) {
        showToast('Catalog crisis injected', 'info');
        synth.playAlert();
        this.pollState();
      } else {
        showToast(res.message, 'danger');
      }
    } catch (err) {
      showToast('Failed to trigger crisis', 'danger');
    }
  }

  async toggleAutoCrisisOnTurn(enabled) {
    try {
      await fetch('/api/admin/config/toggle_auto_crisis', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled })
      });
      showToast(enabled ? 'Auto-inject crisis on Turn enabled' : 'Auto-inject crisis on Turn disabled', 'info');
    } catch (err) {
      showToast('Failed to update config', 'danger');
    }
  }

  async adjustStat(realmId, stat, delta) {
    try {
      const resp = await fetch('/api/state');
      const state = await resp.json();
      const realm = state.realms.find(r => r.id === realmId);
      if (!realm) return;

      const currentVal = realm[stat] || 0;
      const newVal = Math.max(0, currentVal + delta);

      await fetch('/api/admin/realm/override', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          realm_id: realmId,
          updates: { [stat]: newVal }
        })
      });
      this.pollState();
    } catch (err) {
      showToast('Override failed', 'danger');
    }
  }

  openResetModal() {
    const modal = document.getElementById('modal-confirm-reset');
    if (modal) modal.style.display = 'flex';
  }

  closeResetModal() {
    const modal = document.getElementById('modal-confirm-reset');
    if (modal) modal.style.display = 'none';
  }

  async resetSimulation() {
    this.closeResetModal();
    try {
      await fetch('/api/admin/reset', { method: 'POST' });
      showToast('Simulation reset to Turn 1', 'info');
      synth.playGong();
      window.location.reload();
    } catch (err) {
      showToast('Reset failed', 'danger');
    }
  }

  async triggerRoomAudio(cueType, message) {
    try {
      await fetch('/api/admin/chime', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: cueType, message })
      });
      showToast(`Triggered ${cueType} alert`, 'info');
    } catch (err) {
      showToast('Audio trigger failed', 'danger');
    }
  }

  async concludeSummit() {
    try {
      const resp = await fetch('/api/admin/summit/conclude', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      const res = await resp.json();
      if (res.success) {
        showToast('Summit officially concluded! Debriefing active.', 'info');
        synth.playGong();
        this.pollState();
      } else {
        showToast(res.message, 'danger');
      }
    } catch (err) {
      showToast('Failed to conclude summit', 'danger');
    }
  }
}

window.synth = synth;
window.showToast = showToast;
window.RealmApp = RealmApp;
window.ProjectorApp = ProjectorApp;
window.AdminApp = AdminApp;
