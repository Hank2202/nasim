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
    if (!(await confirmAction({ title: 'Leave your delegation?', message: 'You return to the lobby. You can join again with the passcode.', confirmLabel: 'Leave' }))) return;
    try {
      await fetch('/api/auth/realm/logout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ realm_id: this.realmId })
      });
    } catch (err) {}
    window.location.href = '/';
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
  // Motions: pick a template, set its numbers, read what will happen, table it
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
        <span class="motion-template-go">Start from this &rsaquo;</span>
      </button>`).join('');
    this.motionTemplatesRendered = true;
  }

  _activeRealms() {
    return (this._lastRealms || []).filter(r => r.active !== false);
  }

  _defaultMotionParams(t) {
    if (t.builder === 'pact') return { lines: [{ kind: 'transfer', resource: 'grain', amount: 10, payers: [], receivers: [] }] };
    return t.defaults ? JSON.parse(JSON.stringify(t.defaults)) : {};
  }

  chooseMotionTemplate(typeId) {
    const form = document.getElementById('proposal-form');
    const gallery = document.getElementById('motion-templates');
    if (!typeId) {
      form.style.display = 'none';
      gallery.style.display = '';
      this.motionDraft = null;
      return;
    }
    const t = (this.motionTypes || {})[typeId];
    if (!t) return;
    this.motionDraft = { type: t, params: this._defaultMotionParams(t), text: [], error: '' };
    document.getElementById('proposal-type').value = t.id;
    document.getElementById('motion-chosen-name').innerText = `${t.icon || ''} ${t.name}`;
    document.getElementById('proposal-title').value = t.default_title || t.name;
    document.getElementById('proposal-desc').value = t.default_terms || t.summary;
    const targetGroup = document.getElementById('proposal-target-nation-group');
    targetGroup.style.display = t.needs_target ? 'block' : 'none';
    document.getElementById('proposal-target-nation').required = !!t.needs_target;
    document.getElementById('proposal-target-nation').value = '';
    document.getElementById('proposal-target-nation-label').innerText = t.target_label || 'Nation';
    gallery.style.display = 'none';
    form.style.display = 'block';
    this.renderMotionParams();
    this.refreshMotionPreview();
    form.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  _nationOptions(selected, extra = []) {
    const esc = escapeHtml;
    const dyn = extra.map(([v, label]) => `<option value="${esc(v)}" ${v === selected ? 'selected' : ''}>${esc(label)}</option>`).join('');
    return dyn + this._activeRealms().map(r =>
      `<option value="${esc(r.id)}" ${r.id === selected ? 'selected' : ''}>${esc(r.emoji || '')} ${esc(r.name)}</option>`).join('');
  }

  renderMotionParams() {
    const box = document.getElementById('motion-params');
    const d = this.motionDraft;
    if (!box || !d) return;
    const t = d.type, p = d.params, esc = escapeHtml;
    const resOptions = (list, sel) => list.map(r => `<option value="${r}" ${r === sel ? 'selected' : ''}>${esc(RESOURCE_SHORT[r] || r)}</option>`).join('');
    const num = (key, label, min, max) => `<label>${label}<input type="number" inputmode="numeric" min="${min}" max="${max}" value="${esc(p[key])}"
        oninput="realmApp.setMotionParam('${key}', this.value)"></label>`;
    if (t.builder === 'redistribute') {
      box.innerHTML = `<div class="param-box"><div class="section-sub" style="margin:0 0 6px;">Set the numbers (they are applied exactly as written)</div>
        <div class="param-grid">
          <label>Resource<select class="form-select" onchange="realmApp.setMotionParam('resource', this.value)">${resOptions(['grain', 'cores', 'silk'], p.resource)}</select></label>
          ${num('above', 'Nations above this give', 10, 150)}${num('give', 'They give up to', 1, 30)}
          ${num('below', 'Nations below this receive', 1, 100)}${num('receive', 'They receive up to', 1, 30)}
        </div></div>`;
    } else if (t.builder === 'levy') {
      const dyn = [['@richest', 'The richest nation'], ['@poorest', 'The poorest nation'], ['@strongest', 'The strongest army'], ['@weakest', 'The weakest army']];
      box.innerHTML = `<div class="param-box"><div class="section-sub" style="margin:0 0 6px;">Who is sanctioned, and what do they lose?</div>
        <div class="param-grid">
          <label>Nation<select class="form-select" onchange="realmApp.setMotionParam('target', this.value)">${this._nationOptions(p.target, dyn)}</select></label>
          <label>Loses<select class="form-select" onchange="realmApp.setMotionParam('resource', this.value)">${resOptions(['grain', 'cores', 'silk', 'military', 'vitality', 'standing', 'stability'], p.resource)}</select></label>
          ${num('amount', 'Amount', 1, 30)}
        </div></div>`;
    } else if (t.builder === 'pact') {
      this._renderPactLines(box);
    } else {
      box.innerHTML = '';
    }
  }

  setMotionParam(key, value) {
    if (!this.motionDraft) return;
    this.motionDraft.params[key] = value === '' ? '' : (isNaN(Number(value)) ? value : Number(value));
    this.refreshMotionPreview();
  }

  // A resource pact: up to three lines, each a transfer (who gives, who receives) or a penalty (who loses).
  _renderPactLines(box) {
    const esc = escapeHtml, lines = this.motionDraft.params.lines;
    const nations = this._activeRealms();
    const chips = (i, key, picked) => `<div class="pick-chips">${[['@all', 'Everyone']].concat(nations.map(r => [r.id, `${r.emoji || ''} ${r.name}`])).map(([id, label]) =>
      `<button type="button" class="pick-chip ${picked.includes(id) ? 'on' : ''}" onclick="realmApp.pactToggle(${i}, '${key}', '${esc(id)}')">${esc(label)}</button>`).join('')}</div>`;
    const resList = kind => kind === 'transfer' ? ['grain', 'cores', 'silk', 'military', 'standing'] : ['grain', 'cores', 'silk', 'military', 'vitality', 'standing', 'stability'];
    box.innerHTML = `<div class="param-box"><div class="section-sub" style="margin:0;">Write your deal, line by line (up to 3). Everything given is shared equally by the receivers; nothing is created.</div>
      ${lines.map((l, i) => `<div class="pact-line">
        <div class="pl-head">
          <select class="form-select" onchange="realmApp.pactSet(${i}, 'kind', this.value)">
            <option value="transfer" ${l.kind === 'transfer' ? 'selected' : ''}>Transfer</option><option value="levy" ${l.kind === 'levy' ? 'selected' : ''}>Penalty</option></select>
          <select class="form-select" onchange="realmApp.pactSet(${i}, 'resource', this.value)">
            ${resList(l.kind).map(r => `<option value="${r}" ${r === l.resource ? 'selected' : ''}>${esc(RESOURCE_SHORT[r])}</option>`).join('')}</select>
          <input type="number" class="form-input" inputmode="numeric" min="1" max="30" value="${esc(l.amount)}" oninput="realmApp.pactSet(${i}, 'amount', this.value, true)" aria-label="Amount">
        </div>
        ${l.kind === 'transfer' ? `<div class="form-label mt-1">Each of these gives up to that amount</div>${chips(i, 'payers', l.payers || [])}
          <div class="form-label mt-1">These share what is collected</div>${chips(i, 'receivers', l.receivers || [])}`
          : `<div class="form-label mt-1">Each of these loses up to that amount</div>${chips(i, 'targets', l.targets || [])}`}
        ${lines.length > 1 ? `<button type="button" class="btn btn-secondary btn-sm mt-1" onclick="realmApp.pactRemove(${i})">Remove this line</button>` : ''}
      </div>`).join('')}
      ${lines.length < 3 ? '<button type="button" class="btn btn-secondary btn-sm mt-2" onclick="realmApp.pactAdd()">+ Add a line</button>' : ''}
    </div>`;
  }

  pactSet(i, key, value, quiet) {
    const line = this.motionDraft.params.lines[i];
    if (key === 'amount') line.amount = value === '' ? '' : Number(value);
    else line[key] = value;
    if (key === 'kind') { line.resource = 'grain'; if (value === 'levy') line.targets = line.targets || []; }
    if (!quiet) this.renderMotionParams();
    this.refreshMotionPreview();
  }

  pactToggle(i, key, id) {
    const line = this.motionDraft.params.lines[i];
    const list = line[key] = line[key] || [];
    const at = list.indexOf(id);
    if (at >= 0) list.splice(at, 1); else list.push(id);
    this.renderMotionParams();
    this.refreshMotionPreview();
  }

  pactAdd() {
    const lines = this.motionDraft.params.lines;
    if (lines.length < 3) lines.push({ kind: 'transfer', resource: 'grain', amount: 10, payers: [], receivers: [] });
    this.renderMotionParams();
    this.refreshMotionPreview();
  }

  pactRemove(i) {
    this.motionDraft.params.lines.splice(i, 1);
    this.renderMotionParams();
    this.refreshMotionPreview();
  }

  _motionBody() {
    const d = this.motionDraft;
    const t = d.type;
    return {
      proposer_id: this.realmId, effect_type: t.id, params: d.params,
      target_realm_id: t.needs_target ? document.getElementById('proposal-target-nation').value : null,
    };
  }

  // The server writes the effect in words, so what a player reads is exactly what the game will do.
  refreshMotionPreview() {
    clearTimeout(this._previewTimer);
    this._previewTimer = setTimeout(async () => {
      const box = document.getElementById('motion-preview');
      const d = this.motionDraft;
      if (!box || !d) return;
      try {
        const res = await (await fetch('/api/proposal/preview', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(this._motionBody())
        })).json();
        if (!this.motionDraft) return;
        d.text = res.success ? res.effect_text : [];
        d.error = res.success ? '' : (res.message || 'This motion is not valid yet.');
        box.style.display = 'block';
        box.className = `preview-box${res.success ? '' : ' error'}`;
        box.innerHTML = res.success
          ? `<b>If passed, the game will:</b><ul>${res.effect_text.map(x => `<li>${escapeHtml(x)}</li>`).join('')}</ul>`
          : escapeHtml(d.error);
      } catch (err) { /* offline for a moment: the next change tries again */ }
    }, 250);
  }

  async handleDraftProposal(e) {
    e.preventDefault();
    const d = this.motionDraft;
    if (!d) return;
    if (d.error) { showToast(d.error, 'warning'); return; }
    const title = document.getElementById('proposal-title').value;
    const ok = await confirmAction({
      title: 'Table this motion?',
      message: `“${title}”\nAnother nation must co-sponsor it before the Assembly votes on it.`,
      details: (d.text && d.text.length ? d.text.map(x => `If passed: ${x}`) : []),
      confirmLabel: 'Table the motion',
    });
    if (!ok) return;
    const body = Object.assign(this._motionBody(), {
      title, description: document.getElementById('proposal-desc').value,
      target_seconder_id: document.getElementById('proposal-target-realm').value || null,
    });
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
    // A new game started (or the server restarted): this login belonged to the old one, so start over.
    const gameId = state.meta && state.meta.game_id;
    if (gameId) {
      if (this.gameId && this.gameId !== gameId) { window.location.reload(); return; }
      this.gameId = gameId;
    }
    const { meta, realms, trades, proposals, news_feed } = state;
    const realm = realms.find(r => r.id === this.realmId);
    this._lastRealms = realms;
    this._proposals = proposals || [];
    this._trades = trades || [];
    this._me = realm;
    this._turn = meta.current_turn;

    // Audio cues
    if (meta.audio_cue && meta.audio_cue.seq !== undefined) {
      if (this.lastAudioSeq !== null && meta.audio_cue.seq > this.lastAudioSeq) {
        if (meta.audio_cue.type === 'gong' || meta.audio_cue.type === 'turn') synth.playGong();
        else if (meta.audio_cue.type === 'chime' || meta.audio_cue.type === 'trade') synth.playChime();
        else if (meta.audio_cue.type === 'alert') synth.playAlert();
        else if (meta.audio_cue.type === 'battle') synth.playBattle();
        if (meta.audio_cue.message) showToast(meta.audio_cue.message, 'info');
      }
      this.lastAudioSeq = meta.audio_cue.seq;
    }

    // Header updates
    const turnElem = document.getElementById('turn-display');
    if (turnElem) turnElem.innerText = `TURN ${meta.current_turn}`;
    const timerElem = document.getElementById('timer-display');
    if (timerElem) {
      timerElem.innerText = formatSeconds(meta.display_timer ? meta.display_timer.seconds : meta.turn_timer_remaining);
      timerElem.title = meta.display_timer ? meta.display_timer.label : '';
    }
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

    // What the people eat at the end of the turn (difficulty setting; a quarter less with technological efficiency)
    const eat = (state.game_settings || {}).grain_consumption;
    if (eat) this._setVal('eat-amount', `${realm.tech_efficiency_unlocked ? Math.round(eat * 0.75) : eat} Grain`);

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

    // Missions follow the roster: targets and stand-in missions change when nations join or leave
    this.renderMissions(realm);

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

    // Quiz: follow a question opened (or answered) on a teammate's phone
    const openId = realm.quiz_active ? realm.quiz_active.question_id : null;
    const answeredCount = (realm.claimed_lore || []).length + (realm.failed_lore || []).length;
    const quizChanged = this._seenQuizOpen !== undefined && (openId !== this._seenQuizOpen || answeredCount !== this._seenQuizAnswered);
    this._seenQuizOpen = openId;
    this._seenQuizAnswered = answeredCount;
    const badge = document.getElementById('nav-quiz-badge');
    if (badge && !this.quiz) { badge.innerText = '!'; badge.style.display = openId ? 'block' : 'none'; }
    const quizVisible = document.getElementById('view-quiz').classList.contains('active');
    if ((quizChanged || (this.quizTurn !== meta.current_turn)) && !this._quizAnswering) {
      this.quizTurn = meta.current_turn;
      if (quizVisible || this.quiz) this.loadQuiz();
    }

    // War: weather, rules, targets and the battles that have been fought
    this.renderWar(state, realm);
    this.watchBattles(state.battles || []);
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
    let [title, hint] = phases[meta.phase] || phases.working;
    if (meta.phase === 'working' && meta.intermission_end) {
      [title, hint] = [`Turn ${meta.current_turn} starts soon`, 'Listen to the facilitator: the news of the new turn is being read out.'];
    }
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

  renderMissions(realm) {
    const secrets = realm.active_secret_missions;
    if (!realm.public_mission || !secrets) return;
    const key = JSON.stringify([realm.public_mission, secrets]);
    if (key === this._missionKey) return;
    this._missionKey = key;
    const esc = escapeHtml;
    this._setVal('realm-public-title', realm.public_mission.title || '');
    this._setVal('realm-public-desc', realm.public_mission.description || '');
    this._setVal('secret-count-label', `🔒 Secret directives (${secrets.length})`);
    const list = document.getElementById('secret-missions-list');
    if (list) list.innerHTML = secrets.map((sm, i) => `
      <div class="secret-item">
        <strong>${i + 1}. ${esc(sm.title)}</strong>
        ${sm.narrative ? `<p>${esc(sm.narrative)}</p>` : ''}
        <div class="secret-goal">${esc(sm.objective)}</div>
      </div>`).join('');
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

    const icons = { crisis: '⚡', trade: '🤝', assembly: '📜', lore: '📖', turn: '🔔', diplomacy: '🕊️', war: '⚔️', boon: '🌟' };
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
            ${myEval.success_ratio || ''} MANDATES (${myEval.score}%)
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
  // Spireopedia Quiz: one question at a time, against the clock. The server owns the clock and the answers.
  // ---------------------------------------------------------------------------
  async loadQuiz() {
    try {
      const resp = await fetch(`/api/quiz/${encodeURIComponent(this.realmId)}`);
      if (!resp.ok) throw new Error('quiz fetch failed');
      const data = await resp.json();
      this.quiz = data;
      if (data.active) {
        if (data.active.seconds_left > 0) {
          if (!this._quizDeadline || this._quizActiveId !== data.active.question_id || !this._quizTimerHandle) {
            this._startQuizCountdown(data.active);
          }
        } else {                                   // out of time: the server settles it a moment after the deadline
          this._stopQuizCountdown();
          this._quizExpiredId = data.active.question_id;
          if (!this._quizRecheck) this._quizRecheck = setTimeout(() => { this._quizRecheck = null; this.loadQuiz(); }, 1000);
        }
        this._quizActiveId = data.active.question_id;
        this.quizResult = null;
      } else {
        this._stopQuizCountdown();
        this._quizActiveId = null;
        // A question that ran out of time (or was answered on a teammate's phone): show how it ended.
        if (!this.quizResult && this._quizExpiredId) {
          this.quizResult = (data.history || []).find(h => h.id === this._quizExpiredId) || null;
        }
        this._quizExpiredId = null;
      }
      this.renderQuiz();
    } catch (err) {
      const c = document.getElementById('quiz-stage');
      if (c && !this.quiz) c.innerHTML = '<p class="empty-state">Could not load the quiz. Check your connection.</p>';
    }
  }

  _startQuizCountdown(active) {
    this._stopQuizCountdown();
    this._quizDeadline = Date.now() + active.seconds_left * 1000;
    this._quizTotal = active.seconds_total * 1000;
    this._quizTimerHandle = setInterval(() => this._quizTick(), 100);
  }

  _stopQuizCountdown() {
    if (this._quizTimerHandle) clearInterval(this._quizTimerHandle);
    this._quizTimerHandle = null;
    this._quizDeadline = null;
  }

  _quizTick() {
    const left = Math.max(0, this._quizDeadline - Date.now());
    const clock = document.getElementById('quiz-clock');
    const fill = document.getElementById('quiz-timer-fill');
    const bar = document.getElementById('quiz-timer');
    if (clock) { clock.innerText = Math.ceil(left / 1000); clock.classList.toggle('low', left <= 5000); }
    if (fill) fill.style.transform = `scaleX(${Math.max(0, Math.min(1, left / this._quizTotal))})`;
    if (bar) bar.classList.toggle('low', left <= 5000);
    if (left <= 0) {
      this._quizExpiredId = this._quizActiveId;
      this._stopQuizCountdown();
      document.querySelectorAll('#quiz-stage .quiz-option').forEach(b => { b.disabled = true; });
      if (clock) clock.innerText = '0';
      setTimeout(() => this.loadQuiz(), 1800);     // the server counts it as wrong a moment after the deadline
    }
  }

  async takeQuizQuestion() {
    // Pressing the button is the choice to start: no extra dialog, but nothing ever starts by itself.
    const q = this.quiz;
    if (!q || !q.next || this._quizStarting) return;
    this._quizStarting = true;
    try {
      const res = await (await fetch('/api/quiz/start', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ realm_id: this.realmId })
      })).json();
      if (!res.success) showToast(res.message, 'danger');
      this.quizResult = null;
      await this.loadQuiz();
    } catch (err) {
      showToast('Could not start the question. Check your connection.', 'danger');
    }
    this._quizStarting = false;
  }

  // After a result: back to the start card (the next stake and topic), where the player chooses to start.
  quizContinue() {
    this.quizResult = null;
    this.renderQuiz();
  }

  async answerQuiz(originalIndex) {
    const active = this.quiz && this.quiz.active;
    if (!active || this._quizAnswering) return;
    this._quizAnswering = true;
    document.querySelectorAll('#quiz-stage .quiz-option').forEach(b => { b.disabled = true; });
    try {
      const res = await (await fetch('/api/lore/quiz', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ realm_id: this.realmId, question_id: active.question_id, answer_index: originalIndex })
      })).json();
      this._stopQuizCountdown();
      this._quizExpiredId = null;
      showToast(res.message, res.success ? 'success' : 'danger');
      res.success ? synth.playChime() : synth.playAlert();
      this.quizResult = null;
      this._quizAnswering = false;
      await this.loadQuiz();
      this.quizResult = ((this.quiz && this.quiz.history) || []).find(h => h.id === active.question_id) || null;
      this.renderQuiz();
      this.pollState();
    } catch (err) {
      this._quizAnswering = false;
      showToast('Connection failed: your answer may not have been sent.', 'danger');
      this.loadQuiz();
    }
  }

  renderQuiz() {
    const stage = document.getElementById('quiz-stage');
    const q = this.quiz;
    if (!stage || !q) return;
    const esc = escapeHtml, label = r => esc(RESOURCE_SHORT[r] || r);
    this._setVal('quiz-stat-correct', q.stats.correct);
    this._setVal('quiz-stat-wrong', q.stats.wrong);
    this._setVal('quiz-stat-open', q.stats.left);
    this._setVal('quiz-seconds-rule', q.seconds);
    const badge = document.getElementById('nav-quiz-badge');
    if (badge) { badge.innerText = '!'; badge.style.display = q.active ? 'block' : 'none'; }

    if (q.active) {
      const a = q.active;
      const key = String.fromCharCode;
      const over = a.seconds_left <= 0;
      stage.innerHTML = `<div class="quiz-live">
        <div class="row-between"><span class="status-pill open">Stake ±${a.stake_amount} ${label(a.stake_resource)}</span><span class="quiz-clock ${over ? 'low' : ''}" id="quiz-clock">${over ? 0 : Math.ceil(a.seconds_left)}</span></div>
        <div class="quiz-timer ${over ? 'low' : ''}" id="quiz-timer"><div id="quiz-timer-fill" style="transform: scaleX(${over ? 0 : a.seconds_left / a.seconds_total});"></div></div>
        <p class="quiz-q">${esc(a.question)}</p>
        <div class="quiz-options">${a.options.map((o, n) => `<button type="button" class="quiz-option" ${over ? 'disabled' : ''} onclick="realmApp.answerQuiz(${o.i})">
          <span class="opt-key">${key(65 + n)}</span><span>${esc(o.text)}</span></button>`).join('')}</div>
        ${over ? '<p class="empty-state mt-1">Time is up…</p>' : ''}
      </div>`;
    } else if (this.quizResult) {
      const h = this.quizResult;
      const good = h.status === 'correct';
      const pill = good ? `<span class="status-pill ok">Correct &middot; +${h.stake_amount} ${label(h.stake_resource)}</span>`
        : `<span class="status-pill bad">${h.status === 'timeout' ? 'Out of time' : 'Wrong'} &middot; −${h.stake_amount} ${label(h.stake_resource)}</span>`;
      stage.innerHTML = `<div class="quiz-card">
        <div class="quiz-meta"><span class="quiz-num">RESULT</span>${pill}</div>
        <p class="quiz-q">${esc(h.question)}</p>
        <div class="quiz-options">${h.options.map((o, i) => {
          let cls = 'quiz-option';
          if (i === h.correct_index) cls += ' correct'; else if (i === h.your_index) cls += ' wrong';
          return `<button type="button" class="${cls}" disabled><span class="opt-key">${String.fromCharCode(65 + i)}</span><span>${esc(o)}</span></button>`;
        }).join('')}</div>
        <div class="callout ${good ? 'ok' : 'danger'} quiz-result">${esc(h.explanation)}
          <a href="#" onclick="realmApp.openArticle('${esc(h.article)}'); return false;" style="text-decoration: underline; white-space: nowrap;">Read the article</a></div>
        ${q.next ? '<button type="button" class="btn btn-primary btn-block mt-2" onclick="realmApp.quizContinue()">Next question</button>'
                 : `<p class="empty-state mt-2">${q.unlocks_turn ? `More questions unlock in Turn ${q.unlocks_turn}.` : 'You have answered every question.'}</p>`}
      </div>`;
    } else if (q.next) {
      stage.innerHTML = `<div class="quiz-start">
        <div class="section-sub" style="margin:0;">Your next question</div>
        <div class="stake">±${q.next.stake_amount} ${label(q.next.stake_resource)}</div>
        <div class="topic">Topic: ${esc(q.next.category)} &middot; ${q.next.tier === 'hard' ? 'a hard one' : 'standard'}</div>
        <p class="small mt-1" style="color: var(--text-secondary);">Right answer: <b>+${q.next.stake_amount} ${label(q.next.stake_resource)}</b>. Wrong answer or no answer: <b>−${q.next.stake_amount} ${label(q.next.stake_resource)}</b>.<br>
          ${q.seconds} seconds on the clock. You only see the question once you start it.</p>
        <button type="button" class="btn btn-primary btn-block mt-2" onclick="realmApp.takeQuizQuestion()">Start the clock</button>
      </div>`;
    } else {
      stage.innerHTML = `<p class="empty-state">${q.unlocks_turn ? `You have answered every question for now. More unlock in Turn ${q.unlocks_turn}.` : 'You have answered every question.'}</p>`;
    }

    const histCard = document.getElementById('quiz-history-card');
    const hist = document.getElementById('quiz-history');
    if (histCard && hist) {
      const items = q.history.filter(h => !(this.quizResult && h.id === this.quizResult.id));
      histCard.style.display = items.length ? '' : 'none';
      hist.innerHTML = items.slice(0, 15).map(h => `<div class="quiz-history-item">
        <div class="row-between"><b>${esc(h.question)}</b><span class="status-pill ${h.status === 'correct' ? 'ok' : 'bad'}">${h.status === 'correct' ? '✓' : h.status === 'timeout' ? '⏱' : '✗'}</span></div>
        <div class="small" style="color: var(--text-secondary);">${h.status === 'correct' ? '' : `Your answer: ${h.your_index === null || h.your_index < 0 ? 'none' : esc(h.options[h.your_index])}. `}Correct: <b>${esc(h.options[h.correct_index])}</b></div>
        <div class="small muted">${esc(h.explanation)}</div></div>`).join('');
    }
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

  // ---------------------------------------------------------------------------
  // War room: weather, scouting report, the attack order, and the battle replay
  // ---------------------------------------------------------------------------
  renderWar(state, realm) {
    const section = document.getElementById('war-section');
    if (!section) return;
    const settings = state.game_settings || {};
    const meta = state.meta;
    section.style.display = settings.attacks_enabled === false ? 'none' : '';
    if (settings.attacks_enabled === false) return;
    const w = meta.weather;
    const box = document.getElementById('war-weather');
    if (box && w && this._weatherKey !== w.id + meta.current_turn) {
      this._weatherKey = w.id + meta.current_turn;
      const icons = { clear: '☀️', rain: '🌧️', fog: '🌫️', storm: '⛈️', heat: '🔥', tailwind: '💨', night: '🌑' };
      box.innerHTML = `<span class="w-icon">${icons[w.id] || '🌤️'}</span><span><b>${escapeHtml(w.name)}</b> this turn. ${escapeHtml(w.text || '')}</span>`;
    }
    const sig = `${meta.current_turn}|${meta.phase}|${meta.intermission_end ? 1 : 0}|${(state.battles || []).length}|${realm.military_power}|${realm.alchemical_grain}|${(state.sieges || []).length}`;
    const now = Date.now();
    if (sig !== this._warSig || now - (this._warAt || 0) > 5000) {
      this._warSig = sig;
      this._warAt = now;
      this.loadWar();
    }
    this.renderWarLog(state.battles || []);
    this.renderSieges(state.sieges || []);
  }

  async loadWar() {
    try {
      const res = await (await fetch(`/api/war/${encodeURIComponent(this.realmId)}`)).json();
      if (!res.success) return;
      this.war = res;
      if (this.warTarget && !(res.targets || []).some(t => t.id === this.warTarget && t.can_attack)) {
        this.warTarget = null;
        this.warPreview = null;
      }
      this.renderWarTargets();
    } catch (err) { /* the next poll tries again */ }
  }

  renderWarTargets() {
    const war = this.war;
    if (!war) return;
    const esc = escapeHtml;
    const status = document.getElementById('war-status');
    const cost = Object.entries(war.cost || {}).map(([r, n]) => `${n} ${RESOURCE_SHORT[r] || r}`).join(', ');
    if (status) {
      status.innerText = war.from_turn > (this._turn || 1)
        ? `Attacks are allowed from Turn ${war.from_turn}.`
        : `You can march ${war.attacks_left} more time${war.attacks_left === 1 ? '' : 's'} this turn. Supplies cost ${cost}; you need at least ${war.min_military} Military.`;
    }
    const chips = document.getElementById('war-targets');
    if (chips) {
      const names = Object.fromEntries((this._lastRealms || []).map(r => [r.id, r]));
      chips.innerHTML = (war.targets || []).map(t => {
        const r = names[t.id] || {};
        return `<button type="button" class="war-chip ${t.id === this.warTarget ? 'active' : ''}" style="--chip-color:${esc(r.theme_color || '#8c7a5e')}"
          ${t.can_attack ? '' : 'disabled'} title="${esc(t.reason || '')}" onclick="realmApp.selectWarTarget('${esc(t.id)}')"><span>${esc(r.emoji || '🏛️')}</span>${esc(t.name)}</button>`;
      }).join('') || '<p class="empty-state">No other nations are playing.</p>';
      const blocked = (war.targets || []).filter(t => !t.can_attack);
      if (blocked.length && blocked.length === (war.targets || []).length) {
        chips.insertAdjacentHTML('beforeend', `<p class="section-sub" style="width:100%;">${esc(blocked[0].reason)}</p>`);
      }
    }
    this.renderWarScout();
  }

  async selectWarTarget(id) {
    this.warTarget = id;
    this.warPreview = null;
    this.renderWarTargets();
    try {
      const res = await (await fetch('/api/war/preview', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ realm_id: this.realmId, target_id: id })
      })).json();
      if (this.warTarget !== id) return;
      this.warPreview = res.preview || null;
      if (!res.success) showToast(res.message, 'warning');
    } catch (err) { showToast('The scouts could not report. Try again.', 'danger'); }
    this.renderWarScout();
  }

  renderWarScout() {
    const box = document.getElementById('war-scout');
    if (!box) return;
    const p = this.warPreview, esc = escapeHtml;
    if (!this.warTarget || !p) {
      box.innerHTML = '';
      this._setWarButtons(null);
      return;
    }
    const m = p.modes || {};
    const oddsClass = l => (/favourable/i.test(l) && !/un/i.test(l) ? 'good' : (/Unfavourable|Very unfavourable/.test(l) ? 'bad' : 'even'));
    const way = (key, title) => m[key] ? `<div class="way-card ${m[key].can_attack ? '' : 'off'}">
        <div class="way-title">${title}</div>
        <div class="scout-odds ${oddsClass(m[key].label)}">${esc(m[key].label)}</div>
        <p class="small">${esc(m[key].summary)}</p>${m[key].can_attack ? '' : `<p class="small warn">${esc(m[key].reason)}</p>`}</div>` : '';
    box.innerHTML = `<div class="scout-box">
      <div class="scout-note">Your scouts' guess against ${esc(p.defender_name)}. It can be wrong, and chance still decides part of the fight.</div>
      <div class="way-grid mt-1">${way('siege', '🏰 Siege')}${way('surprise', '🗡️ Surprise attack')}</div>
      <div class="mt-1">Your army: <b>${esc(p.own_military)} Military</b>. Their Military: <b>${esc(p.defender_military_tier || '?')}</b>.</div>
      <div class="mt-1"><b>What your scouts could find out</b> <span class="muted">(${esc(p.quality)}; ${p.modifiers.length} of ${esc(p.total)} modifiers revealed)</span>
        ${this._modifierRows(p.modifiers, p.attacker_name, p.defender_name)}
        <div class="section-sub" style="margin:4px 0 0;">More wealth reveals more modifiers; more Silk and Cores make them more accurate.</div></div>
      <div class="mt-1">Ground: <b>${esc((p.terrain || {}).name || '')}</b>. ${esc((p.terrain || {}).note || '')}</div>
      <div>Weather: <b>${esc((p.weather || {}).name || '')}</b>. ${esc((p.weather || {}).text || '')}</div>
    </div>`;
    this._setWarButtons(p);
  }

  _setWarButtons(p) {
    const siege = document.getElementById('war-siege-btn'), quick = document.getElementById('war-surprise-btn');
    if (!siege || !quick) return;
    if (!p) {
      siege.disabled = quick.disabled = true;
      siege.innerText = this.warTarget ? 'The scouts are riding…' : 'Choose a target';
      quick.innerText = 'Surprise attack';
      return;
    }
    const m = p.modes || {};
    siege.disabled = !(m.siege && m.siege.can_attack);
    quick.disabled = !(m.surprise && m.surprise.can_attack);
    siege.innerText = m.siege && m.siege.can_attack ? `Lay siege to ${p.defender_name}` : (p.reason || 'You cannot attack now');
    quick.innerText = m.surprise && m.surprise.can_attack ? 'Surprise attack now' : 'Surprise attack (not possible)';
  }

  async attackTarget(mode) {
    const p = this.warPreview, id = this.warTarget;
    const info = p && p.modes && p.modes[mode];
    if (!p || !id || !info || !info.can_attack) return;
    const cost = Object.entries(info.cost || {}).map(([r, n]) => `${n} ${RESOURCE_SHORT[r] || r}`).join(', ');
    const siege = mode === 'siege';
    const ok = await confirmAction({
      title: siege ? `Lay siege to ${p.defender_name}?` : `Attack ${p.defender_name} by surprise?`,
      message: `Odds, as your scouts see them: ${info.label}.`,
      details: siege ? [
        `The march is announced to everyone, and ${p.defender_name} is warned at once`,
        `Your army arrives after ${Math.floor(info.seconds / 60)}:${String(info.seconds % 60).padStart(2, '0')} of working time; the battle is fought then, with the numbers of that moment`,
        `Supplies for the march, paid now: ${cost}`,
        'You lose Standing for starting a war, win or lose',
      ] : [
        'The battle is fought at once and nobody is warned',
        `Supplies for the march: ${cost}`,
        `Heavy price for the attacker: ${Object.entries(info.penalty || {}).map(([r, n]) => `${Math.abs(n)} ${RESOURCE_SHORT[r] || r}`).join(' and ')} extra, on top of the usual loss of Standing`,
        'Both armies lose soldiers; the loser also loses Stability and Vitality, and the winner takes part of its Grain, Cores and Silk',
      ],
      confirmLabel: siege ? 'Send the army' : 'Strike now', tone: 'danger',
    });
    if (!ok) return;
    try {
      const res = await (await fetch('/api/war/attack', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ realm_id: this.realmId, target_id: id, mode })
      })).json();
      if (!res.success) { showToast(res.message, 'danger'); this.loadWar(); return; }
      this.warTarget = null;
      this.warPreview = null;
      if (res.siege) {
        (this._seenSieges = this._seenSieges || new Set()).add(res.siege.id);
        showToast(`Your army is on the road to ${res.siege.defender_name}. It arrives in ${Math.floor(res.siege.eta / 60)}:${String(res.siege.eta % 60).padStart(2, '0')}.`, 'success');
      } else {
        (this._seenBattles = this._seenBattles || new Set()).add(res.battle.id);
        this.showBattleModal(res.battle);
      }
      this.pollState();
      this.loadWar();
    } catch (err) {
      showToast('The order did not reach the army. Check your connection.', 'danger');
    }
  }

  // Armies on the road are announced to everyone; the nation under siege gets an alarm.
  renderSieges(sieges) {
    const box = document.getElementById('war-sieges');
    const esc = escapeHtml;
    const clock = s => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
    if (box) {
      box.innerHTML = (sieges || []).map(s => {
        const mineUnder = s.defender_id === this.realmId, mineMarching = s.attacker_id === this.realmId;
        return `<div class="siege-row ${mineUnder ? 'danger' : ''}" style="--nc:${esc(s.attacker_color || '#8c7a5e')}">
          <span>${mineUnder ? '⚠️' : '🏰'} <b>${esc(s.attacker_emoji)} ${esc(s.attacker_name)}</b> marches on <b>${esc(s.defender_emoji)} ${esc(s.defender_name)}</b></span>
          <b class="siege-eta">${clock(s.eta)}</b>
          ${mineUnder ? '<em>Prepare: trade for Grain, steady your people, raise your army.</em>' : (mineMarching ? '<em>Your army</em>' : '')}</div>`;
      }).join('');
    }
    if (this._seenSieges === undefined) { this._seenSieges = new Set((sieges || []).map(s => s.id)); return; }
    for (const s of sieges || []) {
      if (this._seenSieges.has(s.id)) continue;
      this._seenSieges.add(s.id);
      if (s.defender_id === this.realmId) { showToast(`⚠️ ${s.attacker_name} is marching on you! They arrive in ${clock(s.eta)}.`, 'danger'); synth.playAlert(); }
      else if (s.attacker_id !== this.realmId) showToast(`🏰 ${s.attacker_name} marches on ${s.defender_name} (${clock(s.eta)})`, 'info');
    }
  }

  renderWarLog(battles) {
    const box = document.getElementById('war-log');
    if (!box) return;
    const key = battles.map(b => b.id).join(',');
    if (key === this._warLogKey) return;
    this._warLogKey = key;
    this._battleById = Object.fromEntries(battles.map(b => [b.id, b]));
    const esc = escapeHtml;
    box.innerHTML = battles.slice(0, 4).map(b => `<div class="battle-row">
      <div><b>${esc(b.attacker_emoji)} ${esc(b.attacker_name)} ⚔️ ${esc(b.defender_emoji)} ${esc(b.defender_name)}</b>
        <span class="muted">Turn ${esc(b.turn)} · ${esc(BattleScene.outcome(b).text)}</span></div>
      <button type="button" class="btn btn-secondary btn-sm" onclick="realmApp.replayBattle('${esc(b.id)}')">Replay</button></div>`).join('');
  }

  replayBattle(id) {
    const b = (this._battleById || {})[id];
    if (b) this.showBattleModal(b);
  }

  watchBattles(battles) {
    if (this._seenBattles === undefined) {                       // first poll: do not replay old battles
      this._seenBattles = new Set(battles.map(b => b.id));
      return;
    }
    for (const b of battles.slice().reverse()) {
      if (this._seenBattles.has(b.id)) continue;
      this._seenBattles.add(b.id);
      if (b.attacker_id === this.realmId || b.defender_id === this.realmId) this.showBattleModal(b);
      else showToast(`⚔️ ${b.headline}`, 'info');
    }
  }

  // The modifiers a nation's scouts could find out, as the scouts reported them (figures are estimates).
  _modifierRows(list, ownName, enemyName) {
    const esc = escapeHtml;
    if (!list || !list.length) return '<div class="section-sub">Your scouts learned nothing.</div>';
    return list.map(m => `<div class="bs-factor"><span>${esc(m.whose === 'own' ? ownName : enemyName)} · ${esc(m.label)}</span>
      <b class="${m.dir === 'pos' ? 'pos' : 'neg'}">${esc(m.text)}</b></div>`).join('');
  }

  _battleExtraHtml(b) {
    const mine = b.private && b.private.mine;
    if (!mine) return '';
    const esc = escapeHtml;
    const changes = Object.entries(mine.changes || {}).map(([r, n]) => `${n > 0 ? '+' : '−'}${Math.abs(n)} ${RESOURCE_SHORT[r] || r}`).join(', ') || 'no change';
    const you = b.private.side === 'attacker';
    const [own, enemy] = you ? [b.attacker_name, b.defender_name] : [b.defender_name, b.attacker_name];
    return `<div class="bs-modal-extra"><b>How it went for you (${you ? 'attacking' : 'defending'})</b>
      <div class="mt-1"><b>Your nation's changes:</b> ${esc(changes)}</div>
      <div class="mt-1"><b>What your scouts made of it</b> <span class="muted">(${esc(mine.quality)}; ${mine.modifiers.length} of ${esc(mine.total)} modifiers known)</span>
        ${this._modifierRows(mine.modifiers, own, enemy)}</div></div>`;
  }

  showBattleModal(b) {
    document.querySelectorAll('.bs-modal').forEach(m => m.remove());
    if (this._battleScene) this._battleScene.stop();
    const overlay = document.createElement('div');
    overlay.className = 'bs-modal';
    overlay.innerHTML = `<div class="bs-modal-card"><div class="bs-stage"></div>${this._battleExtraHtml(b)}
      <button type="button" class="btn btn-primary btn-block mt-2" id="bs-close">Close</button></div>`;
    document.body.appendChild(overlay);
    this._battleScene = BattleScene.play(overlay.querySelector('.bs-stage'), b, {});
    const close = () => { if (this._battleScene) this._battleScene.stop(); overlay.remove(); };
    overlay.querySelector('#bs-close').addEventListener('click', close);
    overlay.addEventListener('click', e => { if (e.target === overlay) close(); });
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
    if (realm.is_plutocrat) html += `<span class="flag good">👑 Richest nation: +1 vote</span>`;
    if (realm.tech_efficiency_unlocked) html += `<span class="flag good">✨ Efficient: eats 25% less Grain</span>`;
    if (realm.is_quarantined) html += `<span class="flag good">🛡️ Cordon: shielded from plague & surges</span>`;
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

    const effectLine = p => this._motionEffectHtml(p);
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
        const count = p.support_count ?? support.length;
        const qualified = count >= 2 || p.is_qualified;
        const pill = qualified ? '<span class="status-pill ok">On the ballot</span>'
                               : '<span class="status-pill">Needs a co-sponsor</span>';
        let action;
        if (support.includes(this.realmId)) {
          action = `<span class="section-sub">${p.proposer_id === this.realmId ? 'Your motion' : 'You co-sponsored this'}</span>`;
        } else if (canEndorse(p)) {
          action = `<button class="btn btn-primary btn-block btn-sm" onclick="realmApp.supportProposal('${esc(p.id)}')">Co-sponsor this motion</button>`;
        } else {
          action = `<span class="section-sub">Addressed to another nation</span>`;
        }
        const ask = p.target_seconder_id && !qualified
          ? `<div class="callout ${p.target_seconder_id === this.realmId ? 'warn' : 'neutral'} mt-1">${p.target_seconder_id === this.realmId ? 'Your nation has been asked to co-sponsor this.' : `Waiting for ${esc(p.target_seconder_name)} to co-sponsor.`}</div>` : '';
        return `<div class="motion-card">${head(p, pill)}${effectLine(p)}
          <details class="motion-terms"><summary>Read the terms</summary><p>${esc(p.description)}</p></details>
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
        const answer = p.effect_type === 'gm_question' && p.status === 'passed'
          ? (p.answer ? `<div class="callout ok mt-1"><b>Game masters' answer:</b> ${esc(p.answer)}</div>`
                      : '<div class="callout neutral mt-1">Waiting for the game masters to answer.</div>')
          : p.effect_type === 'open' && p.status === 'passed' && p.awaiting_gm ? '<div class="callout neutral mt-1">Waiting for the game masters to carry it out.</div>' : '';
        return `<div class="motion-card">${head(p, pill)}${effectLine(p)}${answer}
          <div class="vote-breakdown">
            <div><b>For</b> ${sum('support')} votes &middot; ${side('support').length} nations<br><span>${line('support')}</span></div>
            <div><b>Against</b> ${sum('oppose')} votes &middot; ${side('oppose').length} nations<br><span>${line('oppose')}</span></div>
            ${side('abstain').length ? `<div><b>Abstained</b><br><span>${line('abstain')}</span></div>` : ''}
          </div></div>`;
      }).join('');
    }
  }

  // What the game does if the motion passes: the sentences written when it was tabled (and, once decided, what really happened).
  _motionEffectHtml(p) {
    const esc = escapeHtml;
    const t = (this.motionTypes || {})[p.effect_type] || {};
    const lines = (p.effect_text && p.effect_text.length) ? p.effect_text : [t.effect_plain || t.statutory_effect].filter(Boolean);
    if (!lines.length) return '';
    const body = lines.length === 1 ? ` ${esc(lines[0])}` : `<ul>${lines.map(x => `<li>${esc(x)}</li>`).join('')}</ul>`;
    const done = p.result_text && p.effect_type !== 'gm_question' && !p.awaiting_gm ? `<div class="motion-effect"><span>Carried out:</span> ${esc(p.result_text)}</div>` : '';
    return `<div class="motion-effect"><span>If passed:</span>${body}</div>${done}`;
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
        const partner = (this._realmNames || {})[receiverId] || 'this nation';
        const ok = await confirmAction({
          title: `Send this offer to ${partner}?`,
          details: [`You give: ${offerAmt} ${RESOURCE_SHORT[offerRes]}`, `You ask for: ${reqAmt} ${RESOURCE_SHORT[reqRes]}`, ...(note ? [`Message: “${note}”`] : [])],
          message: 'Nothing moves until they accept.',
          confirmLabel: 'Send the offer',
        });
        if (!ok) return;

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
    if (action !== 'cancel') {
      const t = (this._trades || []).find(x => x.id === tradeId);
      const res = r => RESOURCE_SHORT[r] || r;
      const details = t ? (t.receiver_id === this.realmId
        ? [`You receive: ${t.offer_amount} ${res(t.offer_resource)}`, `You give: ${t.request_amount} ${res(t.request_resource)}`]
        : []) : [];
      const ok = await confirmAction({
        title: action === 'accept' ? `Accept the offer from ${t ? t.sender_name : 'this nation'}?` : `Decline the offer from ${t ? t.sender_name : 'this nation'}?`,
        message: action === 'accept' ? 'The exchange happens at once and cannot be undone.' : '',
        details: action === 'accept' ? details : [],
        confirmLabel: action === 'accept' ? 'Accept the trade' : 'Decline', tone: action === 'accept' ? undefined : 'danger',
      });
      if (!ok) return;
    }
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
    const prop = (this._proposals || []).find(p => p.id === propId) || {};
    const ok = await confirmAction({
      title: 'Co-sponsor this motion?',
      message: prop.title ? `“${prop.title}”` : '',
      details: ['It can then go to the Assembly vote.', "Your nation's name stays hidden from the other nations."].concat(
        ((prop.effect_text || []).map(x => `If passed: ${x}`))),
      confirmLabel: 'Co-sponsor',
    });
    if (!ok) return;
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
    const prop = (this._proposals || []).find(p => p.id === propId) || {};
    const votes = this._me ? this._me.assembly_votes : 1;
    const ok = await confirmAction({
      title: `Vote ${choice.toUpperCase()}?`,
      message: prop.title ? `“${prop.title}”` : '',
      details: choice === 'abstain' ? ['You do not take a side. Your votes are not counted for or against.', 'A ballot cannot be changed once cast.']
        : [`Your nation's ${votes} vote${votes === 1 ? '' : 's'} count ${choice === 'support' ? 'for' : 'against'} the motion.`, 'A ballot cannot be changed once cast.'],
      confirmLabel: `Cast ${choice} vote`, tone: choice === 'oppose' ? 'danger' : undefined,
    });
    if (!ok) return;
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

  async executeDomesticAction(actionType, btn) {
    const d = (btn && btn.dataset) || {};
    const ok = await confirmAction({
      title: `Enact “${d.name || 'this decree'}”?`,
      details: [d.cost ? `Cost: ${d.cost}` : '', d.gain ? `Gain: ${d.gain}` : ''].filter(Boolean),
      confirmLabel: 'Enact the decree',
    });
    if (!ok) return;
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
