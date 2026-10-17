/**
 * The Summit of Realms - phone console for a delegation (RealmApp)
 */
'use strict';

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
    const current = document.querySelector('.mobile-view.active');
    if (current && current.id !== 'view-wiki' && viewId === 'view-wiki') this.viewBeforeWiki = current.id;
    // Reading mode: the encyclopedia takes the whole screen, game chrome is hidden.
    document.body.classList.toggle('wiki-mode', viewId === 'view-wiki');
    document.querySelectorAll('.bottom-nav-item').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.view === viewId);
    });
    document.querySelectorAll('.mobile-view').forEach(v => {
      v.classList.toggle('active', v.id === viewId);
    });
    if (viewId === 'view-wiki' && !this.wikiLoaded) this.wikiHome();
    if (viewId === 'view-quiz') this.loadQuiz();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  async leaveDelegation(e) {
    if (e) e.preventDefault();
    if (confirm('Leave this sovereign delegation and return to lobby?')) {
      try {
        await fetch('/api/auth/realm/logout', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ realm_id: this.realmId })
        });
      } catch (err) {}
      window.location.href = '/';
    }
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

  // ---------------------------------------------------------------------------
  // Motions: template gallery -> editable draft
  // ---------------------------------------------------------------------------
  renderMotionTemplates(types) {
    const box = document.getElementById('motion-templates');
    if (!box || this.motionTemplatesRendered || !types || !types.length) return;
    this.motionTypes = Object.fromEntries(types.map(t => [t.id, t]));
    const esc = escapeHtml;
    box.innerHTML = types.filter(t => t.player_selectable).map(t => `
      <button type="button" class="motion-template" onclick="realmApp.chooseMotionTemplate('${esc(t.id)}')">
        <span class="motion-template-icon">${esc(t.icon || '📜')}</span>
        <span class="grow">
          <span class="motion-template-name">${esc(t.name)}</span>
          <span class="motion-template-summary">${esc(t.summary)}</span>
          <span class="motion-effect"><span>If passed:</span> ${esc(t.effect_plain || t.statutory_effect)}</span>
        </span>
        <span class="motion-template-go">Use &rsaquo;</span>
      </button>`).join('');
    this.motionTemplatesRendered = true;
  }

  chooseMotionTemplate(typeId) {
    const form = document.getElementById('proposal-form');
    const gallery = document.getElementById('motion-templates');
    if (!typeId) {
      form.style.display = 'none';
      gallery.style.display = '';
      return;
    }
    const t = (this.motionTypes || {})[typeId];
    if (!t) return;
    document.getElementById('proposal-type').value = t.id;
    document.getElementById('motion-chosen-name').innerText = `${t.icon || ''} ${t.name}`;
    document.getElementById('motion-chosen-effect').innerText = t.effect_plain || t.statutory_effect;
    document.getElementById('proposal-title').value = t.default_title || t.name;
    document.getElementById('proposal-desc').value = t.default_terms || t.summary;
    const targetGroup = document.getElementById('proposal-target-nation-group');
    targetGroup.style.display = t.needs_target ? 'block' : 'none';
    document.getElementById('proposal-target-nation').required = !!t.needs_target;
    document.getElementById('proposal-target-nation').value = '';
    document.getElementById('proposal-target-nation-label').innerText = t.target_label || 'Nation';
    gallery.style.display = 'none';
    form.style.display = 'block';
    form.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  async handleDraftProposal(e) {
    e.preventDefault();
    const effectType = document.getElementById('proposal-type').value;
    const t = (this.motionTypes || {})[effectType] || {};
    const body = {
      proposer_id: this.realmId,
      title: document.getElementById('proposal-title').value,
      effect_type: effectType,
      description: document.getElementById('proposal-desc').value,
      target_seconder_id: document.getElementById('proposal-target-realm').value || null,
      target_realm_id: t.needs_target ? document.getElementById('proposal-target-nation').value : null
    };
    try {
      const resp = await fetch('/api/proposal/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      const res = await resp.json();
      if (res.success) {
        showToast('Motion tabled. Now find a nation to co-sponsor it!', 'success');
        synth.playChime();
        document.getElementById('proposal-form').reset();
        this.chooseMotionTemplate(null);
        this.pollState();
      } else {
        showToast(res.message, 'danger');
      }
    } catch (err) {
      showToast('Failed to table the motion', 'danger');
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
    this._lastRealms = realms;

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
    this.renderPhaseCard(meta);

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

    // Live lists of the nations actually playing (the facilitator can change the roster mid-game)
    this.renderTradePartners(realms);
    this.renderMotionNationOptions(realms);

    // Telemetry - Exact values for own country
    this._setVal('grain-val', realm.alchemical_grain);
    this._setVal('cores-val', realm.aether_cores);
    this._setVal('silk-val', realm.echo_silk);
    this._setVal('military-val', realm.military_power ?? 0);

    // Metrics
    this._setMetric('vitality', realm.public_vitality);
    this._setMetric('standing', realm.diplomatic_standing);
    this._setMetric('stability', realm.civil_stability);

    // Assembly votes
    const votesBadge = document.getElementById('votes-badge');
    if (votesBadge) {
      let voteText = `${realm.assembly_votes} vote${realm.assembly_votes === 1 ? '' : 's'} in the Assembly`;
      if (realm.is_plutocrat) voteText += ` · richest nation (+1)`;
      votesBadge.innerText = voteText;
    }

    // Flags
    this.renderFlags(realm);

    // Continental registry (World tab): live, fog-of-war tiers for other nations
    this.renderRegistry(realms);

    // Trades
    this.renderTrades(trades, realm);

    // Motions Tab
    this.renderMotionTemplates(state.resolution_types);
    this.renderProposals(proposals, realm);

    // Plenary Session Callout on Mobile
    this.renderPlenarySessionCallout(meta, proposals, realm);

    // Summit Concluded Personal Evaluation Callout
    this.renderConcludedDebrief(state, realm);

    // Quiz: refresh when a new turn unlocks questions (or on first load for the badge)
    // ...or when a teammate on another phone answered (one attempt per question per nation).
    const answeredCount = (realm.claimed_lore || []).length + (realm.failed_lore || []).length;
    const teammateAnswered = this.quizAnswered !== undefined && answeredCount !== this.quizAnswered;
    this.quizAnswered = answeredCount;
    if ((this.quizTurn !== meta.current_turn || teammateAnswered) && !this.quizLoading) {
      this.quizLoading = true;
      this.loadQuiz().finally(() => { this.quizLoading = false; });
    }
  }

  renderPhaseCard(meta) {
    const phases = {
      working: ['Working session', 'Trade, negotiate, enact decrees and table motions before the bell.'],
      plenary_quick: ['The Assembly votes', 'Vote on every motion at the top of your screen.'],
      grand_plenary_discussion: ['Grand Plenary: debate', 'Argue for or against the motion on the floor. Voting opens soon.'],
      grand_plenary_voting: ['Grand Plenary: vote', 'Cast your vote on the motion at the top of your screen.'],
      turn_summary: ['Between turns', 'The Assembly has spoken. The facilitator will start the next turn.'],
      summit_concluded: ['The summit has ended', 'See how your nation fared below.'],
    };
    const [title, hint] = phases[meta.phase] || phases.working;
    this._setVal('phase-kicker', `Turn ${meta.current_turn} of ${meta.max_turns || 3}`);
    this._setVal('phase-title', title);
    this._setVal('phase-hint', hint);
    const bar = document.getElementById('phase-progress');
    if (bar) {
      const total = meta.turn_timer_total || 0;
      const left = meta.turn_timer_remaining || 0;
      bar.style.width = (meta.phase === 'working' && total > 0) ? `${Math.max(0, Math.min(100, 100 * left / total))}%` : '0%';
    }
  }

  _activeOthers(realms) {
    return (realms || []).filter(r => r.active !== false && r.id !== this.realmId);
  }

  renderTradePartners(realms) {
    const box = document.getElementById('trade-partner-chips');
    const hidden = document.getElementById('trade-receiver');
    if (!box || !hidden) return;
    const others = this._activeOthers(realms);
    if (!others.some(r => r.id === hidden.value)) hidden.value = '';
    const key = others.map(r => r.id).join(',') + '|' + hidden.value;
    if (key === this._partnerKey) return;  // avoid re-rendering every second
    this._partnerKey = key;
    this._realmNames = Object.fromEntries((realms || []).map(r => [r.id, r.name]));
    box.innerHTML = others.length ? others.map(r => `
      <button type="button" class="partner-chip ${r.id === hidden.value ? 'active' : ''}" style="--chip-color:${escapeHtml(r.theme_color || '#8c7a5e')}"
              onclick="realmApp.selectTradePartner('${escapeHtml(r.id)}')">
        <span>${escapeHtml(r.emoji || '🏛️')}</span>${escapeHtml(r.name)}
      </button>`).join('') : '<p class="empty-state">No other nations are playing.</p>';
    this.updateTradePreview();
  }

  selectTradePartner(realmId) {
    document.getElementById('trade-receiver').value = realmId;
    this._partnerKey = null;
    this.renderTradePartners(this._lastRealms || []);
  }

  renderMotionNationOptions(realms) {
    const others = this._activeOthers(realms);
    const playing = (realms || []).filter(r => r.active !== false);
    const key = playing.map(r => r.id).join(',');
    if (key === this._motionNationKey) return;
    this._motionNationKey = key;
    const fill = (id, list, first, label) => {
      const sel = document.getElementById(id);
      if (!sel) return;
      const keep = sel.value;
      sel.innerHTML = `<option value="">${first}</option>` + list.map(r =>
        `<option value="${escapeHtml(r.id)}">${escapeHtml(label(r))}</option>`).join('');
      if (list.some(r => r.id === keep)) sel.value = keep;
    };
    fill('proposal-target-realm', others, 'Any nation', r => `Only ${r.name}`);
    fill('proposal-target-nation', playing, 'Choose a nation…', r => `${r.emoji || ''} ${r.name}`);
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
      newsContainer.innerHTML = '<p class="empty-state">No news of this kind yet.</p>';
      return;
    }

    const icons = { crisis: '⚡', trade: '🤝', assembly: '📜', lore: '📖', turn: '🔔', diplomacy: '🕊️' };
    newsContainer.innerHTML = filtered.map(n => `
      <article class="news-item">
        <span class="news-item-icon">${icons[n.type] || '✦'}</span>
        <div class="grow">
          <div class="news-item-head"><strong>${escapeHtml(n.headline)}</strong><span>${escapeHtml(n.time_str)}</span></div>
          <p>${escapeHtml(n.detail)}</p>
        </div>
      </article>
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

    let verdictColor = '#ef4444';
    let verdictIcon = '🔴';
    if (outcome.continental_verdict === 'STABLE CONTINENT') {
      verdictColor = '#10b981';
      verdictIcon = '🟢';
    } else if (outcome.continental_verdict === 'FRAGILE PEACE') {
      verdictColor = '#f59e0b';
      verdictIcon = '🟡';
    }

    // Public mission HTML
    let pubHtml = '';
    if (myEval.public_mission_eval) {
      const pm = myEval.public_mission_eval;
      pubHtml = `
        <div style="background:var(--bg-surface-sunken); border:1px solid var(--border-subtle); padding:10px; border-radius:var(--radius-xs); margin-bottom:8px;">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <strong style="font-size:0.82rem; color: var(--text-primary);">PUBLIC: ${pm.title}</strong>
            ${pm.achieved ? 
              '<span class="badge" style="background:#10b981; color:#fff; font-weight:800;">✓ ACHIEVED</span>' : 
              '<span class="badge" style="background:#ef4444; color:#fff; font-weight:800;">✗ FAILED</span>'}
          </div>
          <div style="font-size:0.75rem; color:var(--text-secondary); margin-top:2px;">${pm.description}</div>
          <div style="font-size:0.72rem; font-family:var(--font-mono); color:var(--text-muted); margin-top:4px;">${pm.explanation}</div>
        </div>
      `;
    }

    // Secret missions HTML
    let secretsHtml = '';
    if (myEval.secret_missions_eval && myEval.secret_missions_eval.length > 0) {
      secretsHtml = myEval.secret_missions_eval.map((sm, i) => `
        <div style="background:var(--bg-surface-sunken); border:1px solid var(--border-subtle); padding:10px; border-radius:var(--radius-xs); margin-bottom:6px;">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <strong style="font-size:0.82rem; color: var(--text-primary);">SECRET #${i+1}: ${sm.title}</strong>
            ${sm.achieved ? 
              '<span class="badge" style="background:#10b981; color:#fff; font-weight:800;">✓ ACHIEVED</span>' : 
              '<span class="badge" style="background:#ef4444; color:#fff; font-weight:800;">✗ FAILED</span>'}
          </div>
          <div style="font-size:0.75rem; color:#10b981; margin-top:2px; font-weight:600;">${sm.objective}</div>
          <div style="font-size:0.72rem; font-family:var(--font-mono); color:var(--text-muted); margin-top:4px;">${sm.explanation}</div>
        </div>
      `).join('');
    } else {
      secretsHtml = `
        <div style="background:var(--bg-surface-sunken); border:1px solid var(--border-subtle); padding:10px; border-radius:var(--radius-xs); margin-bottom:8px;">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <strong style="font-size:0.82rem;">${myEval.directive_title}</strong>
            ${myEval.directive_achieved ? 
              '<span class="badge" style="background:#10b981; color:#fff; font-weight:800;">✓ ACHIEVED</span>' : 
              '<span class="badge" style="background:#ef4444; color:#fff; font-weight:800;">✗ FAILED</span>'}
          </div>
          <div style="font-size:0.72rem; font-family:var(--font-mono); color:var(--text-muted); margin-top:4px;">${myEval.directive_explanation}</div>
        </div>
      `;
    }

    container.style.display = 'block';
    container.innerHTML = `
      <div class="card" style="border: 2px solid ${verdictColor}; padding: 16px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
          <span class="badge" style="background:var(--text-primary); color:var(--bg-surface); font-weight:800;">SUMMIT CONCLUDED</span>
          <span class="badge" style="font-size:0.75rem; background:${verdictColor}; color:#fff; font-weight:800;">
            ${myEval.success_ratio || ''} MANDATES (${myEval.score} PTS)
          </span>
        </div>

        <h2 style="font-size:1.2rem; font-weight:900; margin-bottom:4px; text-transform:uppercase; color:${verdictColor};">
          ${verdictIcon} ${outcome.continental_verdict}
        </h2>
        <p style="font-size:0.82rem; color:var(--text-secondary); line-height:1.4; margin-bottom:12px;">
          ${outcome.continental_desc}
        </p>

        <div style="font-size:0.72rem; font-family:var(--font-mono); color:var(--text-muted); margin-bottom:6px; text-transform:uppercase; font-weight:700;">
          SOVEREIGN MANDATE EVALUATION:
        </div>
        ${pubHtml}
        ${secretsHtml}

        <p style="font-size:0.82rem; color:var(--text-primary); line-height:1.4; font-style:italic; margin-top:8px;">
          "${myEval.epilogue}"
        </p>
      </div>
    `;
  }

  // ---------------------------------------------------------------------------
  // Spireopedia Quiz (shared question bank; server validates every answer)
  // ---------------------------------------------------------------------------
  async loadQuiz() {
    try {
      const resp = await fetch(`/api/quiz/${encodeURIComponent(this.realmId)}`);
      if (!resp.ok) throw new Error('quiz fetch failed');
      const data = await resp.json();
      this.quizData = data;
      if (this.quizPending) {
        const pend = data.questions.find(q => q.id === this.quizPending.id);
        if (!pend || pend.status !== 'open') {
          this.quizPending = null;
          showToast('A teammate already answered that question for your nation.', 'warning');
        }
      }
      this.quizTurn = data.current_turn;
      this.renderQuiz();
    } catch (err) {
      const c = document.getElementById('quiz-container');
      if (c && !this.quizData) c.innerHTML = '<p class="empty-state">Could not load questions. Check your connection.</p>';
    }
  }

  filterQuiz(filter, btn) {
    this.quizFilter = filter;
    this.quizRecent = new Set();
    document.querySelectorAll('#quiz-filter-row .chip').forEach(b => b.classList.toggle('active', b === btn));
    this.renderQuiz();
  }

  renderQuiz() {
    const container = document.getElementById('quiz-container');
    const data = this.quizData;
    if (!container || !data) return;
    const qs = data.questions;
    const count = s => qs.filter(q => q.status === s).length;
    this._setVal('quiz-stat-correct', count('correct'));
    this._setVal('quiz-stat-wrong', count('failed'));
    this._setVal('quiz-stat-open', count('open'));
    this._setVal('quiz-penalty-label', data.fail_penalty);
    const badge = document.getElementById('nav-quiz-badge');
    if (badge) {
      badge.innerText = count('open');
      badge.style.display = count('open') > 0 ? 'block' : 'none';
    }

    const filter = this.quizFilter || 'open';
    let shown = qs.map((q, i) => ({ q, n: i + 1 }));
    // Keep questions answered in this visit on screen so the result/explanation can be read.
    const recent = this.quizRecent || new Set();
    if (filter === 'open') shown = shown.filter(x => x.q.status === 'open' || recent.has(x.q.id));
    if (filter === 'answered') shown = shown.filter(x => x.q.status === 'correct' || x.q.status === 'failed');

    const sealed = qs.filter(q => q.status === 'sealed');
    let html = '';
    if (shown.length === 0) {
      const msg = filter === 'open'
        ? (sealed.length ? 'All open questions answered. More unlock next turn.' : 'You have answered every question.')
        : 'Nothing here yet.';
      html += `<div class="card"><p class="empty-state">${msg}</p></div>`;
    }
    html += shown.map(({ q, n }) => this._quizCardHtml(q, n)).join('');
    if (filter !== 'answered' && sealed.length && filter !== 'all') {
      const nextTurn = Math.min(...sealed.map(q => q.turn));
      html += `<div class="card quiz-sealed"><p class="empty-state">${sealed.length} more question${sealed.length === 1 ? '' : 's'} unlock from Turn ${nextTurn}.</p></div>`;
    }
    container.innerHTML = html;
  }

  _quizCardHtml(q, n) {
    const esc = escapeHtml;
    const reward = `+${q.reward_amount} ${esc(RESOURCE_SHORT[q.reward_resource] || q.reward_resource)}`;
    const num = `<span class="quiz-num">Q${String(n).padStart(2, '0')} &middot; TURN ${q.turn}</span>`;
    if (q.status === 'sealed') {
      return `<div class="card quiz-card quiz-sealed"><div class="quiz-meta">${num}<span class="status-pill">Unlocks turn ${q.turn}</span></div>
        <p class="quiz-q muted">Sealed until Turn ${q.turn}.</p></div>`;
    }
    const answered = q.status === 'correct' || q.status === 'failed';
    const pending = this.quizPending && this.quizPending.id === q.id ? this.quizPending.idx : null;
    const pill = q.status === 'correct' ? `<span class="status-pill ok">Correct &middot; ${reward}</span>`
      : q.status === 'failed' ? `<span class="status-pill bad">Wrong &middot; locked</span>`
      : `<span class="status-pill open">Reward ${reward}</span>`;
    const opts = q.options.map((opt, idx) => {
      let cls = 'quiz-option';
      if (answered && idx === q.correct_index) cls += ' correct';
      else if (answered && q.status === 'failed' && idx === q.your_index) cls += ' wrong';
      else if (pending === idx) cls += ' selected';
      const key = String.fromCharCode(65 + idx);
      return `<button type="button" class="${cls}" ${answered ? 'disabled' : `onclick="realmApp.selectQuizOption('${esc(q.id)}', ${idx})"`}>
        <span class="opt-key">${key}</span><span>${esc(opt)}</span></button>`;
    }).join('');
    let foot = '';
    if (!answered && pending !== null) {
      foot = `<div class="quiz-confirm">
        <button type="button" class="btn btn-secondary btn-sm" onclick="realmApp.selectQuizOption(null)">Cancel</button>
        <button type="button" class="btn btn-primary btn-sm" onclick="realmApp.submitQuizAnswer('${esc(q.id)}', this)">Lock in ${String.fromCharCode(65 + pending)}</button>
      </div>`;
    }
    if (answered && q.explanation) {
      foot = `<div class="callout ${q.status === 'correct' ? 'ok' : 'danger'} quiz-result">${esc(q.explanation)}
        <a href="#" onclick="realmApp.openArticle('${esc(q.article)}'); return false;" style="text-decoration: underline; white-space: nowrap;">Read article</a></div>`;
    }
    return `<div class="card quiz-card" id="quiz-${esc(q.id)}">
      <div class="quiz-meta">${num}${pill}</div>
      <p class="quiz-q">${esc(q.question)}</p>
      <div class="quiz-options">${opts}</div>${foot}</div>`;
  }

  // ---------------------------------------------------------------------------
  // Spireopedia (Wiki tab): rendered natively inside the console, read-only
  // ---------------------------------------------------------------------------
  async _wikiFetch(path) {
    const resp = await fetch(path);
    const data = await resp.json();
    if (!resp.ok || !data.success) throw new Error(data.message || 'Encyclopedia unavailable');
    return data;
  }

  _wikiShow(html, { nav = true, push = null } = {}) {
    const body = document.getElementById('wiki-body');
    if (!body) return;
    if (push) {
      this.wikiHistory = this.wikiHistory || [];
      if (this.wikiCurrent) this.wikiHistory.push(this.wikiCurrent);
      this.wikiCurrent = push;
    }
    body.innerHTML = html;
    document.getElementById('wiki-nav').style.display = nav ? 'flex' : 'none';
    // Internal article links stay inside the tab.
    body.querySelectorAll('[data-wiki]').forEach(el => el.addEventListener('click', e => {
      e.preventDefault();
      this.openArticle(el.dataset.wiki);
    }));
    body.querySelectorAll('a[data-anchor]').forEach(el => el.addEventListener('click', e => {
      e.preventDefault();
      const target = document.getElementById(el.dataset.anchor);
      if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }));
    window.scrollTo({ top: 0 });
  }

  _wikiList(items) {
    const esc = escapeHtml;
    return `<ul>${items.map(a => `<li><a href="#" data-wiki="${esc(a.slug)}">${esc(a.title)}</a>
      <span class="wk-muted">— ${esc(a.subtitle || '')}</span></li>`).join('')}</ul>`;
  }

  async wikiHome() {
    this.wikiLoaded = true;
    this.wikiHistory = [];
    this.wikiCurrent = { type: 'home' };
    try {
      const data = this.wikiIndex || await this._wikiFetch('/api/wiki');
      this.wikiIndex = data;
      const esc = escapeHtml;
      const cats = data.meta.categories.map(cat => {
        const items = data.articles.filter(a => a.category === cat);
        return items.length ? `<h2>${esc(cat)}</h2>${this._wikiList(items)}` : '';
      }).join('');
      this._wikiShow(`<div class="wk-title">Welcome to the Spireopedia</div>
        <div class="wk-sub">${data.articles.length} articles · current year ${esc(data.meta.current_year)}</div>
        <p>${esc(data.meta.tagline)}. ${esc(data.meta.calendar_note)}</p>
        <p class="wk-muted">The answers to every quiz question are somewhere in these articles.</p>${cats}`, { nav: false });
    } catch (err) {
      this._wikiShow(`<p class="wk-muted">${escapeHtml(err.message)}</p>`, { nav: false });
    }
  }

  async openArticle(slug, { push = true } = {}) {
    if (!slug) return;
    this.wikiLoaded = true;
    this.switchView('view-wiki');
    try {
      const { article: a } = await this._wikiFetch(`/api/wiki/${encodeURIComponent(slug)}`);
      const esc = escapeHtml;
      // Body HTML (lead, sections, infobox values) is escaped and rendered on the server.
      const infobox = `<div class="wk-infobox"><div class="wk-ib-title">${esc(a.title)}</div><table>
        ${a.infobox.map(([k, v]) => `<tr><th>${esc(k)}</th><td>${v}</td></tr>`).join('')}</table></div>`;
      const toc = a.sections.length > 2 ? `<div class="wk-toc"><div class="wk-toc-title">Contents</div><ol>
        ${a.sections.map((s, i) => `<li><a href="#" data-anchor="wk-s${i}">${esc(s.heading)}</a></li>`).join('')}</ol></div>` : '';
      const sections = a.sections.map((s, i) => `<h2 id="wk-s${i}">${esc(s.heading)}</h2>${s.html}`).join('');
      const seeAlso = a.see_also.length ? `<h2>See also</h2>${this._wikiList(a.see_also)}` : '';
      const refs = a.references.length ? `<h2>References</h2><ol class="wk-refs">${a.references.map(r => `<li>${esc(r)}</li>`).join('')}</ol>` : '';
      const links = a.linked_from.length ? `<p class="wk-muted" style="margin-top:16px;"><b>What links here:</b>
        ${a.linked_from.map(l => `<a href="#" data-wiki="${esc(l.slug)}">${esc(l.title)}</a>`).join(' · ')}</p>` : '';
      this._wikiShow(`<div class="wk-title">${esc(a.title)}</div><div class="wk-sub">${esc(a.subtitle || '')}</div>
        ${infobox}${a.lead}${toc}${sections}${seeAlso}${refs}${links}
        <div class="wk-foot">Category: ${esc(a.category)}</div>`, { push: push ? { type: 'article', slug } : null });
    } catch (err) {
      showToast(err.message, 'danger');
    }
  }

  async wikiSearch(e, { push = true } = {}) {
    if (e) e.preventDefault();
    const input = document.getElementById('wiki-search-input');
    const q = (input ? input.value : '').trim();
    if (!q) return this.wikiHome();
    try {
      const data = await this._wikiFetch(`/api/wiki/search?q=${encodeURIComponent(q)}`);
      const esc = escapeHtml;
      this._wikiShow(`<div class="wk-title">Search results</div>
        <div class="wk-sub">${data.results.length} result${data.results.length === 1 ? '' : 's'} for “${esc(q)}”</div>
        ${data.results.length ? this._wikiList(data.results) : '<p>No article matches your search.</p>'}`,
        { push: push ? { type: 'search', q } : null });
    } catch (err) {
      showToast(err.message, 'danger');
    }
  }

  wikiClose() {
    this.switchView(this.viewBeforeWiki || 'view-overview');
  }

  wikiBack() {
    const prev = (this.wikiHistory || []).pop();
    if (!prev || prev.type === 'home') return this.wikiHome();
    this.wikiCurrent = prev;
    if (prev.type === 'article') return this.openArticle(prev.slug, { push: false });
    const input = document.getElementById('wiki-search-input');
    if (input) input.value = prev.q;
    return this.wikiSearch(null, { push: false });
  }

  selectQuizOption(questionId, idx) {
    this.quizPending = questionId ? { id: questionId, idx } : null;
    this.renderQuiz();
  }

  async submitQuizAnswer(questionId, btnEl) {
    if (!this.quizPending || this.quizPending.id !== questionId) return;
    const answerIndex = this.quizPending.idx;
    if (btnEl) { btnEl.disabled = true; btnEl.innerText = 'Checking…'; }
    try {
      const resp = await fetch('/api/lore/quiz', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ realm_id: this.realmId, question_id: questionId, answer_index: answerIndex })
      });
      const res = await resp.json();
      this.quizPending = null;
      if (res.data && res.data.status) {
        // Reflect the result locally (incl. which option this delegation picked), then resync.
        const q = this.quizData.questions.find(x => x.id === questionId);
        if (q) Object.assign(q, { status: res.data.status, correct_index: res.data.correct_index,
                                  explanation: res.data.explanation, your_index: answerIndex });
        (this.quizRecent = this.quizRecent || new Set()).add(questionId);
        this.renderQuiz();
        showToast(res.message, res.success ? 'success' : 'danger');
        res.success ? synth.playChime() : synth.playAlert();
      } else {
        showToast(res.message || 'Answer rejected', 'danger');
        this.loadQuiz();
      }
      this.pollState();
    } catch (err) {
      showToast('Connection failed — your answer was not sent.', 'danger');
      if (btnEl) { btnEl.disabled = false; btnEl.innerText = 'Retry'; }
    }
  }

  renderRegistry(realms) {
    const list = document.getElementById('registry-list');
    if (!list) return;
    const esc = escapeHtml;
    const level = t => ({ LOW: 1, MEDIUM: 2, HIGH: 3 }[t] || 0);
    const pips = (icon, label, tier) => `<span class="pips" title="${label}: ${esc(tier || '?')}">
        <i>${icon}</i>${[1, 2, 3].map(n => `<em class="${n <= level(tier) ? 'on' : ''}"></em>`).join('')}</span>`;
    list.innerHTML = realms.filter(r => r.active !== false).map(r => {
      const mine = r.id === this.realmId;
      return `<div class="nation-card" style="--nc:${esc(r.theme_color || '#8c7a5e')}">
        <div class="nation-card-head">
          <span class="crest small">${esc(r.emoji || '🏛️')}</span>
          <div class="grow"><strong>${esc(r.name)}</strong>${mine ? ' <span class="status-pill open">You</span>' : ''}
            <div class="nation-card-sub">${esc(r.public_mission ? r.public_mission.title : r.ethos || '')}</div></div>
          <span class="vote-seal" title="Assembly votes">${r.assembly_votes}</span>
        </div>
        <div class="nation-card-pips">
          ${pips('🌾', 'Grain', r.grain_tier)}${pips('⚙️', 'Cores', r.cores_tier)}${pips('🧵', 'Silk', r.silk_tier)}${pips('⚔️', 'Military', r.military_tier)}
          ${pips('🤝', 'Standing', r.standing_tier)}${pips('🏛️', 'Stability', r.stability_tier)}
        </div>
        ${r.is_starving ? '<div class="flag bad mt-1">🥀 Starving</div>' : ''}
      </div>`;
    }).join('');
  }

  renderFlags(realm) {
    const container = document.getElementById('status-tags-container');
    if (!container) return;

    let html = '';
    if (realm.is_starving) html += `<span class="flag bad">🥀 Starving</span>`;
    if (realm.complacency_warning) html += `<span class="flag warn">😴 Complacency risk: spend Silk on a Gala</span>`;
    if (realm.is_plutocrat) html += `<span class="flag good">👑 Richest nation: +1 vote</span>`;
    if (realm.tech_efficiency_unlocked) html += `<span class="flag good">✨ Efficient: eats 25% less Grain</span>`;
    if (realm.is_quarantined) html += `<span class="flag bad">🚧 Borders sealed</span>`;
    if (realm.is_striking) html += `<span class="flag bad">✊ Workers on strike</span>`;

    container.innerHTML = html;
  }

  renderTrades(trades, realm) {
    const esc = escapeHtml;
    const res = r => `${RESOURCE_ICONS[r] || ''} ${RESOURCE_SHORT[r] || r}`;
    const incoming = trades.filter(t => t.receiver_id === this.realmId && t.status === 'pending');
    const outgoing = trades.filter(t => t.sender_id === this.realmId && t.status === 'pending');

    const badgeEl = document.getElementById('nav-trade-badge');
    if (badgeEl) {
      badgeEl.innerText = incoming.length;
      badgeEl.style.display = incoming.length ? 'inline-block' : 'none';
    }
    const note = t => t.note ? `<p class="trade-note">“${esc(t.note)}”</p>` : '';

    const incomingContainer = document.getElementById('incoming-trades-list');
    if (incomingContainer) {
      incomingContainer.innerHTML = incoming.length ? incoming.map(t => `
        <div class="offer-card">
          <div class="offer-head"><strong>${esc(t.sender_name)}</strong><span>${esc(t.time_str || '')}</span></div>
          <div class="offer-swap">
            <div><span>You get</span><b>${t.offer_amount} ${esc(res(t.offer_resource))}</b></div>
            <div class="offer-arrow">⇄</div>
            <div><span>You give</span><b>${t.request_amount} ${esc(res(t.request_resource))}</b></div>
          </div>
          ${note(t)}
          <div class="row mt-1">
            <button class="btn btn-primary btn-sm grow" onclick="realmApp.respondTrade('${esc(t.id)}', 'accept')">Accept</button>
            <button class="btn btn-secondary btn-sm grow" onclick="realmApp.respondTrade('${esc(t.id)}', 'decline')">Decline</button>
          </div>
        </div>`).join('') : '<p class="empty-state">No offers waiting for you.</p>';
    }

    const outgoingContainer = document.getElementById('outgoing-trades-list');
    if (outgoingContainer) {
      outgoingContainer.innerHTML = outgoing.length ? outgoing.map(t => `
        <div class="offer-card">
          <div class="offer-head"><strong>To ${esc(t.receiver_name)}</strong><span>Waiting…</span></div>
          <div class="offer-swap">
            <div><span>You give</span><b>${t.offer_amount} ${esc(res(t.offer_resource))}</b></div>
            <div class="offer-arrow">⇄</div>
            <div><span>You get</span><b>${t.request_amount} ${esc(res(t.request_resource))}</b></div>
          </div>
          ${note(t)}
          <button class="btn btn-secondary btn-sm mt-1" onclick="realmApp.respondTrade('${esc(t.id)}', 'cancel')">Withdraw offer</button>
        </div>`).join('') : '<p class="empty-state">You have no open offers.</p>';
    }
  }

  renderProposals(proposals, realm) {
    const esc = escapeHtml;
    const types = this.motionTypes || {};
    const open = proposals.filter(p => p.status === 'draft' || p.status === 'qualified');
    const decided = proposals.filter(p => p.status === 'passed' || p.status === 'rejected');
    const canEndorse = p => !(p.support_list || []).includes(this.realmId)
      && (!p.target_seconder_id || p.target_seconder_id === this.realmId);

    const motionsBadge = document.getElementById('nav-motions-badge');
    if (motionsBadge) {
      const n = open.filter(canEndorse).length;
      motionsBadge.innerText = n;
      motionsBadge.style.display = n > 0 ? 'inline-block' : 'none';
    }

    const effectLine = p => {
      const t = types[p.effect_type] || {};
      const target = p.target_realm_name ? ` <em>(${esc(p.target_realm_name)})</em>` : '';
      return `<div class="motion-effect"><span>If passed:</span> ${esc(t.effect_plain || t.statutory_effect || '')}${target}</div>`;
    };
    const head = (p, pill) => {
      const t = types[p.effect_type] || {};
      return `<div class="row-between" style="align-items:flex-start;">
          <div class="motion-title">${esc(t.icon || '📜')} ${esc(p.title)}</div>${pill}</div>
        <div class="motion-sponsor">Tabled by ${esc(p.proposer_name)} &middot; ${esc(t.name || p.effect_type)}</div>`;
    };

    const container = document.getElementById('pending-motions-list');
    if (container) {
      container.innerHTML = open.length ? open.map(p => {
        const support = p.support_list || [];
        const qualified = support.length >= 2 || p.is_qualified;
        const pill = qualified ? '<span class="status-pill ok">On the ballot</span>'
                               : `<span class="status-pill">${support.length}/2 sponsors</span>`;
        let action;
        if (support.includes(this.realmId)) {
          action = `<span class="section-sub">${p.proposer_id === this.realmId ? 'Your motion' : 'You co-sponsored this'}</span>`;
        } else if (canEndorse(p)) {
          action = `<button class="btn btn-primary btn-block btn-sm" onclick="realmApp.supportProposal('${esc(p.id)}')">Co-sponsor this motion</button>`;
        } else {
          action = `<span class="section-sub">Only ${esc(p.target_seconder_name)} may co-sponsor</span>`;
        }
        const ask = p.target_seconder_id && !qualified
          ? `<div class="callout ${p.target_seconder_id === this.realmId ? 'warn' : 'neutral'} mt-1">${p.target_seconder_id === this.realmId ? 'Your nation has been asked to co-sponsor this.' : `Waiting for ${esc(p.target_seconder_name)} to co-sponsor.`}</div>` : '';
        return `<div class="motion-card">${head(p, pill)}${effectLine(p)}
          <details class="motion-terms"><summary>Read the terms</summary><p>${esc(p.description)}</p></details>
          <div class="motion-sponsor">Sponsors: ${(p.supporters || []).map(s => esc(s.name)).join(', ')}</div>
          ${ask}<div class="mt-1">${action}</div></div>`;
      }).join('') : '<p class="empty-state">No motions on the floor yet. Pick a template above to propose one.</p>';
    }

    const decidedCard = document.getElementById('decided-motions-card');
    const decidedList = document.getElementById('decided-motions-list');
    if (decidedCard && decidedList) {
      decidedCard.style.display = decided.length ? '' : 'none';
      decidedList.innerHTML = decided.map(p => {
        const votes = Object.values(p.votes || {});
        const side = c => votes.filter(v => v.choice === c);
        const sum = c => side(c).reduce((a, v) => a + (v.weight || 1), 0);
        const line = c => side(c).map(v => esc(v.realm_name)).join(', ') || '—';
        const pill = p.status === 'passed' ? '<span class="status-pill ok">Passed</span>' : '<span class="status-pill bad">Rejected</span>';
        return `<div class="motion-card">${head(p, pill)}${effectLine(p)}
          <div class="vote-breakdown">
            <div><b>For</b> ${sum('support')} votes &middot; ${side('support').length} nations<br><span>${line('support')}</span></div>
            <div><b>Against</b> ${sum('oppose')} votes &middot; ${side('oppose').length} nations<br><span>${line('oppose')}</span></div>
            ${side('abstain').length ? `<div><b>Abstained</b><br><span>${line('abstain')}</span></div>` : ''}
          </div></div>`;
      }).join('');
    }
  }

  _motionEffectHtml(p) {
    const t = (this.motionTypes || {})[p.effect_type] || {};
    const target = p.target_realm_name ? ` (${escapeHtml(p.target_realm_name)})` : '';
    const text = t.effect_plain || t.statutory_effect;
    return text ? `<div class="motion-effect"><span>If passed:</span> ${escapeHtml(text)}${target}</div>` : '';
  }

  renderPlenarySessionCallout(meta, proposals, realm) {
    const callout = document.getElementById('plenary-session-callout');
    if (!callout) return;

    const phase = meta.phase;
    // Only show the voting box while the Assembly is actually in session (the debrief has its own card).
    if (phase === 'working' || phase === 'summit_concluded') {
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
              <strong class="motion-title">${escapeHtml(p.title)}</strong>
              ${this._motionEffectHtml(p)}
              <details class="motion-terms" style="margin-bottom:8px;"><summary>Read the terms</summary><p>${escapeHtml(p.description)}</p></details>
              
              ${myVote ? `
                <div class="badge" style="border-color:var(--accent); color:var(--accent);">BALLOT CAST: ${myVote.choice.toUpperCase()} (${myVote.weight} VOTES)</div>
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
            <strong class="motion-title">${escapeHtml(activeProp.title)}</strong>
            <div class="motion-sponsor">Tabled by ${escapeHtml(activeProp.proposer_name)}</div>
            ${this._motionEffectHtml(activeProp)}
            <p style="font-size:0.82rem; color:var(--text-secondary); line-height:1.45; margin-top:8px; white-space:pre-line;">${escapeHtml(activeProp.description)}</p>
            <div style="margin-top:10px; font-size:0.78rem; font-family:var(--font-mono); color: var(--text-primary);">
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
            <strong class="motion-title">${escapeHtml(activeProp.title)}</strong>
            ${this._motionEffectHtml(activeProp)}
            <details class="motion-terms" style="margin-bottom:10px;"><summary>Read the terms</summary><p>${escapeHtml(activeProp.description)}</p></details>
            
            ${myVote ? `
              <div class="badge" style="border-color:var(--accent); color:var(--accent);">BALLOT LOCKED: ${myVote.choice.toUpperCase()} (${myVote.weight} VOTES)</div>
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

    document.querySelectorAll('.res-picker').forEach(picker => {
      picker.addEventListener('click', e => {
        const btn = e.target.closest('button[data-res]');
        if (!btn) return;
        picker.querySelectorAll('button').forEach(b => b.classList.toggle('active', b === btn));
        document.getElementById(picker.dataset.target).value = btn.dataset.res;
        this.updateTradePreview();
      });
    });

    const tradeForm = document.getElementById('trade-form');
    if (tradeForm) {
      tradeForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const receiverId = document.getElementById('trade-receiver').value;
        if (!receiverId) { showToast('First choose a nation to trade with.', 'warning'); return; }
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
            showToast('Offer sent. Tell them to check their Trade tab!', 'success');
            synth.playChime();
            document.getElementById('trade-note').value = '';
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
    val = Math.max(0, Math.min(500, val + delta));
    el.value = val;
    this.updateTradePreview();
  }

  updateTradePreview() {
    const el = document.getElementById('trade-preview-text');
    if (!el) return;
    const partner = document.getElementById('trade-receiver').value;
    const name = (this._realmNames || {})[partner];
    const g = document.getElementById('trade-offer-res').value, ga = document.getElementById('trade-offer-amt').value || 0;
    const r = document.getElementById('trade-req-res').value, ra = document.getElementById('trade-req-amt').value || 0;
    el.innerHTML = name
      ? `You give <b>${escapeHtml(ga)} ${RESOURCE_SHORT[g]}</b> to <b>${escapeHtml(name)}</b> and receive <b>${escapeHtml(ra)} ${RESOURCE_SHORT[r]}</b>.`
      : 'Choose a nation to trade with.';
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

window.RealmApp = RealmApp;
