/**
 * The Summit of Realms - facilitator's command deck (AdminApp)
 */
'use strict';

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
    setInterval(() => { const tab = document.getElementById('tab-resources'); if (tab && tab.classList.contains('active')) { this.loadModifiers(false); this.loadJournal(); } }, 5000);
    this.loadCatalogEvents();
    this.bindEvents();
    // A reload (or a link to one tab) comes back to the same tab.
    const fromAddress = () => { if (document.getElementById(location.hash.slice(1))) this.showTab(location.hash.slice(1)); };
    fromAddress();
    window.addEventListener('hashchange', fromAddress);
  }

  showTab(tabId) {
    document.querySelectorAll('.admin-tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === tabId));
    document.querySelectorAll('.admin-tab-content').forEach(c => c.classList.toggle('active', c.id === tabId));
    if (tabId === 'tab-resources') { this.loadModifiers(true); this.loadJournal(); }
    if (tabId === 'tab-saves') this.refreshSaves();
    try { history.replaceState(null, '', `#${tabId}`); } catch (e) { /* only the address bar */ }
  }

  async loadCatalogEvents() {
    try {
      const resp = await fetch('/api/events');
      const data = await resp.json();
      const select = document.getElementById('catalog-event-select');
      if (select && data.events) {
        select.innerHTML = data.events.map(e => `
          <option value="${escapeHtml(e.id)}">[T${escapeHtml(e.turn_recommended)}] ${escapeHtml(e.headline)} (${escapeHtml(e.category)})</option>
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
      connectionWatch.ok();
      this.renderState(state);
    } catch (err) {
      connectionWatch.failed();
      console.warn('Admin polling error:', err);
    } finally {
      this.isPolling = false;
    }
  }

  renderState(state) {
    const { meta, realms, proposals, news_feed } = state;
    const settings = state.game_settings || {};
    const rules = settings.rules || {};
    // The page is built for one kind of game; if the complexity changed before play began, build it again.
    if (this._complexity && this._complexity !== rules.id) { window.location.reload(); return; }
    this._complexity = rules.id;
    this._rules = rules;
    this._settings = settings;
    this._meta = meta;
    this._maxTurns = settings.max_turns || 3;
    this._realms = realms;
    this._proposals = proposals;
    this._saveStatus = state.save_status || {};

    // A copy in this browser at every step of the game, and from the moment the game starts.
    const step = `${meta.current_turn}|${meta.phase}|${this._saveStatus.in_progress}`;
    if (this._gameStep !== undefined && this._gameStep !== step) this.keepBrowserCopy();
    this._gameStep = step;

    this.renderNow(state);
    this.renderAutosaveChip();
    this.renderResumeBanner(state.interrupted_game);
    this.renderSeats(realms, state.pins_are_default);
    this.renderRoster(realms);
    this.renderRunTimeline(meta);

    this._text('admin-mode-pill', `${rules.name} · ${settings.scenario_name}`);
    this._text('pregame-game', `${rules.name}, ${settings.scenario_name}`);
    this._text('admin-grain-rule', `${settings.grain_consumption} Grain`);
    const weather = meta.weather;
    this._text('admin-weather', weather && rules.war !== false
      ? `Weather this turn: ${weather.name}. ${settings.attacks_enabled === false ? 'Attacks are switched off.' : `Attacks unlock in Turn ${settings.attacks_from_turn || 2}.`}` : '');

    // The clock console follows whichever clock the current phase has
    const clock = meta.display_timer || { label: 'Clock', seconds: 0, running: false };
    this._text('clock-label', clock.label);
    this._text('clock-big', formatSeconds(clock.seconds));
    const big = document.getElementById('clock-big');
    if (big) big.classList.toggle('stopped', !clock.running);
    const stateEl = document.getElementById('clock-state');
    if (stateEl) { stateEl.innerText = clock.running ? 'running' : 'stopped'; stateEl.classList.toggle('run', !!clock.running); }

    // Every nation's numbers (type a number and press Enter, or use - and +)
    this.renderBulkNations(realms);
    this.renderBulkPreview();
    const tableBody = document.getElementById('admin-realms-tbody');
    if (tableBody && !tableBody.contains(document.activeElement)) {       // never rebuild while someone is typing
      const cols = [['alchemical_grain', 'Grain'], ['aether_cores', 'Cores'], ['echo_silk', 'Silk'], ['military_power', 'Military'],
                    ['public_vitality', 'Vitality'], ['diplomatic_standing', 'Standing'], ['civil_stability', 'Stability']]
        .filter(([field]) => !(rules.hide_vitality && field === 'public_vitality'));
      const esc = escapeHtml;
      const html = realms.filter(r => r.active !== false).map(r => `
        <tr>
          <th scope="row">
            <div class="numbers-nation"><span>${esc(r.emoji || '')} ${esc(r.name)}</span>
              ${r.is_plutocrat ? '<span class="flag good">Richest</span>' : ''}
              ${r.is_starving ? '<span class="flag bad">Starving</span>' : ''}</div>
            ${rules.quiz === false ? '' : `<div class="section-sub" title="Spireopedia quiz: correct / wrong">Quiz ${(r.claimed_lore || []).length} ✓ · ${(r.failed_lore || []).length} ✗</div>`}
          </th>
          ${cols.map(([field, label]) => `<td>
            <div class="inline-num-ctrl">
              <button class="inline-num-btn" aria-label="5 less" onclick="adminApp.adjustStat('${esc(r.id)}', '${field}', -5)">−</button>
              <input type="number" class="inline-num-input" value="${r[field] ?? 0}" data-realm="${esc(r.id)}" data-field="${field}" data-label="${label}" data-name="${esc(r.name)}"
                     data-old="${r[field] ?? 0}" min="0" ${['public_vitality', 'diplomatic_standing', 'civil_stability'].includes(field) ? 'max="100"' : ''}
                     onchange="adminApp.setStatTyped(this)" onkeydown="if (event.key === 'Enter') { event.preventDefault(); this.blur(); }" aria-label="${esc(r.name)} ${label}">
              <button class="inline-num-btn" aria-label="5 more" onclick="adminApp.adjustStat('${esc(r.id)}', '${field}', 5)">+</button>
            </div></td>`).join('')}
          <td class="numbers-votes">${r.assembly_votes}</td>
        </tr>`).join('');
      if (html !== this._tableHtml) { this._tableHtml = html; tableBody.innerHTML = html; }
    }

    // Motions: what waits for the facilitator, then all of them
    this.renderQuestionInbox(proposals);
    this.renderMotionList(state);

    // Players and passcodes
    this.renderPasscodes(realms);

    this.renderWarLog(state.battles || [], settings);
    this.renderSieges(state.sieges || []);

    // The news so far
    const newsBox = document.getElementById('admin-news-feed');
    if (newsBox && news_feed) {
      setHtml(newsBox, news_feed.slice(0, 15).map(n => `
        <article class="admin-news-item">
          <div class="row-between"><strong>${escapeHtml(n.headline)}</strong><span class="section-sub">${escapeHtml(n.time_str)}</span></div>
          <p>${escapeHtml(n.detail)}</p>
        </article>
      `).join(''));
    }
  }

  // ---------------------------------------------------------------------------
  // Now: what is going on, what happens next, and the buttons for it. The one place to look during a game.
  // ---------------------------------------------------------------------------
  renderNow(state) {
    const { meta, realms, proposals } = state;
    const settings = state.game_settings || {}, rules = settings.rules || {};
    const turn = meta.current_turn, last = turn >= this._maxTurns;
    const esc = escapeHtml;
    const auto = settings.auto_advance !== false;
    const playing = realms.filter(r => r.active !== false);
    const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;
    const ballot = proposals.filter(p => ['draft', 'qualified'].includes(p.status) && ((p.support_list || []).length >= 2 || p.is_qualified));
    const clock = meta.display_timer || { label: 'Clock', seconds: 0, running: false };

    const btn = (label, js, kind = 'secondary', id = '', disabled = false) =>
      `<button type="button" ${id ? `id="${id}" ` : ''}class="btn btn-${kind}" onclick="${js}"${disabled ? ' disabled' : ''}>${label}</button>`;
    const convene = kind => btn('Convene the Assembly', 'adminApp.startPlenary()', kind);
    const endTurn = kind => btn(last ? 'End the summit' : 'End this turn', 'adminApp.advanceTurn()', kind, 'btn-end-turn-header');
    const clockBtn = () => clock.running ? btn('⏸ Pause', "adminApp.clockAction('pause')") : btn('▶ Resume', "adminApp.clockAction('resume')", 'primary');
    // Who still has to vote on what is on the floor now.
    const waitingForVotes = motions => {
      const missing = playing.filter(r => motions.some(p => !(p.votes || {})[r.id]));
      return missing.length ? `${playing.length - missing.length} of ${playing.length} nations have voted. Waiting for ${missing.map(r => r.name).join(', ')}.`
                            : 'All nations have voted. You can settle the vote now.';
    };

    let title, text = '', tone = '', buttons = [];
    if (meta.phase === 'working') {
      const voteName = last && rules.grand_plenary ? 'the Grand Plenary debates and votes on' : 'the Assembly votes on';
      const afterwards = ballot.length ? `${voteName} ${plural(ballot.length, 'motion')}`
        : `${last ? 'the summit ends' : 'the turn ends'}, because no motion is on the ballot yet`;
      const next = auto ? `When the clock runs out, ${afterwards}.` : `When the clock runs out a bell rings, and you move on from here.`;
      const minutes = Math.round((meta.turn_timer_total || 0) / 60);
      const stage = clockStage(meta);
      if (stage === 'ready' && turn === 1) {
        const seats = playing.reduce((sum, r) => sum + (r.player_count || 0), 0);
        const taken = playing.reduce((sum, r) => sum + (r.connected_players || 0), 0);
        title = 'Ready to start';
        text = `Nothing is running yet. ${taken} of ${plural(seats, 'seat')} taken. When everyone is in, start the ${minutes}-minute working session.`;
        tone = 'ready';
        buttons = [btn('▶ Start Turn 1', "adminApp.clockAction('resume')", 'primary', 'now-start')];
        if (ballot.length) buttons.push(convene('secondary'));
      } else if (stage === 'ready') {
        title = `Turn ${turn} is ready`;
        text = `The ${minutes}-minute clock is waiting for you. Phones say the turn is about to begin.`;
        tone = 'ready';
        buttons = [btn(`▶ Start Turn ${turn}`, "adminApp.clockAction('resume')", 'primary', 'now-start')];
        if (ballot.length) buttons.push(convene('secondary'));
        buttons.push(endTurn('secondary'));
      } else if (stage === 'intermission') {
        title = `Turn ${turn} starts in a moment`;
        text = 'A short pause, so the news of the new turn can be read out. Then the clock starts by itself.';
        tone = 'ready';
        buttons = [btn('Start now', "adminApp.clockAction('resume')", 'primary'), btn('Wait for me', "adminApp.clockAction('pause')")];
      } else if (stage === 'running') {
        title = 'Working session';
        text = `Nations talk, trade and table motions. ${next}`;
        buttons = [btn('⏸ Pause', "adminApp.clockAction('pause')")];
        if (ballot.length) buttons.push(convene('primary'));
        buttons.push(endTurn('secondary'));
      } else if (stage === 'paused') {
        title = 'Paused';
        text = `The clock is stopped on every screen. ${next}`;
        tone = 'paused';
        buttons = [btn('▶ Resume', "adminApp.clockAction('resume')", 'primary')];
        if (ballot.length) buttons.push(convene('secondary'));
        buttons.push(endTurn('secondary'));
      } else {
        title = 'Time is up';
        text = ballot.length ? `${plural(ballot.length, 'motion')} on the ballot.` : 'No motion is on the ballot.';
        tone = 'ready';
        buttons = ballot.length ? [convene('primary'), endTurn('secondary')] : [endTurn('primary')];
      }
    } else if (meta.phase === 'plenary_quick') {
      const motions = proposals.filter(p => (meta.plenary_docket || []).includes(p.id));
      title = last ? 'The final vote' : 'The Assembly is voting';
      text = `${plural(motions.length, 'motion')} on the ballot. ${waitingForVotes(motions)}${auto ? ' When the clock runs out the votes are counted.' : ''}`;
      tone = 'vote';
      buttons = [clockBtn(), btn('Settle the vote', 'adminApp.concludeQuickPlenary()', clock.running ? 'primary' : 'secondary')];
    } else if (meta.phase === 'grand_plenary_discussion' || meta.phase === 'grand_plenary_voting') {
      const docket = meta.plenary_docket || [], idx = meta.current_motion_index || 0;
      const motion = proposals.find(p => p.id === docket[idx]);
      const voting = meta.phase === 'grand_plenary_voting';
      title = `Grand Plenary: ${voting ? 'vote' : 'debate'} on motion ${idx + 1} of ${docket.length}`;
      text = motion ? `“${esc(motion.title)}”. ` : '';
      text += voting ? waitingForVotes(motion ? [motion] : []) : 'Delegates argue for or against it out loud. When the clock runs out, voting opens.';
      tone = 'vote';
      buttons = voting ? [clockBtn(), btn('Settle this motion and go on', 'adminApp.nextGrandMotion()', 'primary')]
                       : [clockBtn(), btn('Call the vote now', 'adminApp.callGrandVote()', 'primary')];
    } else if (meta.phase === 'turn_summary') {
      title = 'The vote is over';
      text = last ? 'Nations eat one last time when you end the summit, and the results go on the projector.' : `Next: nations eat, and Turn ${turn + 1} is prepared.`;
      tone = 'ready';
      buttons = last ? [btn('End the summit and show the results', 'adminApp.concludeSummit()', 'primary')]
                     : [btn(`Go to Turn ${turn + 1}`, 'adminApp.advanceTurn()', 'primary')];
    } else if (meta.phase === 'summit_concluded') {
      const total = (state.reflection_questions || []).length;
      const step = meta.reflection_step;
      const reflecting = step !== null && step !== undefined;
      const results = btn('Results report', 'adminApp.downloadReport()');
      tone = 'over';
      if (reflecting) {
        title = `Reflection: question ${step + 1} of ${total}`;
        text = 'The question is on the projector.';
        buttons = [btn('Next question &rarr;', `adminApp.setReflection(${step + 1})`, 'primary', '', step >= total - 1),
                   btn('&larr; Previous', `adminApp.setReflection(${step - 1})`, 'secondary', '', step === 0),
                   btn('Show the results', 'adminApp.setReflection(null)'), results];
      } else {
        const verdict = state.summit_outcome ? state.summit_outcome.continental_verdict : '';
        title = 'The summit is over';
        text = `${verdict ? `Verdict: ${esc(verdict)}. ` : ''}The results are on the projector. Talk it through with the ${total} reflection questions.`;
        buttons = [btn(`Start reflection (${total} questions)`, 'adminApp.setReflection(0)', 'primary'), results,
                   '<a class="btn btn-secondary" href="/admin/setup">New summit…</a>'];
      }
    }

    this._text('admin-turn-display', meta.phase === 'summit_concluded' ? 'The end' : `Turn ${turn} of ${this._maxTurns}`);
    this._text('admin-phase-display', title);
    setHtml(document.getElementById('now-text'), text);
    setHtml(document.getElementById('admin-plenary-controls'), buttons.join(''));
    const panel = document.getElementById('now-panel');
    if (panel) panel.dataset.tone = tone;

    // The clock in the panel: how long, and whether it is running at all
    const freeAndIdle = clock.kind === 'free' && !clock.running && !clock.seconds;
    this._text('admin-timer-display', freeAndIdle ? '--:--' : formatSeconds(clock.seconds));
    this._text('now-clock-label', freeAndIdle ? 'No clock running' : `${clock.label} · ${clock.running ? 'running' : 'stopped'}`);
    const shown = document.getElementById('admin-timer-display');
    if (shown) shown.classList.toggle('stopped', !clock.running);
    const nudges = document.getElementById('now-nudges');
    if (nudges) nudges.style.display = freeAndIdle ? 'none' : '';

    // What needs attention somewhere else on the deck
    const alerts = [];
    const toAnswer = proposals.filter(p => p.status === 'passed' && (p.effect_type === 'open' ? p.awaiting_gm : (p.effect_type === 'gm_question' && !p.answer)));
    if (toAnswer.length) alerts.push(`<button type="button" class="now-alert" onclick="adminApp.showTab('tab-resolutions')">${plural(toAnswer.length, 'passed motion')} waiting for you &rarr;</button>`);
    for (const s of state.sieges || []) {
      alerts.push(`<button type="button" class="now-alert war" onclick="adminApp.showTab('tab-events')">🏰 ${esc(s.attacker_name)} marches on ${esc(s.defender_name)} &rarr;</button>`);
    }
    setHtml(document.getElementById('now-alerts'), alerts.join(''));
  }

  // Before the game: who has joined, with the passcodes at hand. During it: who is connected.
  renderSeats(realms, pinsAreDefault) {
    const playing = realms.filter(r => r.active !== false);
    const started = !!(this._saveStatus && this._saveStatus.in_progress);
    const show = (id, on) => { const el = document.getElementById(id); if (el) el.style.display = on ? '' : 'none'; };
    show('pregame-card', !started);
    show('seats-card', started);
    show('pregame-pins-note', !started && !!pinsAreDefault);
    const esc = escapeHtml;
    const seats = r => `${r.connected_players || 0} of ${r.player_count} seat${r.player_count === 1 ? '' : 's'}`;
    const css = r => ((r.connected_players || 0) >= r.player_count ? 'full' : (r.connected_players ? 'some' : 'none'));
    const taken = playing.reduce((sum, r) => sum + (r.connected_players || 0), 0);
    const total = playing.reduce((sum, r) => sum + (r.player_count || 0), 0);
    this._text('seats-count', `· ${taken} of ${total} seats`);
    setHtml(document.getElementById('pregame-seats'), playing.map(r => `<tr>
        <td>${esc(r.emoji || '')} <b>${esc(r.name)}</b></td>
        <td class="seat-count ${css(r)}">${esc(seats(r))}</td>
        <td class="seat-pin"><span class="section-sub">Passcode</span> <b class="mono">${esc(r.pin || '')}</b></td>
      </tr>`).join(''));
    setHtml(document.getElementById('seat-strip'), playing.map(r => `<span class="seat-chip ${css(r)}" style="--nc:${esc(r.theme_color || '#8c7a5e')}" title="${esc(r.name)}">
        <span class="seat-emoji">${esc(r.emoji || '')}</span><span class="seat-name">${esc(r.name)}</span><b>${r.connected_players || 0}/${r.player_count}</b></span>`).join(''));
  }

  // The whole game in one line, with "you are here".
  renderRunTimeline(meta) {
    const box = document.getElementById('run-timeline');
    if (!box) return;
    const grand = !this._rules || this._rules.grand_plenary !== false;
    const steps = [];
    for (let t = 1; t <= this._maxTurns; t++) {
      steps.push({ key: `turn-${t}`, label: `Turn ${t}` });
      steps.push({ key: `vote-${t}`, label: t === this._maxTurns && grand ? 'Grand Plenary' : 'Vote' });
    }
    steps.push({ key: 'end', label: 'Results' });
    const voting = ['plenary_quick', 'grand_plenary_discussion', 'grand_plenary_voting', 'turn_summary'].includes(meta.phase);
    const current = meta.phase === 'summit_concluded' ? 'end' : `${voting ? 'vote' : 'turn'}-${meta.current_turn}`;
    const at = steps.findIndex(s => s.key === current);
    setHtml(box, steps.map((s, i) => `<span class="run-step ${i < at ? 'done' : ''} ${i === at ? 'now' : ''}">${s.label}</span>`).join(''));
  }

  renderMotionList(state) {
    const resList = document.getElementById('admin-resolutions-list');
    const types = Object.fromEntries((state.resolution_types || []).map(t => [t.id, t]));
    const esc = escapeHtml;
    const tplBox = document.getElementById('admin-motion-templates');
    if (tplBox && !this._templatesShown && (state.resolution_types || []).length) {
      this._templatesShown = true;
      tplBox.innerHTML = state.resolution_types.map(t => `
        <div class="inset">
          <div class="row-between"><b>${esc(t.icon || '📜')} ${esc(t.name)}</b>
            <span class="section-sub" style="margin:0;">${t.player_selectable ? 'players can table it' : 'tabled by the game in Turn 3'}${t.needs_target ? ' · needs a target nation' : ''}</span></div>
          <p class="small" style="margin-top:4px;">${esc(t.summary || '')}</p>
          <div class="motion-effect mt-1"><span>If passed:</span> ${esc(t.effect_plain || t.statutory_effect || '')}</div>
        </div>`).join('');
    }
    if (!resList) return;
    const pill = p => {
      if (p.status === 'passed') return '<span class="status-pill ok">Passed</span>';
      if (p.status === 'rejected') return '<span class="status-pill bad">Rejected</span>';
      const backers = (p.support_list || []).length;
      return backers >= 2 || p.is_qualified ? '<span class="status-pill open">On the ballot</span>' : '<span class="status-pill">Needs a co-sponsor</span>';
    };
    setHtml(resList, state.proposals.length ? state.proposals.map(p => {
      const t = types[p.effect_type] || {};
      const cosponsors = (p.supporters || []).filter(x => x.id !== p.proposer_id).map(x => esc(x.name)).join(', ');
      const decided = p.status === 'passed' || p.status === 'rejected';
      const tallies = p.tallies || {};
      return `<div class="motion-card">
          <div class="row-between" style="align-items:flex-start;"><strong class="motion-title">${esc(t.icon || '📜')} ${esc(p.title)}</strong>${pill(p)}</div>
          <div class="motion-sponsor">${esc(t.name || p.effect_type)} · tabled by ${esc(p.proposer_name)}${cosponsors ? ` · co-sponsored by ${cosponsors}` : ''}</div>
          ${p.description ? `<details class="motion-terms"><summary>Read the terms</summary><p>${esc(p.description)}</p></details>` : ''}
          ${this._effectBlock(p, t)}
          ${p.answer ? `<div class="callout ok mt-1"><b>Game masters' answer:</b> ${esc(p.answer)}</div>` : ''}
          ${decided || tallies.total_cast ? `<div class="motion-tally">For ${tallies.support_weight || 0} · Against ${tallies.oppose_weight || 0} · Abstained ${tallies.abstain_weight || 0}</div>` : ''}
        </div>`;
    }).join('') : '<p class="empty-state">No motions yet.</p>');
  }

  // Nations, seats and passcodes. Not rebuilt while someone is typing a passcode or has a list open.
  renderPasscodes(realms) {
    const body = document.getElementById('admin-pins-tbody');
    if (!body || body.contains(document.activeElement)) return;
    const esc = escapeHtml;
    setHtml(body, realms.map(r => {
      const active = r.active !== false;
      const seats = r.player_count || 1;
      return `<tr class="${active ? '' : 'not-playing'}">
        <td>${esc(r.emoji || '🏛️')} <b>${esc(r.name)}</b>${active ? '' : ' <span class="muted small">not playing</span>'}</td>
        <td class="seat-count ${(r.connected_players || 0) >= seats ? 'full' : ''}">${r.connected_players || 0} of ${seats}
          ${r.connected_players ? `<button class="btn btn-secondary btn-sm seat-free" onclick="adminApp.clearRealmSessions('${esc(r.id)}', ${esc(JSON.stringify(r.name))})" title="Free this nation's seats, for instance when a phone was lost">Free</button>` : ''}</td>
        <td><select class="form-select seat-select" aria-label="Seats of ${esc(r.name)}" onchange="adminApp.setPlayerCount('${esc(r.id)}', this.value, this)">
          ${[1, 2, 3, 4, 5, 6].map(n => `<option value="${n}" ${n === seats ? 'selected' : ''}>${n}</option>`).join('')}</select></td>
        <td>${(r.active_secret_missions || []).length}</td>
        <td><input type="text" class="form-input pin-input" inputmode="numeric" maxlength="8" value="${esc(r.pin || '')}" aria-label="Passcode of ${esc(r.name)}"
                   onchange="adminApp.setPin('${esc(r.id)}', this)" onkeydown="if (event.key === 'Enter') this.blur();"></td>
      </tr>`;
    }).join(''));
  }

  async setPin(realmId, input) {
    const res = await (await fetch('/api/admin/pin/reset', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ realm_id: realmId, pin: input.value.trim() }),
    })).json();
    showToast(res.message, res.success ? 'success' : 'danger');
    if (!res.success) input.value = input.defaultValue;
    this.pollState();
  }

  async shufflePins() {
    if (!(await confirmAction({ title: 'Give every nation a new passcode?', message: 'Phones already in the game stay in. New phones need the new code, and printed cards no longer work.', confirmLabel: 'Shuffle passcodes' }))) return;
    const res = await (await fetch('/api/admin/pins/shuffle', { method: 'POST' })).json();
    showToast(res.message, res.success ? 'success' : 'danger');
    this.pollState();
  }

  bindEvents() {
    document.querySelectorAll('.admin-tab-btn').forEach(btn => btn.addEventListener('click', () => this.showTab(btn.dataset.tab)));
  }

  // ---------------------------------------------------------------------------
  // Clock console: one set of controls for whichever clock the current phase has
  // ---------------------------------------------------------------------------
  async _clock(action, value) {
    try {
      const res = await (await fetch('/api/admin/clock', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action, value })
      })).json();
      showToast(res.message, res.success ? 'info' : 'danger');
      this.pollState();
    } catch (err) {
      showToast('The clock did not answer. Try again.', 'danger');
    }
  }

  async clockSet() {
    const mins = parseInt(document.getElementById('clock-min').value || 0, 10) || 0;
    const secs = parseInt(document.getElementById('clock-sec').value || 0, 10) || 0;
    const total = Math.max(0, mins * 60 + secs);
    const label = (document.getElementById('clock-label') || {}).innerText || 'the clock';
    if (!(await confirmAction({ title: `Set ${label.toLowerCase()} to ${formatSeconds(total)}?`, confirmLabel: 'Set the time' }))) return;
    this._clock('set', total);
  }

  clockAdjust(delta) {
    this._clock('adjust', delta);
  }

  async clockAction(action) {
    const label = (document.getElementById('clock-label') || {}).innerText || 'the clock';
    if (action === 'reset' && !(await confirmAction({ title: `Reset ${label.toLowerCase()}?`, message: 'It goes back to the length chosen on the setup screen.', confirmLabel: 'Reset' }))) return;
    this._clock(action);
  }

  // Motions on the ballot that would not be voted on if the turn ended now (they wait for the next vote).
  _ballotCount() {
    return (this._proposals || []).filter(p => ['draft', 'qualified'].includes(p.status) && ((p.support_list || []).length >= 2 || p.is_qualified)).length;
  }

  async advanceTurn() {
    // The last turn ends with the results, not with another turn.
    if (this._meta && this._meta.current_turn >= this._maxTurns) return this.concludeSummit();
    const waiting = this._meta && this._meta.phase === 'working' ? this._ballotCount() : 0;
    const note = waiting ? ` ${waiting} motion${waiting === 1 ? '' : 's'} on the ballot wait${waiting === 1 ? 's' : ''} for the next vote.` : '';
    if (!(await confirmAction({ title: 'End this turn?', message: `Nations eat, the storyline moves on and the next turn is prepared.${note}`, confirmLabel: 'End the turn' }))) return;
    try {
      const resp = await fetch('/api/admin/turn/next', { method: 'POST' });
      const res = await resp.json();
      if (res.success) {
        showToast(`Turn ${res.result.new_turn} is ready. Start its clock when you like.`, 'info');
        synth.playGong();
        this.pollState();
      } else {
        showToast(res.message, 'danger');
      }
    } catch (err) {
      showToast('Turn processing failed', 'danger');
    }
  }

  async handleBroadcastNews(e) {
    e.preventDefault();
    if (!(await confirmAction({ title: 'Send this to everyone?', message: document.getElementById('admin-news-headline').value, confirmLabel: 'Send' }))) return;
    const headline = document.getElementById('admin-news-headline').value;
    const detail = document.getElementById('admin-news-detail').value;
    try {
      await fetch('/api/admin/news/broadcast', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ headline, detail, type: 'crisis' })
      });
      showToast('Sent to everyone', 'info');
      synth.playAlert();
      document.getElementById('admin-news-form').reset();
      this.pollState();
    } catch (err) {
      showToast('Sending failed. Try again.', 'danger');
    }
  }

  async startPlenary() {
    if (!(await confirmAction({ title: 'Convene the Assembly?', message: 'Every motion with two sponsors goes to the vote. Motions tabled from now on wait for the next turn.', confirmLabel: 'Convene' }))) return;
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
    if (!(await confirmAction({ title: 'Settle the Assembly vote?', message: 'Votes are counted now. Motions that passed take effect at once.', confirmLabel: 'Settle the vote' }))) return;
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

  async callGrandVote() {
    if (!(await confirmAction({ title: 'Call the vote now?', message: 'The debate ends and the nations cast their votes.', confirmLabel: 'Call the vote' }))) return;
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
    if (!(await confirmAction({ title: 'Settle this motion and move on?', message: 'Its vote is counted and, if it passed, carried out.', confirmLabel: 'Settle and continue' }))) return;
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
    if (!(await confirmAction({ title: 'Start the crisis the game recommends next?', message: 'It is announced to everyone and applied at once.', confirmLabel: 'Start it', tone: 'danger' }))) return;
    try {
      const resp = await fetch('/api/admin/event/auto', { method: 'POST' });
      const res = await resp.json();
      if (res.success) {
        showToast(`Crisis started: ${res.event.headline}`, 'info');
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
    const sel = document.getElementById('catalog-event-select');
    if (!sel || !sel.value) return;
    if (!(await confirmAction({ title: 'Start this crisis?', message: sel.options[sel.selectedIndex].text, confirmLabel: 'Start it', tone: 'danger' }))) return;
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
        showToast('Crisis started', 'info');
        synth.playAlert();
        this.pollState();
      } else {
        showToast(res.message, 'danger');
      }
    } catch (err) {
      showToast('Failed to trigger crisis', 'danger');
    }
  }

  async minorEvent(tone) {
    if (!(await confirmAction({ title: tone === 'good' ? 'Post good news?' : tone === 'bad' ? 'Post bad news?' : 'Post a news item?', message: 'A random nation is affected at once.', confirmLabel: 'Post it' }))) return;
    const res = await (await fetch('/api/admin/event/minor', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ tone })
    })).json();
    showToast(res.message, res.success ? 'info' : 'danger');
    this.pollState();
  }

  async largeEvent() {
    if (!(await confirmAction({ title: 'Strike a nation with a disaster?', message: 'A random large disaster hits one nation at once.', confirmLabel: 'Strike', tone: 'danger' }))) return;
    const res = await (await fetch('/api/admin/event/large', { method: 'POST' })).json();
    showToast(res.message, res.success ? 'info' : 'danger');
    this.pollState();
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

  async triggerRoomAudio(cueType, message) {
    try {
      await fetch('/api/admin/chime', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: cueType, message })
      });
      showToast('Sound sent to the room', 'info');
    } catch (err) {
      showToast('Audio trigger failed', 'danger');
    }
  }

  async concludeSummit() {
    const waiting = this._meta && this._meta.phase === 'working' ? this._ballotCount() : 0;
    const note = waiting ? ` ${waiting} motion${waiting === 1 ? '' : 's'} on the ballot will not be voted on.` : '';
    if (!(await confirmAction({ title: 'End the summit?', message: `Nations eat one last time, and the results go on the projector. After this, trades, motions and the quiz are closed.${note}`, confirmLabel: 'End the summit', tone: 'danger' }))) return;
    try {
      const resp = await fetch('/api/admin/summit/conclude', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      const res = await resp.json();
      if (res.success) {
        showToast('The summit is over. The results are on the projector.', 'info');
        synth.playGong();
        this.pollState();
      } else {
        showToast(res.message, 'danger');
      }
    } catch (err) {
      showToast('Failed to conclude summit', 'danger');
    }
  }

  renderRoster(realms) {
    const box = document.getElementById('roster-chips');
    if (!box) return;
    const playing = realms.filter(r => r.active !== false).length;
    const count = document.getElementById('roster-count');
    if (count) count.innerText = `· ${playing} of ${realms.length} playing`;
    const key = realms.map(r => `${r.id}:${r.active !== false}`).join(',');
    if (key === this._rosterKey) return;
    this._rosterKey = key;
    box.innerHTML = realms.map(r => {
      const on = r.active !== false;
      return `<button type="button" class="roster-chip ${on ? 'on' : ''}" style="--nc:${escapeHtml(r.theme_color || '#8c7a5e')}"
          onclick="adminApp.toggleRealm('${escapeHtml(r.id)}', ${on})" title="${on ? 'Take out of' : 'Bring into'} this summit">
          <span class="crest small">${escapeHtml(r.emoji || '🏛️')}</span>
          <span><b>${escapeHtml(r.name)}</b><em>${on ? 'Playing' : 'Not playing'}</em></span>
        </button>`;
    }).join('');
  }

  // ---------------------------------------------------------------------------
  // Saves: server autosaves + copies in this browser (survive a server restart)
  // ---------------------------------------------------------------------------
  initSaves() {
    this.refreshSaves();
    this.keepBrowserCopy();
    setInterval(() => this.keepBrowserCopy(), 60 * 1000);       // nothing is stored unless the game has moved on
    setInterval(() => this.refreshSaves(), 60 * 1000);
  }

  _browserSaves() {
    if (!this._browserList) {                                   // parsed once: this list can be megabytes long
      try { this._browserList = JSON.parse(localStorage.getItem('summit_saves') || '[]'); } catch (e) { this._browserList = []; }
      for (const s of this._browserList) if (s.game_id === undefined) s.game_id = ((s.snapshot || {}).meta || {}).game_id || '';
    }
    return this._browserList;
  }

  // Oldest copies go first if the browser runs out of room; if not even the newest fits, the facilitator is told.
  _storeBrowserSaves(saves) {
    let list = saves;
    while (list.length) {
      try {
        localStorage.setItem('summit_saves', JSON.stringify(list));
        this._browserList = list;
        this._browserSaveFailed = false;
        return;
      } catch (e) { list = list.slice(0, -1); }
    }
    this._browserSaveFailed = true;
  }

  // The newest copy is refreshed every minute, and one copy is kept for good every five minutes.
  // A game nobody has started is not worth a copy: above all it must never push out the game a server restart interrupted.
  async keepBrowserCopy(label) {
    try {
      const res = await (await fetch('/api/admin/save/export')).json();
      if (!res.success || (!res.in_progress && !label)) return;
      const meta = res.snapshot.meta || {};
      const gameId = meta.game_id || '';
      const text = JSON.stringify(res.snapshot);
      if (!label && text === this._lastCopyText) return;        // nothing has happened since the last copy
      this._lastCopyText = text;
      const now = Date.now() / 1000;
      let saves = this._browserSaves().slice();
      const newest = saves[0];
      const refresh = !label && newest && newest.game_id === gameId && !newest.manual && now - newest.first < 300;
      const entry = { created: now, first: refresh ? newest.first : now, game_id: gameId, turn: meta.current_turn || 1, manual: !!label,
                      in_progress: !!res.in_progress, label: label || `Turn ${meta.current_turn || 1}, ${(meta.phase || 'working').replace(/_/g, ' ')}`, snapshot: res.snapshot };
      saves = refresh ? [entry, ...saves.slice(1)] : [entry, ...saves];
      // Five copies of this game, and the newest copy of up to two earlier games.
      const mine = saves.filter(s => s.game_id === gameId).slice(0, 5);
      const others = [];
      for (const s of saves) if (s.game_id !== gameId && others.length < 2 && !others.some(o => o.game_id === s.game_id)) others.push(s);
      this._storeBrowserSaves(mine.concat(others));
      this._browserCopyAt = now;
      this.renderBrowserSaves();
    } catch (e) { /* offline for a moment: try again next time */ }
  }

  async refreshSaves() {
    try {
      const res = await (await fetch('/api/admin/saves')).json();
      const box = document.getElementById('server-saves');
      if (!box || !res.success) return;
      this._serverSaves = res.saves;
      setHtml(box, res.saves.length ? res.saves.map(s => this._saveRow(s.label, s.created, s.game_id === res.game_id,
        `adminApp.restoreServerSave(${s.id})`, `adminApp.downloadSave(${s.id})`)).join('')
        : '<p class="empty-state">No saves yet. The first one is made a few minutes after the game starts.</p>');
    } catch (e) { /* the next refresh tries again */ }
    this.renderBrowserSaves();
    this.renderSaveStatus();
  }

  renderBrowserSaves() {
    const box = document.getElementById('browser-saves');
    if (!box) return;
    const saves = this._browserSaves();
    const game = (this._saveStatus || {}).game_id;
    setHtml(box, saves.length ? saves.map((s, i) => this._saveRow(s.label, s.created, s.game_id === game,
      `adminApp.restoreBrowserSave(${i})`, null)).join('') : '<p class="empty-state">None yet. A copy is made as soon as the game starts.</p>');
    this.renderSaveStatus();
  }

  _saveRow(label, created, thisGame, restoreJs, downloadJs) {
    const when = new Date(created * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    return `<div class="inset save-row"><div class="grow"><b>${escapeHtml(label)}</b>
        <div class="section-sub" style="margin:0;">${when}, ${timeAgo(created)}${thisGame ? '' : ' · an earlier game'}</div></div>
      <div class="row">${downloadJs ? `<button class="btn btn-secondary btn-sm" onclick="${downloadJs}">Download</button>` : ''}
      <button class="btn btn-secondary btn-sm" onclick="${restoreJs}">Restore</button></div></div>`;
  }

  // The reassurance that it works, in the header of every tab. It also says so if it does not.
  renderAutosaveChip() {
    const chip = document.getElementById('autosave-chip');
    const status = this._saveStatus;
    if (!chip || !status) return;
    const newest = Math.max(status.last_at || 0, this._browserCopyAt || 0);
    let text = '✓ Saved', tone = '';
    if (status.error) [text, tone] = ['⚠ Autosave failed', 'bad'];
    else if (!status.in_progress) [text, tone] = ['Saves start with the game', 'idle'];
    else if (newest) text = `✓ Saved ${timeAgo(newest)}`;
    else [text, tone] = ['Saves within 5 minutes', 'idle'];
    this._text('autosave-chip', text);
    chip.dataset.tone = tone;
    if (document.getElementById('tab-saves').classList.contains('active')) this.renderSaveStatus();
  }

  renderSaveStatus() {
    const el = document.getElementById('save-status');
    const status = this._saveStatus || {};
    if (!el) return;
    const parts = [];
    if (status.error) parts.push(`⚠ The last autosave failed: ${status.error}. Download a save file to be safe.`);
    if (!status.in_progress) parts.push('The game has not started yet, so there is nothing to save.');
    else {
      parts.push(status.last_at ? `Last saved on the server ${timeAgo(status.last_at)}.` : 'The first save on the server comes within 5 minutes.');
      if (this._browserCopyAt) parts.push(`Last copy in this browser ${timeAgo(this._browserCopyAt)}.`);
    }
    if (this._browserSaveFailed) parts.push('⚠ This browser has no room for a copy: use Download a save file.');
    setHtml(el, escapeHtml(parts.join(' ')));
  }

  // After a server restart: offer the interrupted game back, first thing. A wiped hosted server no longer has it, but this browser may.
  renderResumeBanner(offer) {
    const box = document.getElementById('resume-banner');
    if (!box) return;
    const status = this._saveStatus || {};
    let copy = null;
    if (!offer && !status.in_progress) {
      let dismissed = 0;
      try { dismissed = Number(localStorage.getItem('summit_resume_dismissed')) || 0; } catch (e) { /* offered again next time */ }
      const age = s => Date.now() / 1000 - s.created;
      copy = this._browserSaves().find(s => s.in_progress && s.game_id && s.game_id !== status.game_id && age(s) < 24 * 3600 && s.created > dismissed) || null;
    }
    if (!offer && !copy) { box.style.display = 'none'; return; }
    box.style.display = '';
    const prepared = offer && offer.kind === 'setup';
    const saved = timeAgo(offer ? offer.created : copy.created);
    const headline = prepared ? 'You had prepared a game before the server restarted.'
      : offer ? 'A game was interrupted when the server restarted.' : 'The server has lost your game, but this browser still has a copy.';
    const detail = prepared ? `${escapeHtml(offer.description)} (saved ${saved}).`
      : `${escapeHtml(offer ? offer.description : copy.label)}, saved ${saved}. Phones that were in that game reconnect by themselves, and the clock waits for you.`;
    const restore = offer ? `adminApp.restoreServerSave(${offer.id}, true)` : `adminApp.restoreBrowserSave(${this._browserSaves().indexOf(copy)}, true)`;
    setHtml(box, `<div class="grow"><b>${headline}</b><p>${detail}</p></div>
      <div class="row wrap"><button type="button" class="btn btn-primary" id="resume-btn" onclick="${restore}">Bring it back</button>
      <button type="button" class="btn btn-secondary" onclick="adminApp.dismissResume()">Start fresh</button></div>`);
  }

  // "No" counts for the server's save and for this browser's copies of that game alike.
  async dismissResume() {
    try { localStorage.setItem('summit_resume_dismissed', String(Date.now() / 1000)); } catch (e) { /* offered again next time */ }
    await fetch('/api/admin/resume/dismiss', { method: 'POST' });
    showToast('It stays on the Saves tab if you change your mind.', 'info');
    this.pollState();
  }

  async saveNow() {
    const res = await (await fetch('/api/admin/save/now', { method: 'POST' })).json();
    showToast(res.message || 'Saved', res.success ? 'success' : 'danger');
    const meta = this._meta || {};
    await this.keepBrowserCopy(`Manual save · Turn ${meta.current_turn || 1}`);
    this.pollState();
    this.refreshSaves();
  }

  async downloadSave(id) {
    const res = await (await fetch('/api/admin/save/export' + (id ? `?id=${id}` : ''))).json();
    if (!res.success) return showToast(res.message, 'danger');
    const meta = res.snapshot.meta || {};
    const blob = new Blob([JSON.stringify(res, null, 1)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `summit-save-turn${meta.current_turn || 1}-${new Date().toISOString().slice(0, 16).replace(/[:T]/g, '-')}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  async _restore(body, resuming) {
    const ok = await confirmAction(resuming
      ? { title: 'Bring this game back?', message: 'Phones that were in that game reconnect by themselves. The clock stays paused until you resume it.', confirmLabel: 'Bring it back' }
      : { title: 'Restore this save?', message: 'The current game is replaced by it (a copy of the current game is kept here first). The clock stays paused until you resume it.', confirmLabel: 'Restore', tone: 'danger' });
    if (!ok) return;
    const res = await (await fetch('/api/admin/save/restore', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
    })).json();
    showToast(res.message, res.success ? 'success' : 'danger');
    this.refreshSaves();
    this.pollState();
  }

  restoreServerSave(id, resuming) { return this._restore({ id }, resuming); }

  restoreBrowserSave(i, resuming) {
    const s = this._browserSaves()[i];
    if (s) return this._restore({ snapshot: s.snapshot }, resuming);
  }

  loadSaveFile(input) {
    const file = input.files && input.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const data = JSON.parse(reader.result);
        this._restore({ snapshot: data.snapshot || data });
      } catch (e) { showToast('That file is not a valid save.', 'danger'); }
      input.value = '';
    };
    reader.readAsText(file);
  }

  downloadReport() {
    window.open('/admin/report', '_blank');
  }

  async setReflection(step) {
    const res = await (await fetch('/api/admin/reflection', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ step })
    })).json();
    if (!res.success) showToast(res.message, 'danger');
    this.pollState();
  }

  renderQuestionInbox(proposals) {
    // Questions are ordinary motions: they need a co-sponsor and a passing vote before the facilitators answer.
    const questions = proposals.filter(p => p.effect_type === 'gm_question' || p.effect_type === 'open');
    const isOpen = p => p.effect_type === 'open';
    const toAnswer = questions.filter(p => p.status === 'passed' && (isOpen(p) ? p.awaiting_gm : !p.answer));
    const badge = document.getElementById('gm-tab-badge');
    if (badge) { badge.innerText = toAnswer.length; badge.style.display = toAnswer.length ? 'inline-block' : 'none'; }
    const count = document.getElementById('gm-inbox-count');
    if (count) count.innerText = toAnswer.length ? `· ${toAnswer.length} to answer` : '';
    const box = document.getElementById('gm-inbox');
    if (!box) return;
    // Re-render only when questions change, so an answer being typed is not wiped by the 1-second refresh.
    const key = questions.map(p => `${p.id}:${p.status}:${p.answer ? 1 : 0}:${p.awaiting_gm ? 1 : 0}`).join(',');
    if (key === this._inboxKey) return;
    if (this._inboxKey !== undefined && toAnswer.some(p => !this._inboxKey.includes(`${p.id}:passed`))) {
      showToast('The Assembly passed a motion for the game masters', 'info');
      synth.playChime();
    }
    this._inboxKey = key;
    const esc = escapeHtml;
    const stateLine = p => ({
      draft: 'Waiting for a co-sponsor', qualified: 'On the ballot: waiting for the Assembly vote',
      rejected: 'Rejected by the Assembly: no answer needed',
    })[p.status] || '';
    box.innerHTML = questions.length ? questions.slice().reverse().map(p => `
      <div class="inset">
        <div class="row-between"><b>${esc(p.proposer_name)}</b><span class="section-sub" style="margin:0;">${esc(p.time_str || '')}</span></div>
        <div style="font-weight:600; margin-top:4px;">${isOpen(p) ? '✍️ Open motion: ' : ''}${esc(p.title)}</div>
        <p class="small" style="white-space:pre-line; margin-top:2px;">${esc(p.description)}</p>
        ${isOpen(p) && p.status === 'passed' ? (p.awaiting_gm ? `
        <div class="callout warn mt-1">Passed by the Assembly. It has no automatic effect: carry it out, then mark it done.</div>
        <textarea class="form-textarea mt-1" rows="2" id="answer-${esc(p.id)}" placeholder="What you did (shown to everyone)…"></textarea>
        <button class="btn btn-primary btn-sm mt-1" onclick="adminApp.completeOpenMotion('${esc(p.id)}')">Mark as carried out</button>`
          : `<div class="callout ok mt-1"><b>Carried out:</b> ${esc(p.result_text || '')}</div>`) :
        p.answer ? `<div class="callout ok mt-1"><b>Answered:</b> ${esc(p.answer)}</div>`
          : p.status === 'passed' ? `
        <div class="callout warn mt-1">Passed by the Assembly: please answer. Everyone sees the answer.</div>
        <textarea class="form-textarea mt-1" rows="2" id="answer-${esc(p.id)}" placeholder="Your answer…"></textarea>
        <button class="btn btn-primary btn-sm mt-1" onclick="adminApp.answerQuestion('${esc(p.id)}')">Publish answer</button>`
          : `<div class="section-sub mt-1">${stateLine(p)}</div>`}
      </div>`).join('') : '<p class="empty-state">Nothing yet.</p>';
  }

  async loadJournal() {
    const box = document.getElementById('journal-list');
    if (!box) return;
    const res = await (await fetch('/api/admin/journal')).json();
    if (!res.success) return;
    const esc = escapeHtml;
    const html = res.entries.slice(0, 40).map(e => `<div class="inset journal-entry ${e.reverted ? 'reverted' : ''}">
        <div class="row-between"><b>${esc(e.label)}</b><span class="section-sub" style="margin:0;">${esc(e.time_str)} · Turn ${esc(e.turn)} · ${esc(e.actor)}</span></div>
        <ul class="small journal-lines">${e.lines.map(l => `<li>${esc(l)}</li>`).join('')}</ul>
        ${e.reverted ? '<span class="status-pill neutral">Reversed</span>'
          : e.undoable ? `<button class="btn btn-secondary btn-sm" onclick="adminApp.undoJournal('${esc(e.id)}')">↩ Reverse this change</button>`
          : '<span class="section-sub">Cannot be reversed here: correct the values with the resource editor.</span>'}
      </div>`).join('') || '<p class="empty-state">Nothing yet.</p>';
    if (html !== this._journalHtml) { this._journalHtml = html; box.innerHTML = html; }
  }

  async undoJournal(id) {
    const entry = ((await (await fetch('/api/admin/journal')).json()).entries || []).find(e => e.id === id);
    if (!entry) return;
    if (!(await confirmAction({ title: `Reverse "${entry.label}"?`, message: 'The opposite change is applied to:', details: entry.lines, confirmLabel: 'Reverse it', tone: 'danger' }))) return;
    const res = await (await fetch('/api/admin/journal/undo', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id })
    })).json();
    showToast(res.message, res.success ? 'success' : 'danger');
    this.loadJournal();
    this.pollState();
  }

  // Modifiers: what bends the rules for each nation, and the adjustments the facilitators can make.
  async loadModifiers(force) {
    const box = document.getElementById('modifiers-list');
    if (!box) return;
    if (!force && box.contains(document.activeElement) && box.querySelector('input:focus')) return;
    const res = await (await fetch('/api/admin/modifiers')).json();
    if (!res.success) return;
    const esc = escapeHtml;
    const war = (this._rules || {}).war !== false;
    this._modNations = res.nations;
    box.innerHTML = res.nations.map(n => {
      const lim = n.limits;
      const field = (key, hint) => `<label class="mod-field"><span>${esc(lim[key][2])}</span>
        <input type="number" class="form-input" id="mod-${esc(n.id)}-${key}" value="${n.manual[key]}" min="${lim[key][0]}" max="${lim[key][1]}" step="1">
        <small>${hint}</small></label>`;
      const flag = (key, label) => `<label class="mod-flag"><input type="checkbox" id="mod-${esc(n.id)}-${key}" ${n.flags[key] ? 'checked' : ''}> ${label}</label>`;
      return `<div class="inset mod-card">
        <div class="row-between"><b>${esc(n.emoji)} ${esc(n.name)}</b>
          <span class="section-sub" style="margin:0;">${n.votes.total} votes · eats ${n.grain_use} Grain a turn${war ? ` · readiness ×${n.war.readiness}` : ''}</span></div>
        ${n.automatic.length ? `<ul class="mod-auto">${n.automatic.map(a => `<li>${esc(a)}</li>`).join('')}</ul>` : '<div class="section-sub">No automatic modifiers.</div>'}
        <div class="mod-grid">
          ${field('votes', `Base ${n.votes.base}${n.votes.richest ? ' + 1 richest' : ''}; added to these`)}
          ${field('grain_use_pct', 'Percent more or less than usual')}
          ${war ? field('war_power_pct', 'Percent, hidden from players') : ''}
          ${war ? field('war_defence_pct', 'Percent, only when attacked') : ''}
        </div>
        <div class="mod-flags">${flag('is_quarantined', 'Cordoned')}${flag('is_striking', 'General strike')}${flag('tech_efficiency_unlocked', 'Efficient Cores')}</div>
        <button class="btn btn-primary btn-sm mt-1" onclick="adminApp.saveModifiers('${esc(n.id)}')">Save modifiers</button>
      </div>`;
    }).join('') || '<p class="empty-state">No nations.</p>';
  }

  async saveModifiers(id) {
    const n = (this._modNations || []).find(x => x.id === id);
    if (!n) return;
    const manual = {}, flags = {};
    for (const key of Object.keys(n.limits)) {
      const input = document.getElementById(`mod-${id}-${key}`);
      if (input) manual[key] = parseInt(input.value, 10) || 0;      // the war fields are not shown when the game has no war
    }
    for (const key of Object.keys(n.flags)) flags[key] = document.getElementById(`mod-${id}-${key}`).checked;
    if (!(await confirmAction({ title: `Change the modifiers of ${n.name}?`, message: 'Nobody is told about this change.', confirmLabel: 'Save' }))) return;
    const res = await (await fetch('/api/admin/modifiers', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ realm_id: id, manual, flags })
    })).json();
    showToast(res.message, res.success ? 'success' : 'danger');
    this.loadModifiers(true);
    this.pollState();
  }

  async completeOpenMotion(id) {
    const note = ((document.getElementById(`answer-${id}`) || {}).value || '').trim();
    if (!(await confirmAction({ title: 'Mark this motion as carried out?', message: note || 'Everyone will see that it was carried out as written.', confirmLabel: 'Mark as done' }))) return;
    const res = await (await fetch('/api/admin/motion/complete', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id, note })
    })).json();
    showToast(res.message, res.success ? 'success' : 'danger');
    this.pollState();
  }

  async answerQuestion(id) {
    const typed = (document.getElementById(`answer-${id}`) || {}).value || '';
    if (!typed.trim()) { showToast('Write an answer first.', 'warning'); return; }
    if (!(await confirmAction({ title: 'Publish this answer to everyone?', message: typed.trim(), confirmLabel: 'Publish' }))) return;
    const answer = (document.getElementById(`answer-${id}`) || {}).value || '';
    const res = await (await fetch('/api/admin/question/answer', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id, answer })
    })).json();
    showToast(res.message, res.success ? 'success' : 'danger');
    this.pollState();
  }

  async toggleRealm(realmId, currentActive) {
    const nm = ((this._realms || []).find(r => r.id === realmId) || {}).name || 'this nation';
    if (!(await confirmAction({ title: currentActive ? `Take ${nm} out of the summit?` : `Bring ${nm} into the summit?`,
      message: 'Missions, quotas, votes, trade lists and the projector adjust at once.', confirmLabel: currentActive ? 'Take out' : 'Bring in', tone: currentActive ? 'danger' : undefined }))) return;
    try {
      const resp = await fetch('/api/admin/realm/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ realm_id: realmId, active: !currentActive })
      });
      const res = await resp.json();
      if (res.success) {
        showToast(res.message, 'info');
        this.pollState();
      } else {
        showToast(res.message, 'danger');
      }
    } catch (err) {
      showToast('Failed to toggle realm status', 'danger');
    }
  }

  async setPlayerCount(realmId, count, select) {
    const realm = (this._realms || []).find(r => r.id === realmId) || {};
    const nm = realm.name || 'this nation';
    if (!(await confirmAction({ title: `Seat ${count} delegate${Number(count) === 1 ? '' : 's'} for ${nm}?`, message: (this._rules || {}).one_secret_mission ? 'A delegation shares one secret mission, however many delegates it has.' : 'Each delegate brings one secret mission, as far as the nation has them.', confirmLabel: 'Change seats' }))) {
      if (select) select.value = realm.player_count;
      return;
    }
    try {
      const resp = await fetch('/api/admin/realm/player_count', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ realm_id: realmId, player_count: parseInt(count, 10) })
      });
      const res = await resp.json();
      if (res.success) {
        showToast(res.message, 'info');
        this.pollState();
      } else {
        showToast(res.message, 'danger');
      }
    } catch (err) {
      showToast('Failed to update player count', 'danger');
    }
  }

  async triggerRoundCrisis(roundNum) {
    if (!(await confirmAction({ title: `Broadcast Round ${roundNum}?`, message: 'In the famine scenarios this only repeats the announcement; in the Open summit it also applies the round\'s effect.', confirmLabel: 'Broadcast' }))) return;
    try {
      const resp = await fetch('/api/admin/crisis/round', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ round: roundNum })
      });
      const res = await resp.json();
      if (res.success) {
        showToast(res.message, 'info');
        synth.playSiren();
        this.pollState();
      } else {
        showToast(res.message, 'danger');
      }
    } catch (err) {
      showToast('Failed to trigger round crisis', 'danger');
    }
  }

  async clearRealmSessions(realmId, realmName) {
    const targetLabel = realmName || (realmId ? `delegation ${realmId}` : 'all delegations');
    if (!(await confirmAction({ title: `Free the seats of ${targetLabel}?`, message: 'Use this when a phone was lost or someone cannot get in. Phones still in the game take their seats back by themselves.', confirmLabel: 'Free the seats' }))) return;

    try {
      const resp = await fetch('/api/admin/realm/clear_sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ realm_id: realmId })
      });
      const res = await resp.json();
      if (res.success) {
        showToast(res.message, 'info');
        this.pollState();
      } else {
        showToast(res.message || 'Failed to free the seats', 'danger');
      }
    } catch (err) {
      showToast('Network error while freeing the seats', 'danger');
    }
  }

  _text(id, value) {
    const el = document.getElementById(id);
    if (el && el.innerText !== String(value)) el.innerText = value;
  }

  // What the game does if the motion passes (and what it actually did), exactly as the players read it.
  _effectBlock(p, type) {
    const esc = escapeHtml;
    const lines = (p.effect_text && p.effect_text.length) ? p.effect_text : [type.effect_plain || type.statutory_effect || ''].filter(Boolean);
    const body = lines.length === 1 ? ` ${esc(lines[0])}` : `<ul>${lines.map(x => `<li>${esc(x)}</li>`).join('')}</ul>`;
    const target = p.target_realm_name ? ` <em>(${esc(p.target_realm_name)})</em>` : '';
    const done = p.result_text && p.effect_type !== 'gm_question' && !p.awaiting_gm ? `<div class="motion-effect"><span>Carried out:</span> ${esc(p.result_text)}</div>` : '';
    return `<div class="motion-effect"><span>If passed (automatic):</span>${body}${target}</div>${done}`;
  }

  // A typed value in the telemetry table: ask, then set it.
  async setStatTyped(input) {
    const value = parseInt(input.value, 10);
    const old = parseInt(input.dataset.old, 10);
    if (Number.isNaN(value) || value === old) { input.value = old; return; }
    const ok = await confirmAction({ title: `Set ${input.dataset.name}'s ${input.dataset.label}?`, message: `From ${old} to ${value}. Nobody is told about this change.`, confirmLabel: 'Set the value' });
    if (!ok) { input.value = old; return; }
    try {
      const res = await (await fetch('/api/admin/realm/override', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ realm_id: input.dataset.realm, updates: { [input.dataset.field]: value } })
      })).json();
      showToast(res.success ? `${input.dataset.name}: ${input.dataset.label} ${old} → ${value}` : res.message, res.success ? 'info' : 'danger');
    } catch (err) { showToast('Override failed', 'danger'); }
    this._tableHtml = null;
    this.pollState();
  }

  // ---------------------------------------------------------------------------
  // Bulk resource editor
  // ---------------------------------------------------------------------------
  bulkRowsState() {
    if (!this.bulkRows) this.bulkRows = [{ resource: 'grain', mode: 'add', amount: 10 }];
    if (!this.bulkSelected) this.bulkSelected = new Set();
    return this.bulkRows;
  }

  renderBulkNations(realms) {
    const rows = this.bulkRowsState();
    const box = document.getElementById('bulk-nations');
    if (!box) return;
    const key = realms.map(r => `${r.id}:${r.active !== false}`).join(',');
    if (key !== this._bulkKey) {
      this._bulkKey = key;
      for (const id of [...this.bulkSelected]) if (!realms.some(r => r.id === id)) this.bulkSelected.delete(id);
      box.innerHTML = realms.map(r => `<label class="bulk-nation ${this.bulkSelected.has(r.id) ? 'on' : ''}" style="${r.active === false ? 'opacity:0.55;' : ''}">
        <input type="checkbox" ${this.bulkSelected.has(r.id) ? 'checked' : ''} onchange="adminApp.bulkToggle('${escapeHtml(r.id)}', this)">
        <span>${escapeHtml(r.emoji || '🏛️')}</span> ${escapeHtml(r.name)}${r.active === false ? ' (not playing)' : ''}</label>`).join('');
    }
    if (!this._bulkRowsBuilt) this.renderBulkRows();
  }

  renderBulkRows() {
    this._bulkRowsBuilt = true;
    const box = document.getElementById('bulk-rows');
    if (!box) return;
    const rows = this.bulkRowsState();
    const stats = [['grain', 'Grain'], ['cores', 'Cores'], ['silk', 'Silk'], ['military', 'Military'], ['vitality', 'Vitality'], ['standing', 'Standing'], ['stability', 'Stability']];
    box.innerHTML = rows.map((r, i) => `<div class="bulk-row">
      <label class="form-label">What<select class="form-select" onchange="adminApp.bulkSet(${i}, 'resource', this.value)">
        ${stats.map(([v, l]) => `<option value="${v}" ${v === r.resource ? 'selected' : ''}>${l}</option>`).join('')}</select></label>
      <label class="form-label">Action<select class="form-select" onchange="adminApp.bulkSet(${i}, 'mode', this.value)">
        <option value="add" ${r.mode === 'add' ? 'selected' : ''}>Add</option><option value="take" ${r.mode === 'take' ? 'selected' : ''}>Take away</option>
        <option value="set" ${r.mode === 'set' ? 'selected' : ''}>Set to exactly</option></select></label>
      <label class="form-label">Amount<input type="number" class="form-input" min="0" max="999" value="${r.amount}" inputmode="numeric"
        oninput="adminApp.bulkSet(${i}, 'amount', this.value, true)"></label>
      ${rows.length > 1 ? `<button class="btn btn-secondary btn-sm" onclick="adminApp.bulkRemoveRow(${i})" title="Remove this row">✕</button>` : '<span></span>'}
    </div>`).join('');
  }

  bulkSet(i, key, value, quiet) {
    const row = this.bulkRowsState()[i];
    row[key] = key === 'amount' ? (value === '' ? 0 : Math.max(0, parseInt(value, 10) || 0)) : value;
    this.renderBulkPreview();
  }

  bulkAddRow() {
    const rows = this.bulkRowsState();
    if (rows.length < 4) rows.push({ resource: 'cores', mode: 'add', amount: 10 });
    this.renderBulkRows();
    this.renderBulkPreview();
  }

  bulkRemoveRow(i) {
    this.bulkRowsState().splice(i, 1);
    this.renderBulkRows();
    this.renderBulkPreview();
  }

  bulkToggle(id, box) {
    this.bulkRowsState();
    if (box.checked) this.bulkSelected.add(id); else this.bulkSelected.delete(id);
    box.parentElement.classList.toggle('on', box.checked);
    this.renderBulkPreview();
  }

  bulkSelect(which) {
    this.bulkRowsState();
    this.bulkSelected = new Set(which === 'all' ? (this._realms || []).filter(r => r.active !== false).map(r => r.id) : []);
    this._bulkKey = null;
    this.renderBulkNations(this._realms || []);
    this.renderBulkPreview();
  }

  bulkPreview() { this.renderBulkPreview(); }

  // What each chosen nation would end up with, worked out the same way the server does it.
  _bulkOutcome() {
    const FIELDS = { grain: 'alchemical_grain', cores: 'aether_cores', silk: 'echo_silk', military: 'military_power',
                     vitality: 'public_vitality', standing: 'diplomatic_standing', stability: 'civil_stability' };
    const NAMES = { grain: 'Grain', cores: 'Cores', silk: 'Silk', military: 'Military', vitality: 'Vitality', standing: 'Standing', stability: 'Stability' };
    const lines = [];
    for (const r of (this._realms || []).filter(x => this.bulkSelected && this.bulkSelected.has(x.id))) {
      const parts = [];
      for (const row of this.bulkRowsState()) {
        const field = FIELDS[row.resource];
        const before = (r._sim && r._sim[field] !== undefined) ? r._sim[field] : (r[field] ?? 0);
        let after = row.mode === 'add' ? before + row.amount : row.mode === 'take' ? before - row.amount : row.amount;
        after = ['vitality', 'standing', 'stability'].includes(row.resource) ? Math.max(0, Math.min(100, after)) : Math.max(0, after);
        (r._sim = r._sim || {})[field] = after;
        if (after !== before) parts.push(`${NAMES[row.resource]} ${before} → ${after}`);
      }
      delete r._sim;
      lines.push(`${r.name}: ${parts.length ? parts.join(', ') : 'no change'}`);
    }
    return lines;
  }

  renderBulkPreview() {
    const box = document.getElementById('bulk-preview');
    if (!box) return;
    this.bulkRowsState();
    const lines = this._bulkOutcome();
    setHtml(box, lines.length
      ? `<b>This would change:</b><br>${lines.map(escapeHtml).join('<br>')}`
      : '<span class="muted">Tick the nations to change.</span>');
  }

  async bulkApply() {
    const rows = this.bulkRowsState();
    const ids = [...this.bulkSelected];
    if (!ids.length) { showToast('Tick at least one nation.', 'warning'); return; }
    const lines = this._bulkOutcome();
    const announce = document.getElementById('bulk-announce').checked;
    const reason = document.getElementById('bulk-reason').value.trim();
    const ok = await confirmAction({
      title: `Change ${ids.length} nation${ids.length === 1 ? '' : 's'}?`,
      message: announce ? 'The nations are told (news and a sound).' : 'Nobody is told. The change is written to the results report.',
      details: lines.slice(0, 12).concat(lines.length > 12 ? [`…and ${lines.length - 12} more`] : []),
      confirmLabel: 'Apply the changes', tone: 'danger',
    });
    if (!ok) return;
    try {
      const res = await (await fetch('/api/admin/resources/bulk', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ realm_ids: ids, changes: rows.map(r => ({ resource: r.resource, mode: r.mode, amount: r.amount })), announce, reason })
      })).json();
      showToast(res.message, res.success ? 'success' : 'danger');
      if (res.success) { synth.playChime(); this._tableHtml = null; }
    } catch (err) { showToast('The change did not go through.', 'danger'); }
    this.pollState();
  }

  // ---------------------------------------------------------------------------
  // War log: both sides of every battle
  // ---------------------------------------------------------------------------
  renderSieges(sieges) {
    const box = document.getElementById('admin-sieges');
    if (!box) return;
    const esc = escapeHtml;
    const html = sieges.map(s => `<div class="inset">
      <div class="row-between"><b>🏰 ${esc(s.attacker_name)} marches on ${esc(s.defender_name)}</b>
        <span class="siege-eta">${Math.floor(s.eta / 60)}:${String(s.eta % 60).padStart(2, '0')}</span></div>
      <div class="mt-1"><button class="btn btn-secondary btn-sm" onclick="adminApp.siegeAction('${esc(s.id)}', 'arrive')">Arrive now</button>
        <button class="btn btn-secondary btn-sm" onclick="adminApp.siegeAction('${esc(s.id)}', 'cancel')">Call back (return supplies)</button></div></div>`).join('');
    if (html !== this._siegeHtml) { this._siegeHtml = html; box.innerHTML = html; }
  }

  async siegeAction(id, action) {
    const arrive = action === 'arrive';
    if (!(await confirmAction({ title: arrive ? 'Bring this army in now?' : 'Call this army back?',
      message: arrive ? 'The battle is fought immediately.' : 'The march is cancelled and the attacker gets its supplies back.', confirmLabel: arrive ? 'Fight now' : 'Call back', tone: 'danger' }))) return;
    const res = await (await fetch('/api/admin/siege', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id, action })
    })).json();
    showToast(res.message, res.success ? 'success' : 'danger');
    this.pollState();
  }

  renderWarLog(battles, settings) {
    const box = document.getElementById('admin-war-log');
    if (!box) return;
    this._text('war-log-count', battles.length ? `· ${battles.length}` : '');
    const key = battles.map(b => b.id).join(',') + (settings.attacks_enabled === false ? 'off' : '');
    if (key === this._warLogKey) return;
    this._warLogKey = key;
    const esc = escapeHtml;
    const side = (name, d) => d ? `<div><b>${esc(name)}</b>: ${esc(d.military)} Military × readiness ${esc(d.readiness)} × (1 ${d.environment_pct >= 0 ? '+' : ''}${esc(d.environment_pct)}% ground/weather ${d.luck_pct >= 0 ? '+' : ''}${esc(d.luck_pct)}% luck) = <b>${esc(d.power)}</b></div>` : '';
    const changes = d => Object.entries((d && d.changes) || {}).map(([r, n]) => `${n > 0 ? '+' : '−'}${Math.abs(n)} ${RESOURCE_SHORT[r] || r}`).join(', ');
    box.innerHTML = battles.length ? battles.map(b => `<div class="inset">
      <div class="row-between"><b>${esc(b.attacker_name)} ⚔️ ${esc(b.defender_name)}</b><span class="section-sub" style="margin:0;">Turn ${esc(b.turn)} · ${esc(b.time_str)}</span></div>
      <div class="small"><b>${esc(BattleScene.outcome(b).text)}</b> · ${b.mode === 'surprise' ? 'surprise attack' : 'siege'} · ${esc(b.weather.name)} · ${esc(b.terrain.name)}</div>
      <div class="small" style="margin-top:4px;">${side(b.attacker_name, b.private && b.private.attacker)}${side(b.defender_name, b.private && b.private.defender)}</div>
      <div class="small muted" style="margin-top:4px;">${esc(b.attacker_name)}: ${esc(changes(b.private && b.private.attacker))}<br>${esc(b.defender_name)}: ${esc(changes(b.private && b.private.defender))}</div>
      <div class="small muted" style="margin-top:4px;">Entered something wrong? Reverse the resource changes under Nations' numbers → Undo a mistake.</div>
    </div>`).join('') : `<p class="empty-state">${settings.attacks_enabled === false ? 'Attacks are switched off for this summit.' : 'No battles yet.'}</p>`;
  }

  async logout() {
    try {
      await fetch('/api/auth/admin/logout', { method: 'POST' });
      window.location.href = '/admin';
    } catch (err) {
      window.location.href = '/admin';
    }
  }
}

window.AdminApp = AdminApp;
