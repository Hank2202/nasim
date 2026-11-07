/**
 * The Summit of Realms - phone console for a delegation (RealmApp)
 */
'use strict';

// -----------------------------------------------------------------------------
// Participant Mobile Cockpit App (RealmApp)
// -----------------------------------------------------------------------------
class RealmApp {
  // The settings come with the page, so help texts are right even before the first poll has answered.
  constructor(realmId, settings) {
    this.realmId = realmId;
    this._settings = settings || {};
    this.rules = this._settings.rules || {};
    this.lastAudioSeq = null;
    this.isPolling = false;
    window.realmApp = this;
  }

  start() {
    this.pollState();
    setInterval(() => this.pollState(), 1000);
    this.bindEvents();
    this.bindBottomNav();
    this.showWelcome();
    // A phone that wakes up should not show old numbers for even a second.
    document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') this.pollState(); });
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
    if (viewId === 'view-news') this.renderNewsBadge(this.rawNewsFeed || []);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  async leaveDelegation() {
    if (!(await confirmAction({ title: 'Leave your delegation?', message: 'You go back to the first page. You can join again with the passcode.', confirmLabel: 'Leave' }))) return;
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
  // Help: the first-time card, the ? button, and what each number means when tapped
  // ---------------------------------------------------------------------------
  showWelcome() {
    let seen = false;
    try { seen = localStorage.getItem('summit_welcome_seen') === '1'; } catch (e) { /* private window: shown again next time */ }
    const card = document.getElementById('welcome-card');
    if (card && !seen) card.style.display = '';
  }

  dismissWelcome() {
    try { localStorage.setItem('summit_welcome_seen', '1'); } catch (e) { /* not remembered, that is all */ }
    const card = document.getElementById('welcome-card');
    if (card) card.style.display = 'none';
  }

  openHelp() {
    const r = this.rules || {}, s = this._settings || {};
    const minutes = s.working_session_seconds ? ` (${Math.round(s.working_session_seconds / 60)} minutes)` : '';
    const votes = this._me ? this._me.assembly_votes : 1;
    const close = showSheet({ title: 'How this works', html: `
      <h3>How a turn goes</h3>
      <ol>
        <li><b>Working session${minutes}.</b> Walk around and talk. Trade, enact decrees and table motions before the bell.</li>
        <li><b>The Assembly votes</b> on every motion that found a co-sponsor. Your nation has ${votes} vote${votes === 1 ? '' : 's'}.${r.grand_plenary ? ' In the last turn each motion is debated out loud first.' : ''}</li>
        <li><b>Your people eat${s.grain_consumption ? ` ${s.grain_consumption} Grain` : ''}.</b> Then the next turn begins.</li>
      </ol>
      <p>After Turn ${s.max_turns || 3} the results are counted: how many of your goals you met, and how the whole continent fares.</p>
      ${r.verdict_rules ? `<h3>How the continent is judged</h3>
      <ul class="verdict-rules">
        <li><b>🟢 Stable continent:</b> at the end no nation is out of Grain, every nation has at least 50 Stability and the average Standing of all nations is at least 50. No nation's Stability may ever have fallen to 0.</li>
        <li><b>🟡 Fragile peace:</b> at the end at most one nation is out of Grain, and no nation's Stability has ever fallen to 0.</li>
        <li><b>🔴 Continental crisis:</b> two or more nations are out of Grain at the end, or a nation's Stability fell to 0.</li>
      </ul>` : ''}
      <h3>Where to find things</h3>
      <dl>
        <dt>Realm</dt><dd>Your numbers, your goals, your decrees${r.war ? ' and the war room' : ''}.</dd>
        <dt>World</dt><dd>The news, and estimates of how the other nations stand.</dd>
        <dt>Trade</dt><dd>Offers to and from other nations.</dd>
        <dt>Motions</dt><dd>Co-sponsor other nations' motions, or propose your own.</dd>
        <dt>Wiki</dt><dd>The history of every nation${r.quiz ? '. The quiz answers are all in there' : ''}.</dd>
        ${r.quiz ? '<dt>Quiz</dt><dd>Win or lose resources, one question at a time.</dd>' : ''}
      </dl>
      <div class="sheet-actions">
        ${document.getElementById('language-switch').innerHTML}
        <a class="btn btn-secondary btn-block" href="/overview" target="_blank" rel="noopener">Read the full game guide</a>
        <button type="button" class="btn btn-secondary btn-block" id="help-sound">${synth.muted ? 'Turn sounds on' : 'Turn sounds off'}</button>
        <button type="button" class="btn btn-danger btn-block" id="help-leave">Leave this delegation</button>
      </div>` });
    document.getElementById('help-sound').addEventListener('click', e => {
      synth.setMuted(!synth.muted);
      e.target.innerText = synth.muted ? 'Turn sounds on' : 'Turn sounds off';
      if (!synth.muted) synth.playChime();
    });
    document.getElementById('help-leave').addEventListener('click', () => { close(); this.leaveDelegation(); });
  }

  // Tapping one of the player's own numbers says what it is for.
  explain(key) {
    const r = this.rules || {}, s = this._settings || {};
    const eat = this._me && this._me.tech_efficiency_unlocked ? Math.round(s.grain_consumption * 0.75) : s.grain_consumption;
    const texts = {
      grain: ['🌾 Grain', `Food. Your people eat ${eat} Grain at the end of every turn. If your silos run empty you are starving: ${r.hide_vitality ? '−20 Stability' : '−25 Vitality and −20 Stability'}, and a nation still starving at the end hurts the whole continent's result.${r.verdict_rules ? ' One nation out of Grain at the end turns a stable continent into a fragile peace; two make it a crisis.' : ''}`],
      cores: ['⚙️ Cores', 'Aether Cores run your industry. They pay for the Civil Guard and for mustering regiments. With 75 Cores your nation becomes Efficient: it eats a quarter less Grain for the rest of the summit.'],
      silk: ['🧵 Silk', 'Luxury and influence. It pays for the Grand Gala and the Forges. Your wealth is Grain + Cores + Silk, and the single richest nation has one extra vote in the Assembly.'],
      military: ['⚔️ Military', `Your army. Some missions measure it, and the news may make it matter.${r.war ? ' It decides most of a battle.' : ''}`],
      vitality: ['❤️ Vitality', 'How healthy your people are. Starving costs 25. In a battle a healthy nation fights a little better.'],
      standing: ['🤝 Standing', `How the other nations see you. It counts towards how the whole continent fares at the end.${r.verdict_rules ? ' For a stable continent the average Standing of all nations must be at least 50.' : ''}${r.war ? ' Starting a war costs Standing.' : ''}`],
      stability: ['🏛️ Stability', `How calm your people are. Starving costs 20. It counts towards how the whole continent fares at the end, and a people at 0 is a disaster for everyone.${r.verdict_rules ? ' For a stable continent every nation needs at least 50 at the end; a nation that ever falls to 0 makes it a crisis.' : ''}`],
    };
    const t = texts[key];
    if (t) showSheet({ title: t[0], html: `<p>${escapeHtml(t[1])}</p>` });
  }

  // ---------------------------------------------------------------------------
  // Motions: pick a template, set its numbers, read what will happen, table it
  // ---------------------------------------------------------------------------
  renderMotionTemplates(types) {
    const box = document.getElementById('motion-templates');
    if (!box || this.motionTemplatesRendered || !types || !types.length) return;
    this.motionTypes = Object.fromEntries(types.map(t => [t.id, t]));
    const esc = escapeHtml;
    if (this.rules && this.rules.free_motions === false) {
      this.renderSimpleMotions(box, types);
      this.motionTemplatesRendered = true;
      return;
    }
    box.innerHTML = types.filter(t => t.player_selectable).map(t => `
      <button type="button" class="motion-template" onclick="realmApp.chooseMotionTemplate('${esc(t.id)}')">
        <span class="motion-template-icon">${esc(t.icon || '📜')}</span>
        <span class="grow">
          <span class="motion-template-name">${esc(t.name)}</span>
          <span class="motion-template-summary">${esc(t.summary)}</span>
        </span>
        <span class="motion-template-go" aria-hidden="true">&rsaquo;</span>
      </button>`).join('');
    this.motionTemplatesRendered = true;
  }

  // Proposing a motion has its own screen; the floor is what most visits to this tab are for.
  openMotionBuilder() {
    document.getElementById('motion-floor').style.display = 'none';
    document.getElementById('motion-builder').style.display = '';
    window.scrollTo({ top: 0 });
  }

  closeMotionBuilder() {
    if (document.getElementById('proposal-form')) this.chooseMotionTemplate(null);
    document.getElementById('motion-builder').style.display = 'none';
    document.getElementById('motion-floor').style.display = '';
    window.scrollTo({ top: 0 });
  }

  // Simplified game: ready-made motions. A player can only change the amount; the wording and the effect are fixed.
  renderSimpleMotions(box, types) {
    const esc = escapeHtml;
    this.simpleAmounts = {};
    box.innerHTML = types.filter(t => t.player_selectable).map(t => {
      const a = t.amount;
      if (a) this.simpleAmounts[t.id] = a.default;
      return `<div class="simple-motion" data-motion="${esc(t.id)}">
        <div class="row simple-motion-head">
          <span class="motion-template-icon">${esc(t.icon || '📜')}</span>
          <span class="grow"><span class="motion-template-name">${esc(t.name)}</span>
            <span class="motion-template-summary">${esc(t.summary)}</span></span>
        </div>
        <div class="motion-effect"><span>If passed:</span> <span class="simple-effect">${esc(this._simpleText(t))}</span></div>
        ${a ? `<div class="form-label mt-1">${esc(a.label)}</div>
        <div class="stepper">
          <button type="button" aria-label="Less" onclick="realmApp.stepSimpleAmount('${esc(t.id)}', -1)">−${esc(a.step)}</button>
          <input type="number" inputmode="numeric" min="${esc(a.min)}" max="${esc(a.max)}" step="${esc(a.step)}" value="${esc(a.default)}" aria-label="${esc(a.label)}"
                 onchange="realmApp.setSimpleAmount('${esc(t.id)}', this.value)">
          <button type="button" aria-label="More" onclick="realmApp.stepSimpleAmount('${esc(t.id)}', 1)">+${esc(a.step)}</button>
        </div>` : ''}
        <button type="button" class="btn btn-primary btn-block btn-sm mt-1" onclick="realmApp.tableSimpleMotion('${esc(t.id)}')">Table this motion</button>
      </div>`;
    }).join('');
  }

  // The same words the server writes under "If passed" when the motion is tabled.
  _simpleText(t) {
    const amount = (this.simpleAmounts || {})[t.id];
    const me = this._me ? this._me.name : 'Your nation';
    return String(t.effect_plain || '').split('{amount}').join(amount).split('{me}').join(me);
  }

  setSimpleAmount(id, value) {
    const t = (this.motionTypes || {})[id];
    if (!t || !t.amount) return;
    const n = parseInt(value, 10);
    const amount = Math.max(t.amount.min, Math.min(t.amount.max, Number.isNaN(n) ? t.amount.default : n));
    this.simpleAmounts[id] = amount;
    const card = document.querySelector(`.simple-motion[data-motion="${id}"]`);
    if (card) {
      card.querySelector('input').value = amount;
      card.querySelector('.simple-effect').innerText = this._simpleText(t);
    }
  }

  stepSimpleAmount(id, direction) {
    const t = (this.motionTypes || {})[id];
    if (t && t.amount) this.setSimpleAmount(id, this.simpleAmounts[id] + direction * t.amount.step);
  }

  async tableSimpleMotion(id) {
    const t = (this.motionTypes || {})[id];
    if (!t) return;
    const ok = await confirmAction({
      title: `Table “${t.name}”?`,
      message: 'Another nation must co-sponsor it before the Assembly votes on it.',
      details: [`If passed: ${this._simpleText(t)}`],
      confirmLabel: 'Table the motion',
    });
    if (!ok) return;
    try {
      const res = await (await fetch('/api/proposal/create', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ proposer_id: this.realmId, effect_type: id, params: { amount: this.simpleAmounts[id] } }),
      })).json();
      if (res.success) {
        showToast('Motion tabled. Now find a nation to co-sponsor it!', 'success');
        synth.playChime();
        this.closeMotionBuilder();
        this.pollState();
      } else {
        showToast(res.message, 'danger');
      }
    } catch (err) {
      showToast('Failed to table the motion', 'danger');
    }
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
    const head = document.getElementById('motion-gallery-head');
    if (!typeId) {
      form.style.display = 'none';
      gallery.style.display = '';
      head.style.display = '';
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
    head.style.display = 'none';
    form.style.display = 'block';
    this.renderMotionParams();
    this.refreshMotionPreview();
    window.scrollTo({ top: 0 });
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
    const num = (key, label, min, max) => `<label>${label}<input type="number" class="form-input" inputmode="numeric" min="${min}" max="${max}" value="${esc(p[key])}"
        oninput="realmApp.setMotionParam('${key}', this.value)"></label>`;
    if (t.builder === 'redistribute') {
      box.innerHTML = `<div class="param-box"><div class="section-sub" style="margin:0 0 6px;">Set the numbers (they are applied exactly as written)</div>
        <div class="param-grid">
          <label>Resource<select class="form-select" onchange="realmApp.setMotionParam('resource', this.value)">${resOptions(['grain', 'cores', 'silk'], p.resource)}</select></label>
          ${num('above', 'Nations above this give', 10, 150)}${num('give', 'They give up to', 1, 999)}
          ${num('below', 'Nations below this receive', 1, 100)}${num('receive', 'They receive up to', 1, 999)}
        </div></div>`;
    } else if (t.builder === 'levy') {
      const dyn = [['@richest', 'The richest nation'], ['@poorest', 'The poorest nation'], ['@strongest', 'The strongest army'], ['@weakest', 'The weakest army']];
      box.innerHTML = `<div class="param-box"><div class="section-sub" style="margin:0 0 6px;">Who is sanctioned, and what do they lose?</div>
        <div class="param-grid">
          <label>Nation<select class="form-select" onchange="realmApp.setMotionParam('target', this.value)">${this._nationOptions(p.target, dyn)}</select></label>
          <label>Loses<select class="form-select" onchange="realmApp.setMotionParam('resource', this.value)">${resOptions(['grain', 'cores', 'silk', 'military', 'vitality', 'standing', 'stability'], p.resource)}</select></label>
          ${num('amount', 'Amount', 1, 999)}
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
          <input type="number" class="form-input" inputmode="numeric" min="1" max="999" value="${esc(l.amount)}" oninput="realmApp.pactSet(${i}, 'amount', this.value, true)" aria-label="Amount">
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
        this.closeMotionBuilder();
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
      connectionWatch.ok();
      this.renderState(state);
    } catch (err) {
      connectionWatch.failed();
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
    // The facilitator took this nation out of the summit: back to the first page, where the others still are.
    if (realm && realm.active === false) { window.location.href = '/'; return; }
    // The facilitator changed the complexity before play began: this page was built for the other kind of game.
    this.rules = (state.game_settings || {}).rules || {};
    if (followLanguage(state)) return;
    if (this._complexity && this._complexity !== this.rules.id) { window.location.reload(); return; }
    this._complexity = this.rules.id;
    this._lastRealms = realms;
    this._proposals = proposals || [];
    this._trades = trades || [];
    this._me = realm;
    this._turn = meta.current_turn;
    this._meta = meta;
    this._settings = state.game_settings || {};
    document.body.classList.toggle('summit-over', meta.phase === 'summit_concluded');

    // Audio cues. Another nation's decree or trade is only news on a phone: the projector chimes, and a room
    // of phones chiming at once helps nobody. (A trade this nation took part in has its own message below.)
    if (meta.audio_cue && meta.audio_cue.seq !== undefined) {
      if (this.lastAudioSeq !== null && meta.audio_cue.seq > this.lastAudioSeq && !['decree', 'trade'].includes(meta.audio_cue.type)) {
        synth.playCue(meta.audio_cue.type);
        if (meta.audio_cue.message) showToast(meta.audio_cue.message, 'info');
      }
      this.lastAudioSeq = meta.audio_cue.seq;
    }

    // A vote or debate has opened: this must not be missed, whatever the player is doing.
    const assembly = !['working', 'summit_concluded', 'turn_summary'].includes(meta.phase);
    if (assembly && this._phaseSeen !== undefined && this._phaseSeen !== meta.phase) {
      if (document.body.classList.contains('wiki-mode')) this.wikiClose();
      window.scrollTo({ top: 0, behavior: 'smooth' });
      if (navigator.vibrate) navigator.vibrate(200);
    }
    this._phaseSeen = meta.phase;

    // Header updates
    const turnElem = document.getElementById('turn-display');
    if (turnElem) turnElem.innerText = `TURN ${meta.current_turn}`;
    const clock = meta.display_timer || { seconds: meta.turn_timer_remaining, running: meta.is_timer_running, label: '' };
    const shown = clock.kind === 'free' && !clock.seconds && !clock.running ? '--:--' : formatSeconds(clock.seconds);
    const timerElem = document.getElementById('timer-display');
    if (timerElem) {
      timerElem.innerText = shown;
      timerElem.title = clock.label || '';
      timerElem.classList.toggle('stopped', !clock.running);
      timerElem.classList.toggle('low', !!clock.running && clock.seconds <= 60);
    }
    this._setVal('wk-timer', shown);       // the wiki hides the header, and nobody should read past the bell
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
    this.renderNewsBadge(news_feed || []);

    if (!realm) return;

    // Live lists of the nations actually playing (the facilitator can change the roster mid-game)
    this.renderTradePartners(realms);
    this.renderMotionNationOptions(realms);

    // What the people eat at the end of the turn (set by the scenario; a quarter less with technological efficiency)
    const eat = (state.game_settings || {}).grain_consumption;
    if (eat) this._setVal('eat-amount', `${realm.tech_efficiency_unlocked ? Math.round(eat * 0.75) : eat} Grain`);
    this.renderFoodForecast(state, realm);

    // The nation's own numbers, each with a mark when it changes (and a message if the Realm tab is not showing)
    this._setStock('grain', 'Grain', realm.alchemical_grain);
    this._setStock('cores', 'Cores', realm.aether_cores);
    this._setStock('silk', 'Silk', realm.echo_silk);
    this._setStock('military', 'Military', realm.military_power ?? 0);
    this._setMetric('vitality', 'Vitality', realm.public_vitality);
    this._setMetric('standing', 'Standing', realm.diplomatic_standing);
    this._setMetric('stability', 'Stability', realm.civil_stability);
    this.renderDecrees(realm, meta);
    this.updateTradePreview();

    // Assembly votes
    const votesBadge = document.getElementById('votes-badge');
    if (votesBadge) {
      let voteText = `${realm.assembly_votes} vote${realm.assembly_votes === 1 ? '' : 's'} in the Assembly`;
      if (realm.is_plutocrat) voteText += ` · richest nation (+1)`;
      votesBadge.innerText = voteText;
    }

    // Missions follow the roster: targets and stand-in missions change when nations join or leave
    this.renderMissions(realm);
    this.renderMissionHints(realm);

    // Flags
    this.renderFlags(realm);

    // Continental registry (World tab): live, fog-of-war tiers for other nations
    this.renderRegistry(realms);

    // Trades
    this.renderTrades(trades, realm);
    this._round2 = (!!this._settings.famine_storyline && meta.current_turn === 2) || meta.round2_rules_turn === meta.current_turn;

    // Motions Tab
    this.renderMotionTemplates(state.resolution_types);
    this.renderProposals(proposals, realm);

    // Plenary Session Callout on Mobile
    this.renderPlenarySessionCallout(meta, proposals, realm);

    // Summit Concluded Personal Evaluation Callout
    this.renderConcludedDebrief(state, realm);

    if (this.rules.quiz !== false) this.followQuiz(realm, meta);

    // War: weather, rules, targets and the battles that have been fought
    this.renderWar(state, realm);
    this.renderSiegeAlert(state.sieges || []);
    this.watchBattles(state.battles || []);
  }

  // Quiz: follow a question opened (or answered) on a teammate's phone
  followQuiz(realm, meta) {
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
  }

  // What is going on right now, and what happens next, in words. The clock alone does not say whether it is running.
  renderPhaseCard(meta) {
    const turn = meta.current_turn, last = turn >= (meta.max_turns || 3);
    const stage = clockStage(meta);
    let title, hint, tone = '';
    if (meta.phase === 'working') {
      [title, hint, tone] = {
        ready: turn === 1
          ? ['The summit is about to begin', 'The clock starts when everyone is here. Read your goals below and find the rest of your delegation.', 'waiting']
          : [`Turn ${turn} is about to begin`, 'The facilitator starts the clock in a moment. Keep talking.', 'waiting'],
        intermission: [`Turn ${turn} starts soon`, 'Listen to the facilitator: the news of the new turn is being read out.', 'waiting'],
        running: ['Working session', 'Talk to the other nations. Trade, enact decrees and table motions before the bell.', ''],
        paused: ['The clock is paused', 'The facilitator has stopped the clock for a moment.', 'waiting'],
        timeup: ['Time is up', 'The facilitator is moving on to the next step.', 'waiting'],
      }[stage];
    } else {
      [title, hint, tone] = {
        plenary_quick: ['The Assembly votes', 'Vote on every motion at the top of this screen.', 'vote'],
        grand_plenary_discussion: ['Grand Plenary: debate', 'Argue for or against the motion on the floor, out loud. Voting opens when the clock runs out.', 'vote'],
        grand_plenary_voting: ['Grand Plenary: vote', 'Vote on the motion at the top of this screen.', 'vote'],
        turn_summary: last ? ['The last vote is over', 'The results are coming.', 'waiting'] : ['Between turns', 'The vote is over. The next turn starts soon.', 'waiting'],
        summit_concluded: ['The summit has ended', 'See how your nation fared.', 'waiting'],
      }[meta.phase] || ['Working session', '', ''];
    }
    this._setVal('phase-kicker', `Turn ${turn} of ${meta.max_turns || 3}`);
    this._setVal('phase-title', title);
    this._setVal('phase-hint', hint);
    const card = document.getElementById('phase-card');
    if (card) card.dataset.tone = tone;
    const bar = document.getElementById('phase-progress');
    if (bar) {
      const total = meta.turn_timer_total || 0;
      const left = meta.turn_timer_remaining || 0;
      bar.style.width = (meta.phase === 'working' && total > 0) ? `${Math.max(0, Math.min(100, 100 * left / total))}%` : '0%';
    }
  }

  // Decrees that cannot be paid for right now say so before the tap, not after it.
  renderDecrees(realm, meta) {
    const stock = { grain: realm.alchemical_grain, cores: realm.aether_cores, silk: realm.echo_silk };
    const open = meta.phase === 'working';
    document.querySelectorAll('.decree').forEach(btn => {
      const needs = JSON.parse(btn.dataset.needs || '{}');
      const missing = Object.keys(needs).filter(r => (stock[r] ?? 0) < needs[r]).map(r => RESOURCE_SHORT[r]);
      btn.classList.toggle('cannot', !open || missing.length > 0);
      const why = btn.querySelector('.decree-why');
      if (why) why.innerText = open && missing.length ? `Not enough ${missing.join(' and ')}` : '';
    });
    this._setVal('decrees-intro', open
      ? 'Spend your own resources to gain others. No other nation is involved. Tap one to enact it.'
      : 'Decrees can wait for the next working session.');
  }

  // Simplified game: how far the Grain lasts (one meal at the end of every turn left). Only the meals are
  // counted: what the storyline has in store stays a surprise, so it says "as things stand".
  renderFoodForecast(state, realm) {
    const el = document.getElementById('food-forecast');
    if (!el) return;
    const settings = state.game_settings || {}, meta = state.meta;
    if (meta.phase === 'summit_concluded') { el.style.display = 'none'; return; }
    const eat = realm.tech_efficiency_unlocked ? Math.round(settings.grain_consumption * 0.75) : settings.grain_consumption;
    const meals = Math.max(0, (settings.max_turns || 3) - meta.current_turn + 1);
    const need = eat * meals + 1;                 // silos at 0 count as starving, so something has to be left
    const short = need - realm.alchemical_grain;
    const word = `${meals} meal${meals === 1 ? '' : 's'} left`;
    el.innerText = short > 0 ? `⚠️ As things stand you are ${short} Grain short for the ${word}. Trade for more, or ask the Assembly.`
                             : `✓ As things stand you have enough Grain for the ${word}.`;
    el.classList.toggle('short', short > 0);
  }

  // Simplified game: where this nation's missions stand right now (same check as the final results).
  renderMissionHints(realm) {
    const status = realm.mission_status;
    if (!status) return;
    const esc = escapeHtml;
    const hint = m => `<span class="mission-hint ${m.met ? 'ok' : 'no'}">${m.met ? '✓ On track' : '… Not yet'}</span>${m.note ? `<span class="mission-note">${esc(m.note)}</span>` : ''}`;
    setHtml(document.getElementById('public-hint'), hint(status.public));
    for (const s of status.secrets || []) setHtml(document.getElementById(`secret-hint-${s.id}`), hint(s));
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
    this._setVal('secret-count-label', secrets.length === 1 ? '🔒 Your secret mission' : `🔒 Your ${secrets.length} secret missions`);
    const list = document.getElementById('secret-missions-list');
    const hints = (this.rules || {}).live_hints;
    if (list) list.innerHTML = secrets.map((sm, i) => `
      <div class="secret-item">
        <strong>${i + 1}. ${esc(sm.title)}</strong>
        ${sm.narrative ? `<p>${esc(sm.narrative)}</p>` : ''}
        <div class="secret-goal">${esc(sm.objective)}</div>
        ${hints ? `<div id="secret-hint-${esc(sm.id)}" class="mission-hint-row"></div>` : ''}
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

  // A number of the nation's own changed: mark it where it is, and say so if another tab is showing.
  _noteChange(key, label, value, host) {
    this._numbers = this._numbers || {};
    const before = this._numbers[key];
    this._numbers[key] = value;
    if (before === undefined || before === value) return;
    const change = value - before;
    const text = `${change > 0 ? '+' : '−'}${Math.abs(change)}`;
    if (host) {
      const mark = document.createElement('span');
      mark.className = `delta ${change > 0 ? 'up' : 'down'}`;
      mark.textContent = text;
      host.appendChild(mark);
      setTimeout(() => mark.remove(), 5000);
    }
    const onRealm = document.getElementById('view-overview').classList.contains('active');
    if (!onRealm) showToast(`${label} ${text} (now ${value})`, change > 0 ? 'success' : 'warning');
  }

  _setStock(key, label, val) {
    const el = document.getElementById(`${key}-val`);
    if (!el) return;
    el.innerText = val;
    this._noteChange(key, label, val, el.closest('.coin'));
    el.closest('.coin').classList.toggle('empty', key === 'grain' && val <= 0);
  }

  _setMetric(name, label, val) {
    const valEl = document.getElementById(`${name}-val`);
    const barEl = document.getElementById(`${name}-bar`);
    if (!valEl) return;
    valEl.innerText = `${val}/100`;
    if (barEl) {
      barEl.style.width = `${val}%`;
      barEl.classList.toggle('low', val < 50);
      barEl.classList.toggle('critical', val < 25);
    }
    this._noteChange(name, label, val, valEl.closest('.vital'));
  }

  worldShow(which) {
    document.getElementById('world-news').style.display = which === 'news' ? '' : 'none';
    document.getElementById('world-nations').style.display = which === 'nations' ? '' : 'none';
    document.querySelectorAll('.segment[data-world]').forEach(b => b.classList.toggle('active', b.dataset.world === which));
  }

  // How many news items have come in since the player last looked at the World tab.
  renderNewsBadge(news) {
    const badge = document.getElementById('nav-news-badge');
    if (!badge) return;
    const newest = news.length ? news[0].id : null;
    if (this._newsSeenId === undefined || document.getElementById('view-news').classList.contains('active')) this._newsSeenId = newest;
    const at = news.findIndex(n => n.id === this._newsSeenId);
    const unread = at < 0 ? news.length : at;
    badge.innerText = unread > 9 ? '9+' : unread;
    badge.style.display = unread ? 'inline-block' : 'none';
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
      setHtml(newsContainer, '<p class="empty-state">No news of this kind yet.</p>');
      return;
    }

    const icons = { crisis: '⚡', trade: '🤝', assembly: '📜', lore: '📖', turn: '🔔', diplomacy: '🕊️', war: '⚔️', boon: '🌟' };
    setHtml(newsContainer, filtered.map(n => `
      <article class="news-item">
        <span class="news-item-icon">${icons[n.type] || '✦'}</span>
        <div class="grow">
          <div class="news-item-head"><strong>${escapeHtml(n.headline)}</strong><span>${escapeHtml(n.time_str)}</span></div>
          <p>${escapeHtml(n.detail)}</p>
        </div>
      </article>
    `).join(''));
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

    const esc = escapeHtml;
    const look = { legendary: ['🟢', 'stable'], moderate: ['🟡', 'fragile'] }[outcome.continental_grade] || ['🔴', 'crisis'];
    const result = (title, goal, achieved, explanation) => `<div class="mission-result ${achieved ? 'met' : 'missed'}">
        <div class="row-between"><strong>${esc(title)}</strong><span class="status-pill ${achieved ? 'ok' : 'bad'}">${achieved ? 'Met' : 'Not met'}</span></div>
        ${goal ? `<p class="mission-result-goal">${esc(goal)}</p>` : ''}
        <p class="mission-result-why">${esc(explanation)}</p>
      </div>`;
    const pub = myEval.public_mission_eval;
    const secrets = myEval.secret_missions_eval || [];

    container.style.display = 'block';
    setHtml(container, `
      <div class="verdict-card ${look[1]}">
        <div class="phase-kicker">The summit has ended</div>
        <h2 class="verdict-title">${look[0]} ${esc(outcome.continental_verdict)}</h2>
        <p class="verdict-desc">${esc(outcome.continental_desc)}</p>
        <div class="verdict-score">${esc(myEval.name)}: ${myEval.achieved_missions} of ${myEval.total_missions} goals met</div>
        ${pub ? result(`Public mandate: ${pub.title}`, pub.description, pub.achieved, pub.explanation) : ''}
        ${secrets.map((sm, i) => result(`Secret mission ${i + 1}: ${sm.title}`, sm.objective, sm.achieved, sm.explanation)).join('')}
        <p class="verdict-epilogue">${esc(myEval.epilogue)}</p>
      </div>
    `);
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
        ${(this.rules || {}).quiz === false ? '' : '<p class="wk-muted">The answers to every quiz question are somewhere in these articles.</p>'}${cats}`, { nav: false });
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
    const summitOver = meta.phase === 'summit_concluded';
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
    const open = document.getElementById('war-open');
    if (open) open.style.display = this.war && this.war.from_turn <= meta.current_turn && !summitOver ? '' : 'none';
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
      const blocked = (war.targets || []).filter(t => !t.can_attack);
      // setHtml: a tap on a target must not land between two rebuilds of the list.
      setHtml(chips, ((war.targets || []).map(t => {
        const r = names[t.id] || {};
        return `<button type="button" class="war-chip ${t.id === this.warTarget ? 'active' : ''}" style="--chip-color:${esc(r.theme_color || '#8c7a5e')}"
          ${t.can_attack ? '' : 'disabled'} title="${esc(t.reason || '')}" onclick="realmApp.selectWarTarget('${esc(t.id)}')"><span>${esc(r.emoji || '🏛️')}</span>${esc(t.name)}</button>`;
      }).join('') || '<p class="empty-state">No other nations are playing.</p>')
        + (blocked.length && blocked.length === (war.targets || []).length ? `<p class="section-sub" style="width:100%;">${esc(blocked[0].reason)}</p>` : ''));
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
    const buttons = document.getElementById('war-buttons');
    if (buttons) buttons.style.display = this.warTarget ? '' : 'none';
    if (!this.warTarget || !p) {
      box.innerHTML = '';
      this._setWarButtons(null);
      return;
    }
    const m = p.modes || {};
    const way = (key, title) => m[key] ? `<div class="way-card ${m[key].can_attack ? '' : 'off'}">
        <div class="way-title">${title}</div>
        <div class="scout-odds ${esc(m[key].tone || 'even')}">${esc(m[key].label)}</div>
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

  // The alarm for a nation under siege is on every tab, with what can be done about it.
  renderSiegeAlert(sieges) {
    const box = document.getElementById('siege-alert');
    if (!box) return;
    const coming = sieges.filter(s => s.defender_id === this.realmId);
    box.style.display = coming.length ? '' : 'none';
    setHtml(box, coming.map(s => `<div class="row-between"><b>⚠️ ${escapeHtml(s.attacker_name)} is marching on you!</b>
      <b class="siege-eta">${Math.floor(s.eta / 60)}:${String(s.eta % 60).padStart(2, '0')}</b></div>`).join('')
      + (coming.length ? '<p>The battle is fought when the army arrives, with the numbers of that moment. Trade for Grain, steady your people, raise your army.</p>' : ''));
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
      if (s.defender_id === this.realmId) synth.playAlert();
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
    this._openNations = this._openNations || new Set();
    if (!list._toggleWatched) {               // what is open stays open when a number changes and the list is rebuilt
      list._toggleWatched = true;
      list.addEventListener('toggle', e => {
        const id = e.target.dataset && e.target.dataset.nation;
        if (!id) return;
        if (e.target.open) this._openNations.add(id); else this._openNations.delete(id);
      }, true);
    }
    setHtml(list, realms.filter(r => r.active !== false).map(r => {
      const mine = r.id === this.realmId;
      const mandate = r.public_mission || {};
      return `<details class="nation-card" data-nation="${esc(r.id)}" style="--nc:${esc(r.theme_color || '#8c7a5e')}" ${this._openNations.has(r.id) ? 'open' : ''}>
        <summary>
          <div class="nation-card-head">
            <span class="crest small">${esc(r.emoji || '🏛️')}</span>
            <div class="grow"><strong>${esc(r.name)}</strong>${mine ? ' <span class="status-pill open">You</span>' : ''}
              <div class="nation-card-sub">${esc(mandate.title || r.ethos || '')}</div></div>
            <span class="vote-seal" title="Assembly votes">${r.assembly_votes}</span>
          </div>
          <div class="nation-card-pips">
            ${pips('🌾', 'Grain', r.grain_tier)}${pips('⚙️', 'Cores', r.cores_tier)}${pips('🧵', 'Silk', r.silk_tier)}${pips('⚔️', 'Military', r.military_tier)}
            ${pips('🤝', 'Standing', r.standing_tier)}${pips('🏛️', 'Stability', r.stability_tier)}
          </div>
          ${r.is_starving ? '<div class="flag bad mt-1">🥀 Starving</div>' : ''}
        </summary>
        <p class="nation-card-more"><b>Public mandate:</b> ${esc(mandate.description || '—')}</p>
      </details>`;
    }).join(''));
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

    setHtml(container, html);
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
    const show = (id, on) => { const el = document.getElementById(id); if (el) el.style.display = on ? '' : 'none'; };
    const amount = (n, r) => `${n} ${RESOURCE_SHORT[r] || r}`;

    show('incoming-card', incoming.length > 0);
    setHtml(document.getElementById('incoming-trades-list'), incoming.map(t => `
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
      </div>`).join(''));

    show('outgoing-card', outgoing.length > 0);
    setHtml(document.getElementById('outgoing-trades-list'), outgoing.map(t => `
      <div class="offer-card">
        <div class="offer-head"><strong>To ${esc(t.receiver_name)}</strong><span>Waiting for an answer…</span></div>
        <div class="offer-swap">
          <div><span>You give</span><b>${t.offer_amount} ${esc(res(t.offer_resource))}</b></div>
          <div class="offer-arrow">⇄</div>
          <div><span>You get</span><b>${t.request_amount} ${esc(res(t.request_resource))}</b></div>
        </div>
        ${note(t)}
        <button class="btn btn-secondary btn-sm mt-1" onclick="realmApp.respondTrade('${esc(t.id)}', 'cancel')">Withdraw offer</button>
      </div>`).join(''));

    // What became of this nation's offers: an offer must not simply vanish from the list.
    const mine = trades.filter(t => t.status !== 'pending' && (t.sender_id === this.realmId || t.receiver_id === this.realmId));
    show('trade-history-card', mine.length > 0);
    setHtml(document.getElementById('trade-history'), mine.slice(0, 6).map(t => {
      const sent = t.sender_id === this.realmId;
      const other = sent ? t.receiver_name : t.sender_name;
      const deal = sent ? `you give ${amount(t.offer_amount, t.offer_resource)}, you get ${amount(t.request_amount, t.request_resource)}`
                        : `you give ${amount(t.request_amount, t.request_resource)}, you get ${amount(t.offer_amount, t.offer_resource)}`;
      const [icon, cls, text] = {
        accepted: ['✓', 'ok', sent ? `${other} accepted` : `You accepted ${other}'s offer`],
        declined: ['✗', 'bad', sent ? `${other} declined` : `You declined ${other}'s offer`],
      }[t.status] || ['–', '', sent ? `Offer to ${other} withdrawn` : `${other}'s offer was withdrawn`];
      return `<div class="trade-past ${cls}"><span class="trade-past-icon">${icon}</span><span><b>${esc(text)}</b><br>${esc(deal)}</span></div>`;
    }).join(''));

    this._announceTradeNews(trades);
  }

  // Offers that arrive and answers to this nation's offers matter at once, whichever tab is showing.
  _announceTradeNews(trades) {
    const known = this._tradeStatus;
    const now = {};
    for (const t of trades) {
      if (t.sender_id !== this.realmId && t.receiver_id !== this.realmId) continue;
      now[t.id] = t.status;
      if (!known) continue;
      if (!known[t.id] && t.status === 'pending' && t.receiver_id === this.realmId) {
        const onTrade = document.getElementById('view-trades').classList.contains('active');
        showToast(onTrade ? `New offer from ${t.sender_name}` : `${t.sender_name} sent you an offer. See the Trade tab.`, 'info');
        synth.playChime();
      } else if (known[t.id] === 'pending' && t.sender_id === this.realmId && t.status === 'accepted') {
        showToast(`${t.receiver_name} accepted your offer!`, 'success');
        synth.playChime();
      } else if (known[t.id] === 'pending' && t.sender_id === this.realmId && t.status === 'declined') {
        showToast(`${t.receiver_name} declined your offer.`, 'warning');
      }
    }
    this._tradeStatus = now;
  }

  renderProposals(proposals, realm) {
    const esc = escapeHtml;
    const types = this.motionTypes || {};
    const open = proposals.filter(p => p.status === 'draft' || p.status === 'qualified');
    const decided = proposals.filter(p => p.status === 'passed' || p.status === 'rejected');
    const working = !this._meta || this._meta.phase === 'working';
    const fromSpire = p => p.proposer_id === 'spire_council';
    const canEndorse = p => working && !fromSpire(p) && !(p.support_list || []).includes(this.realmId)
      && (!p.target_seconder_id || p.target_seconder_id === this.realmId);
    const hasBallotPlace = p => (p.support_count ?? (p.support_list || []).length) >= 2 || p.is_qualified;

    // The badge counts what is waiting for a nation like this one: motions that still need a co-sponsor.
    const motionsBadge = document.getElementById('nav-motions-badge');
    if (motionsBadge) {
      const n = open.filter(p => canEndorse(p) && !hasBallotPlace(p)).length;
      motionsBadge.innerText = n;
      motionsBadge.style.display = n > 0 ? 'inline-block' : 'none';
    }
    const newBtn = document.getElementById('motion-new-btn');
    if (newBtn) newBtn.style.display = working ? '' : 'none';
    const closed = document.getElementById('motion-closed-note');
    if (closed) closed.style.display = working || (this._meta && this._meta.phase === 'summit_concluded') ? 'none' : '';

    const effectLine = p => this._motionEffectHtml(p);
    // The wording of a ready-made motion adds nothing to what "If passed" already says.
    const terms = p => (this.rules || {}).free_motions === false ? '' : `<details class="motion-terms"><summary>Read the terms</summary><p>${esc(p.description)}</p></details>`;
    const head = (p, pill) => {
      const t = types[p.effect_type] || {};
      return `<div class="row-between" style="align-items:flex-start;">
          <div class="motion-title">${esc(t.icon || '📜')} ${esc(p.title)}</div>${pill}</div>
        <div class="motion-sponsor">Tabled by ${esc(p.proposer_name)} &middot; ${esc(t.name || p.effect_type)}</div>`;
    };

    const container = document.getElementById('pending-motions-list');
    if (container) {
      setHtml(container, open.length ? open.map(p => {
        const support = p.support_list || [];
        const count = p.support_count ?? support.length;
        const qualified = count >= 2 || p.is_qualified;
        const pill = qualified ? '<span class="status-pill ok">On the ballot</span>'
                               : '<span class="status-pill">Needs a co-sponsor</span>';
        let action;
        if (fromSpire(p)) {
          action = '<span class="section-sub">Put on the ballot by the Spire Council</span>';
        } else if (p.proposer_id === this.realmId) {
          action = `<span class="section-sub">Your motion.${qualified ? ' It goes to the next vote.' : ' Ask another nation to co-sponsor it.'}</span>`;
        } else if (support.includes(this.realmId)) {
          action = '<span class="section-sub">You co-sponsored this</span>';
        } else if (canEndorse(p)) {
          action = `<button class="btn btn-primary btn-block btn-sm" onclick="realmApp.supportProposal('${esc(p.id)}')">Co-sponsor this motion</button>`;
        } else if (p.target_seconder_id && p.target_seconder_id !== this.realmId) {
          action = '<span class="section-sub">Addressed to another nation</span>';
        } else {
          action = '';
        }
        const ask = p.target_seconder_id && !qualified
          ? `<div class="callout ${p.target_seconder_id === this.realmId ? 'warn' : 'neutral'} mt-1">${p.target_seconder_id === this.realmId ? 'Your nation has been asked to co-sponsor this.' : `Waiting for ${esc(p.target_seconder_name)} to co-sponsor.`}</div>` : '';
        return `<div class="motion-card">${head(p, pill)}${effectLine(p)}
          ${terms(p)}
          ${ask}<div class="mt-1">${action}</div></div>`;
      }).join('') : '<p class="empty-state">No motions on the floor yet.</p>');
    }


    const decidedCard = document.getElementById('decided-motions-card');
    const decidedList = document.getElementById('decided-motions-list');
    if (decidedCard && decidedList) {
      decidedCard.style.display = decided.length ? '' : 'none';
      setHtml(decidedList, decided.map(p => {
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
      }).join(''));
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

    const simple = (this.rules || {}).free_motions === false;
    const esc = escapeHtml;
    const docket = meta.plenary_docket || [];
    const idx = meta.current_motion_index || 0;
    const clock = meta.display_timer;
    const votes = realm.assembly_votes;
    const voteWord = `${votes} vote${votes === 1 ? '' : 's'}`;
    const passRule = `A motion passes when it has more votes for than against. Your nation has ${voteWord}.`;
    timerEl.innerText = clock && (clock.kind === 'vote' || clock.kind === 'debate')
      ? `${clock.running ? (clock.kind === 'vote' ? 'Voting closes in' : 'Debate') : 'Clock paused at'} ${formatSeconds(clock.seconds)}` : '';

    const voteCard = p => {
      const mine = (p.votes || {})[this.realmId];
      const verb = { support: 'for', oppose: 'against' }[mine ? mine.choice : ''];
      return `<div class="vote-card">
        <strong class="motion-title">${esc(p.title)}</strong>
        <div class="motion-sponsor">Tabled by ${esc(p.proposer_name)}</div>
        ${this._motionEffectHtml(p)}
        ${simple ? '' : `<details class="motion-terms"><summary>Read the terms</summary><p>${esc(p.description)}</p></details>`}
        ${mine ? `<div class="vote-cast">✓ ${verb ? `You voted ${verb} with ${mine.weight} vote${mine.weight === 1 ? '' : 's'}` : 'You abstained'}</div>` : `
        <div class="vote-buttons">
          <button class="btn btn-primary vote-for" onclick="realmApp.castPlenaryVote('${esc(p.id)}', 'support')">For</button>
          <button class="btn btn-danger vote-against" onclick="realmApp.castPlenaryVote('${esc(p.id)}', 'oppose')">Against</button>
          <button class="btn btn-secondary vote-abstain" onclick="realmApp.castPlenaryVote('${esc(p.id)}', 'abstain')">Abstain</button>
        </div>`}
      </div>`;
    };

    if (phase === 'plenary_quick') {
      const last = meta.current_turn >= (meta.max_turns || 3);
      const motions = proposals.filter(p => docket.includes(p.id));
      const left = motions.filter(p => !(p.votes || {})[this.realmId]).length;
      titleEl.innerText = last ? 'The final vote' : 'The Assembly votes';
      descEl.innerText = !motions.length ? '' : left ? `Vote on ${left === 1 ? 'this motion' : `all ${left} motions`}. ${passRule}` : 'All your votes are in. The result comes when voting closes.';
      setHtml(actionsContainer, motions.length ? motions.map(voteCard).join('') : '<p class="empty-state">No motion reached the ballot this time.</p>');
    } else if (phase === 'grand_plenary_discussion') {
      const motion = proposals.find(p => p.id === docket[idx]);
      titleEl.innerText = `Grand Plenary: motion ${idx + 1} of ${docket.length}`;
      descEl.innerText = 'Argue for or against it, out loud. Voting opens when the debate ends.';
      setHtml(actionsContainer, motion ? `<div class="vote-card">
        <strong class="motion-title">${esc(motion.title)}</strong>
        <div class="motion-sponsor">Tabled by ${esc(motion.proposer_name)}</div>
        ${this._motionEffectHtml(motion)}
        ${simple ? '' : `<p class="vote-terms">${esc(motion.description)}</p>`}
      </div>` : '');
    } else if (phase === 'grand_plenary_voting') {
      const motion = proposals.find(p => p.id === docket[idx]);
      titleEl.innerText = `Grand Plenary: vote on motion ${idx + 1} of ${docket.length}`;
      descEl.innerText = passRule;
      setHtml(actionsContainer, motion ? voteCard(motion) : '');
    } else if (phase === 'turn_summary') {
      const last = meta.current_turn >= (meta.max_turns || 3);
      titleEl.innerText = 'The vote is over';
      descEl.innerText = last ? 'The results are coming.' : 'The next turn starts soon. See the Motions tab for how it went.';
      timerEl.innerText = '';
      setHtml(actionsContainer, '');
    }
  }

  bindEvents() {
    const toggleAgendaBtn = document.getElementById('toggle-agenda-btn');
    const agendaContent = document.getElementById('agenda-content');
    if (toggleAgendaBtn && agendaContent) {
      toggleAgendaBtn.addEventListener('click', () => {
        agendaContent.classList.toggle('open');
        const isOpen = agendaContent.classList.contains('open');
        toggleAgendaBtn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
        toggleAgendaBtn.querySelector('.toggle-indicator').innerText = isOpen ? 'Hide' : 'Tap to read';
      });
    }

    // Tapping one of the nation's own numbers says what it is for.
    document.querySelectorAll('[data-explain]').forEach(el => {
      el.addEventListener('click', () => this.explain(el.dataset.explain));
    });

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

  // The offer in plain words, and anything that would stop it, before the player presses Send.
  updateTradePreview() {
    const el = document.getElementById('trade-preview-text');
    if (!el) return;
    const partner = document.getElementById('trade-receiver').value;
    const name = (this._realmNames || {})[partner];
    const g = document.getElementById('trade-offer-res').value, ga = parseInt(document.getElementById('trade-offer-amt').value, 10) || 0;
    const r = document.getElementById('trade-req-res').value, ra = parseInt(document.getElementById('trade-req-amt').value, 10) || 0;
    const me = this._me || {};
    const stock = { grain: me.alchemical_grain, cores: me.aether_cores, silk: me.echo_silk, military: me.military_power };
    const have = stock[g];
    this._setVal('trade-have', have === undefined ? '' : `You have ${have} ${RESOURCE_SHORT[g]}`);
    const givePart = `<b>${ga} ${RESOURCE_SHORT[g]}</b>`, getPart = `<b>${ra} ${RESOURCE_SHORT[r]}</b>`;
    let text, warn = '';
    if (!name) text = 'Choose a nation to trade with.';
    else if (!ga && !ra) text = 'Set how much you give or ask for.';
    else if (!ra) text = `You give ${givePart} to <b>${escapeHtml(name)}</b> as a gift.`;
    else if (!ga) text = `You ask <b>${escapeHtml(name)}</b> for ${getPart} and give nothing in return.`;
    else text = `You give ${givePart} to <b>${escapeHtml(name)}</b> and receive ${getPart}.`;
    if (have !== undefined && ga > have) warn = `You only have ${have} ${RESOURCE_SHORT[g]}.`;
    else if (name && this._round2 && ((g === 'grain' && ga) || (r === 'grain' && ra))) warn = 'The border crisis costs 5 Grain in transit on this trade.';
    setHtml(el, text + (warn ? `<div class="trade-warn">${escapeHtml(warn)}</div>` : ''));
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
    const word = { support: 'for', oppose: 'against' }[choice];
    const ok = await confirmAction({
      title: word ? `Vote ${word}?` : 'Abstain?',
      message: prop.title ? `“${prop.title}”` : '',
      details: !word ? ['You do not take a side. Your votes are not counted for or against.', 'A vote cannot be changed once cast.']
        : [`Your nation's ${votes} vote${votes === 1 ? '' : 's'} count ${word} the motion.`, 'A vote cannot be changed once cast.'],
      confirmLabel: word ? `Vote ${word}` : 'Abstain', tone: choice === 'oppose' ? 'danger' : undefined,
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
