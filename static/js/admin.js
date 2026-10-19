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
    this.renderRoster(state.realms || []);
    const { meta, realms, proposals, news_feed } = state;

    // Header Pills
    const turnEl = document.getElementById('admin-turn-display');
    if (turnEl) turnEl.innerText = `TURN ${meta.current_turn}`;

    const timerEl = document.getElementById('admin-timer-display');
    if (timerEl) {
      timerEl.innerText = formatSeconds(meta.display_timer ? meta.display_timer.seconds : meta.turn_timer_remaining);
      timerEl.title = meta.display_timer ? meta.display_timer.label : '';
    }
    // The clock console follows whichever clock the current phase has
    const clock = meta.display_timer || { label: 'Clock', seconds: 0, running: false };
    this._text('clock-label', clock.label);
    this._text('clock-big', formatSeconds(clock.seconds));
    const big = document.getElementById('clock-big');
    if (big) big.classList.toggle('stopped', !clock.running);
    const stateEl = document.getElementById('clock-state');
    if (stateEl) { stateEl.innerText = clock.running ? 'running' : 'stopped'; stateEl.classList.toggle('run', !!clock.running); }
    const weather = meta.weather;
    const settings = state.game_settings || {};
    this._text('admin-weather', weather
      ? `Weather this turn: ${weather.name}. ${settings.attacks_enabled === false ? 'Attacks are switched off.' : `Attacks unlock in Turn ${settings.attacks_from_turn || 2}.`}` : '');
    this._realms = realms;


    // Tab 1: Pacing & Plenary Phase
    const phaseDisplay = document.getElementById('admin-phase-display');
    const controlsContainer = document.getElementById('admin-plenary-controls');

    if (phaseDisplay && controlsContainer) {
      if (meta.phase === 'working') {
        phaseDisplay.innerText = meta.intermission_end ? `TURN ${meta.current_turn} STARTS SOON` : `WORKING SESSION · TURN ${meta.current_turn}`;
        controlsContainer.innerHTML = `
          <button class="btn btn-primary btn-sm" onclick="adminApp.startPlenary()">
            ⚡ Convene Between-Rounds Plenary
          </button>
        `;
      } else if (meta.phase === 'plenary_quick') {
        phaseDisplay.innerText = `BETWEEN-ROUNDS PLENARY: QUICK VOTE`;
        controlsContainer.innerHTML = `
          <button class="btn btn-primary btn-sm" onclick="adminApp.concludeQuickPlenary()">
            Settle Plenary &amp; End Turn
          </button>
        `;
      } else if (meta.phase === 'grand_plenary_discussion') {
        phaseDisplay.innerText = `GRAND PLENARY: FLOOR DEBATE`;
        controlsContainer.innerHTML = `
          <button class="btn btn-secondary btn-sm" onclick="adminApp.controlDiscussionTimer('start')">▶ Start Debate</button>
          <button class="btn btn-secondary btn-sm" onclick="adminApp.controlDiscussionTimer('pause')">⏸ Pause</button>
          <button class="btn btn-primary btn-sm" onclick="adminApp.callGrandVote()">🗳️ Call Sovereign Vote Now</button>
        `;
      } else if (meta.phase === 'grand_plenary_voting') {
        phaseDisplay.innerText = `GRAND PLENARY: SOVEREIGN VOTE ACTIVE`;
        controlsContainer.innerHTML = `
          <button class="btn btn-primary btn-sm" onclick="adminApp.nextGrandMotion()">
            Next Motion in Docket
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
              Advance to Next Turn
            </button>
          `;
        }
      } else if (meta.phase === 'summit_concluded') {
        const total = (state.reflection_questions || []).length;
        const step = meta.reflection_step;
        const reflecting = step !== null && step !== undefined;
        phaseDisplay.innerText = reflecting ? `REFLECTION: QUESTION ${step + 1} OF ${total}` : `SUMMIT CONCLUDED: RESULTS ON THE PROJECTOR`;
        controlsContainer.innerHTML = reflecting ? `
          <button class="btn btn-secondary btn-sm" onclick="adminApp.setReflection(${step - 1})" ${step === 0 ? 'disabled' : ''}>&larr; Previous</button>
          <button class="btn btn-primary btn-sm" onclick="adminApp.setReflection(${step + 1})" ${step >= total - 1 ? 'disabled' : ''}>Next question &rarr;</button>
          <button class="btn btn-secondary btn-sm" onclick="adminApp.setReflection(null)">Show results</button>
          <button class="btn btn-secondary btn-sm" onclick="adminApp.downloadReport()">Download results</button>
        ` : `
          <button class="btn btn-primary btn-sm" onclick="adminApp.setReflection(0)">Start reflection (${total} questions)</button>
          <button class="btn btn-secondary btn-sm" onclick="adminApp.downloadReport()">Download results</button>
          <button class="btn btn-danger btn-sm" onclick="adminApp.openResetModal()">↺ Reset Simulation</button>
        `;
      }
    }

    // Tab 3: Resource Telemetry Table (type a number and press Enter, or use +/-)
    this.renderBulkNations(realms);
    this.renderBulkPreview();
    const tableBody = document.getElementById('admin-realms-tbody');
    if (tableBody && !tableBody.contains(document.activeElement)) {       // never rebuild while someone is typing
      const cols = [['alchemical_grain', 'Grain'], ['aether_cores', 'Cores'], ['echo_silk', 'Silk'], ['military_power', 'Military'],
                    ['public_vitality', 'Vitality'], ['diplomatic_standing', 'Standing'], ['civil_stability', 'Stability']];
      const esc = escapeHtml;
      const html = realms.map(r => `
        <tr style="${r.active === false ? 'opacity:0.5;' : ''}">
          <td>
            <div style="display:flex; align-items:center; gap: 8px;">
              <strong>${esc(r.name)}</strong>
              ${r.is_plutocrat ? '<span class="badge">[RICHEST]</span>' : ''}
              ${r.is_starving ? '<span class="badge badge-danger">[STARVING]</span>' : ''}
            </div>
            <div class="section-sub" style="margin-top:2px;" title="Spireopedia quiz: correct / wrong">QUIZ ${(r.claimed_lore || []).length} ✓ · ${(r.failed_lore || []).length} ✗</div>
          </td>
          ${cols.map(([field, label]) => `<td>
            <div class="inline-num-ctrl">
              <button class="inline-num-btn" onclick="adminApp.adjustStat('${esc(r.id)}', '${field}', -5)">-</button>
              <input type="number" class="inline-num-input" value="${r[field] ?? 0}" data-realm="${esc(r.id)}" data-field="${field}" data-label="${label}" data-name="${esc(r.name)}"
                     data-old="${r[field] ?? 0}" min="0" ${['public_vitality', 'diplomatic_standing', 'civil_stability'].includes(field) ? 'max="100"' : ''}
                     onchange="adminApp.setStatTyped(this)" onkeydown="if (event.key === 'Enter') { event.preventDefault(); this.blur(); }" aria-label="${esc(r.name)} ${label}">
              <button class="inline-num-btn" onclick="adminApp.adjustStat('${esc(r.id)}', '${field}', 5)">+</button>
            </div></td>`).join('')}
          <td><span class="badge">${r.assembly_votes} VOTES</span></td>
          <td><button class="btn btn-secondary btn-sm" onclick="adminApp.editRealmModal('${esc(r.id)}')">Edit</button></td>
        </tr>`).join('');
      if (html !== this._tableHtml) { this._tableHtml = html; tableBody.innerHTML = html; }
    }

    // Tab 4: questions to the game masters, then floor resolutions
    this.renderQuestionInbox(proposals);
    const motions = proposals;
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
    const resList = document.getElementById('admin-resolutions-list');
    if (resList) {
      if (motions.length === 0) {
        resList.innerHTML = '<p class="text-muted" style="font-size:0.8rem; font-family:var(--font-mono);">No floor resolutions registered.</p>';
      } else {
        resList.innerHTML = motions.map(p => {
          const qual = p.support_list.length >= 2 || p.is_qualified;
          const t = types[p.effect_type] || {};
          return `
            <div style="background:var(--bg-surface-sunken); border:1px solid var(--border-subtle); padding:12px; border-radius:4px;">
              <div style="display:flex; justify-content:space-between; align-items:center;">
                <strong style="font-size:0.95rem;">${esc(t.icon || '📜')} ${esc(p.title)}</strong>
                <span class="badge" style="border-color:${qual ? '#fff' : 'var(--border-subtle)'};">
                  ${qual ? 'QUALIFIED FOR PLENARY' : `AWAITING ENDORSEMENT (${p.support_list.length}/2)`}
                </span>
              </div>
              <div style="font-size:0.75rem; font-family:var(--font-mono); color:var(--text-muted); margin:4px 0;">
                Template: ${esc(t.name || p.effect_type)} | Sponsor: ${esc(p.proposer_name)} | Co-Sponsors: ${(p.supporters || []).map(s => esc(s.name)).join(', ')}
              </div>
              <p style="font-size:0.82rem; color:var(--text-secondary); white-space:pre-line;">${esc(p.description)}</p>
              ${this._effectBlock(p, t)}
              ${p.answer ? `<div class="callout ok mt-1"><b>Game masters' answer:</b> ${esc(p.answer)}</div>` : ''}
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
      pinsTbody.innerHTML = realms.map(r => {
        const isActive = r.active !== false;
        const pCount = r.player_count || 1;
        const activeMissionsCount = (r.active_secret_missions || []).length;
        const connCount = r.connected_players || 0;
        const isFull = !!r.is_capacity_full;
        return `
        <tr style="${isActive ? '' : 'opacity: 0.55; background: rgba(120, 90, 40, 0.04);'}">
          <td>
            <div style="display:flex; align-items:center; gap:6px;">
              <span style="font-size:1.1rem;">${r.emoji || '🏛️'}</span>
              <strong>${r.name}</strong>
            </div>
            <div style="font-size:0.7rem; color:var(--text-muted);">${r.ethos}</div>
          </td>
          <td>
            <button class="btn ${isActive ? 'btn-primary' : 'btn-secondary'} btn-sm" style="font-size:0.7rem; padding:3px 8px;" onclick="adminApp.toggleRealm('${r.id}', ${isActive})">
              ${isActive ? '🟢 Active' : '⚪ Inactive'}
            </button>
          </td>
          <td>
            <div style="display:flex; align-items:center; gap:6px;">
              <span class="badge" style="font-size:0.75rem; font-family:var(--font-mono); ${isFull ? 'background:rgba(239,68,68,0.2); color:#f87171;' : 'background:rgba(59,130,246,0.15); color:#93c5fd;'}">
                👥 ${connCount} / ${pCount} ${isFull ? '[FULL]' : ''}
              </span>
              <button class="btn btn-secondary btn-sm" style="padding: 2px 6px; font-size:0.7rem;" onclick="adminApp.clearRealmSessions('${r.id}', '${r.name}')" title="Reset/Clear active sessions for this realm">↺</button>
            </div>
          </td>
          <td>
            <select class="form-select" style="font-size:0.75rem; padding:3px 6px; width:105px;" onchange="adminApp.setPlayerCount('${r.id}', this.value)">
              <option value="1" ${pCount === 1 ? 'selected' : ''}>1 Delegate</option>
              <option value="2" ${pCount === 2 ? 'selected' : ''}>2 Delegates</option>
              <option value="3" ${pCount === 3 ? 'selected' : ''}>3 Delegates</option>
              <option value="4" ${pCount === 4 ? 'selected' : ''}>4 Delegates</option>
            </select>
          </td>
          <td>
            <span class="badge" style="font-family:var(--font-mono); font-size:0.75rem;">
              ${activeMissionsCount} Secret (${activeMissionsCount} pts)
            </span>
          </td>
          <td>
            <span class="badge" style="font-size:0.85rem; font-family:var(--font-mono);">${r.pin || '1001'}</span>
          </td>
          <td>
            <div style="display:flex; gap:4px;">
              <button class="btn btn-secondary btn-sm" onclick="adminApp.promptChangePin('${r.id}', '${r.name}')">PIN</button>
              <button class="btn btn-danger btn-sm" onclick="adminApp.removeRealm('${r.id}', '${r.name}')" title="Remove Delegation">✕</button>
            </div>
          </td>
        </tr>
      `;
      }).join('');
    }

    this.renderWarLog(state.battles || [], settings);
    this.renderSieges(state.sieges || []);

    // News Audit Log
    const newsBox = document.getElementById('admin-news-feed');
    if (newsBox && news_feed) {
      newsBox.innerHTML = news_feed.slice(0, 15).map(n => `
        <div style="border-bottom: 1px solid var(--border-subtle); padding: 8px 0; font-size: 0.8rem;">
          <div style="display:flex; justify-content:space-between; font-family:var(--font-mono); font-size:0.72rem; color: var(--text-muted);">
            <strong style="color: var(--text-primary);">[${escapeHtml(n.type.toUpperCase())}] ${escapeHtml(n.headline)}</strong>
            <span>${escapeHtml(n.time_str)}</span>
          </div>
          <p style="color: var(--text-secondary); margin-top: 2px;">${escapeHtml(n.detail)}</p>
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

  async advanceTurn() {
    if (!(await confirmAction({ title: 'End this turn?', message: 'Nations eat, round rules apply and the next turn is prepared. Settle the Assembly first if motions are waiting.', confirmLabel: 'End the turn' }))) return;
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
    if (!(await confirmAction({ title: `Change the passcode of ${realmName}?`, message: `New passcode: ${newPin.trim()}. Phones logged in with the old one keep working until they reconnect.`, confirmLabel: 'Change passcode' }))) return;

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
    if (!(await confirmAction({ title: 'Broadcast this dispatch?', message: document.getElementById('admin-news-headline').value, confirmLabel: 'Broadcast' }))) return;
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
    if (!(await confirmAction({ title: 'Inject the next recommended crisis?', message: 'It is announced to everyone and applied at once.', confirmLabel: 'Inject it', tone: 'danger' }))) return;
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
    const sel = document.getElementById('catalog-event-select');
    if (!sel || !sel.value) return;
    if (!(await confirmAction({ title: 'Inject this crisis?', message: sel.options[sel.selectedIndex].text, confirmLabel: 'Inject it', tone: 'danger' }))) return;
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
    if (!(await confirmAction({ title: 'End the summit?', message: 'Results are counted and shown on the projector. After this, trades, motions and the quiz are closed.', confirmLabel: 'End the summit', tone: 'danger' }))) return;
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

  renderRoster(realms) {
    const box = document.getElementById('roster-chips');
    if (!box) return;
    const playing = realms.filter(r => r.active !== false).length;
    const count = document.getElementById('roster-count');
    if (count) count.innerText = `· ${playing} of ${realms.length} playing`;
    const key = realms.map(r => `${r.id}:${r.active !== false}:${r.connected_players || 0}`).join(',');
    if (key === this._rosterKey) return;
    this._rosterKey = key;
    box.innerHTML = realms.map(r => {
      const on = r.active !== false;
      return `<button type="button" class="roster-chip ${on ? 'on' : ''}" style="--nc:${escapeHtml(r.theme_color || '#8c7a5e')}"
          onclick="adminApp.toggleRealm('${escapeHtml(r.id)}', ${on})" title="${on ? 'Remove from' : 'Add to'} this summit">
          <span class="crest small">${escapeHtml(r.emoji || '🏛️')}</span>
          <span><b>${escapeHtml(r.name)}</b><em>${on ? `${r.connected_players || 0}/${r.player_count} seats taken` : 'Not playing'}</em></span>
        </button>`;
    }).join('');
  }

  // ---------------------------------------------------------------------------
  // Saves: server autosaves + copies in this browser (survive a server restart)
  // ---------------------------------------------------------------------------
  initSaves() {
    this.refreshSaves();
    this.keepBrowserCopy();
    setInterval(() => this.keepBrowserCopy(), 5 * 60 * 1000);
    setInterval(() => this.refreshSaves(), 60 * 1000);
  }

  _browserSaves() {
    try { return JSON.parse(localStorage.getItem('summit_saves') || '[]'); } catch (e) { return []; }
  }

  async keepBrowserCopy(label = 'Autosave') {
    try {
      const res = await (await fetch('/api/admin/save/export')).json();
      if (!res.success) return;
      const meta = res.snapshot.meta || {};
      const saves = this._browserSaves();
      saves.unshift({ created: Date.now() / 1000, label: `${label} · Turn ${meta.current_turn || 1}`, snapshot: res.snapshot });
      try { localStorage.setItem('summit_saves', JSON.stringify(saves.slice(0, 6))); } catch (e) {}
      this.renderBrowserSaves();
    } catch (e) { /* offline for a moment: try again next time */ }
  }

  async refreshSaves() {
    try {
      const res = await (await fetch('/api/admin/saves')).json();
      const box = document.getElementById('server-saves');
      if (!box || !res.success) return;
      box.innerHTML = res.saves.length ? res.saves.map(s => this._saveRow(s.label, s.created,
        `adminApp.restoreServerSave(${s.id})`, `adminApp.downloadSave(${s.id})`)).join('')
        : '<p class="empty-state">No saves yet. The first autosave happens within 5 minutes.</p>';
      const status = document.getElementById('save-status');
      if (status && res.saves[0]) status.innerText = `Last server save: ${new Date(res.saves[0].created * 1000).toLocaleTimeString()}`;
    } catch (e) {}
    this.renderBrowserSaves();
  }

  renderBrowserSaves() {
    const box = document.getElementById('browser-saves');
    if (!box) return;
    const saves = this._browserSaves();
    box.innerHTML = saves.length ? saves.map((s, i) => this._saveRow(s.label, s.created,
      `adminApp.restoreBrowserSave(${i})`, null)).join('') : '<p class="empty-state">None yet.</p>';
  }

  _saveRow(label, created, restoreJs, downloadJs) {
    const when = new Date(created * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    return `<div class="inset row-between"><div><b>${escapeHtml(label)}</b><div class="section-sub" style="margin:0;">${when}</div></div>
      <div class="row">${downloadJs ? `<button class="btn btn-secondary btn-sm" onclick="${downloadJs}">Download</button>` : ''}
      <button class="btn btn-secondary btn-sm" onclick="${restoreJs}">Restore</button></div></div>`;
  }

  async saveNow() {
    const res = await (await fetch('/api/admin/save/now', { method: 'POST' })).json();
    showToast(res.message || 'Saved', res.success ? 'success' : 'danger');
    await this.keepBrowserCopy('Manual save');
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

  async _restore(body) {
    if (!(await confirmAction({ title: 'Restore this save?', message: 'The current game is replaced (a "Before restore" save is kept on the server).', confirmLabel: 'Restore', tone: 'danger' }))) return;
    const res = await (await fetch('/api/admin/save/restore', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
    })).json();
    showToast(res.message, res.success ? 'success' : 'danger');
    this.refreshSaves();
    this.pollState();
  }

  restoreServerSave(id) { return this._restore({ id }); }

  restoreBrowserSave(i) {
    const s = this._browserSaves()[i];
    if (s) return this._restore({ snapshot: s.snapshot });
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
      </div>`).join('') : '<p class="empty-state">No questions yet.</p>';
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
    this._modNations = res.nations;
    box.innerHTML = res.nations.map(n => {
      const lim = n.limits;
      const field = (key, hint) => `<label class="mod-field"><span>${esc(lim[key][2])}</span>
        <input type="number" class="form-input" id="mod-${esc(n.id)}-${key}" value="${n.manual[key]}" min="${lim[key][0]}" max="${lim[key][1]}" step="1">
        <small>${hint}</small></label>`;
      const flag = (key, label) => `<label class="mod-flag"><input type="checkbox" id="mod-${esc(n.id)}-${key}" ${n.flags[key] ? 'checked' : ''}> ${label}</label>`;
      return `<div class="inset mod-card">
        <div class="row-between"><b>${esc(n.emoji)} ${esc(n.name)}</b>
          <span class="section-sub" style="margin:0;">${n.votes.total} votes · eats ${n.grain_use} Grain a turn · readiness ×${n.war.readiness}</span></div>
        ${n.automatic.length ? `<ul class="mod-auto">${n.automatic.map(a => `<li>${esc(a)}</li>`).join('')}</ul>` : '<div class="section-sub">No automatic modifiers.</div>'}
        <div class="mod-grid">
          ${field('votes', `Base ${n.votes.base}${n.votes.richest ? ' + 1 richest' : ''}; added to these`)}
          ${field('grain_use_pct', 'Percent more or less than usual')}
          ${field('war_power_pct', 'Percent, hidden from players')}
          ${field('war_defence_pct', 'Percent, only when attacked')}
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
    for (const key of Object.keys(n.limits)) manual[key] = parseInt(document.getElementById(`mod-${id}-${key}`).value, 10) || 0;
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
    if (!(await confirmAction({ title: currentActive ? `Remove ${nm} from the summit?` : `Bring ${nm} into the summit?`,
      message: 'Missions, quotas, votes, trade lists and the projector adjust at once.', confirmLabel: currentActive ? 'Remove' : 'Bring in', tone: currentActive ? 'danger' : undefined }))) return;
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

  async setPlayerCount(realmId, count) {
    const nm = ((this._realms || []).find(r => r.id === realmId) || {}).name || 'this nation';
    if (!(await confirmAction({ title: `Seat ${count} delegate${Number(count) === 1 ? '' : 's'} for ${nm}?`, message: 'Each delegate brings one secret mission, as far as the nation has them.', confirmLabel: 'Change seats' }))) return;
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

  async removeRealm(realmId, realmName) {
    if (!(await confirmAction({ title: `Remove ${realmName} for good?`, message: 'Active delegations, quotas and missions are recalculated.', confirmLabel: 'Remove it', tone: 'danger' }))) return;

    try {
      const resp = await fetch('/api/admin/realm/remove', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ realm_id: realmId })
      });
      const res = await resp.json();
      if (res.success) {
        showToast(res.message, 'info');
        synth.playAlert();
        this.pollState();
      } else {
        showToast(res.message || 'Failed to remove realm', 'danger');
      }
    } catch (err) {
      showToast('Network error while removing delegation', 'danger');
    }
  }

  async setActiveRealmCount(count) {
    if (!(await confirmAction({ title: `Play with ${count} nations?`, message: `The first ${count} standard nations take part; missions and voting quotas scale accordingly.`, confirmLabel: `Use ${count} nations` }))) return;

    try {
      const resp = await fetch('/api/admin/realms/set_count', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ count: parseInt(count, 10) })
      });
      const res = await resp.json();
      if (res.success) {
        showToast(res.message, 'info');
        synth.playChime();
        this.pollState();
      } else {
        showToast(res.message || 'Failed to set nation count', 'danger');
      }
    } catch (err) {
      showToast('Network error while configuring nation count', 'danger');
    }
  }

  async clearRealmSessions(realmId, realmName) {
    const targetLabel = realmName || (realmId ? `delegation ${realmId}` : 'all delegations');
    if (!(await confirmAction({ title: `Clear the sessions of ${targetLabel}?`, message: 'This frees the seats so participants can reconnect.', confirmLabel: 'Clear sessions' }))) return;

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
        showToast(res.message || 'Failed to clear sessions', 'danger');
      }
    } catch (err) {
      showToast('Network error while clearing sessions', 'danger');
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
    box.innerHTML = lines.length
      ? `<b>This would change:</b><br>${lines.map(escapeHtml).join('<br>')}`
      : '<span class="muted">Tick the nations to change.</span>';
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
      <div class="small muted" style="margin-top:4px;">Entered something wrong? Reverse the resource changes in Resource Overrides → Action log.</div>
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
