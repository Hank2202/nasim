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
            <div class="section-sub" style="margin-top:2px;" title="Spireopedia quiz: correct / wrong">QUIZ ${(r.claimed_lore || []).length} ✓ · ${(r.failed_lore || []).length} ✗</div>
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
              <span class="inline-num-val">${r.military_power ?? 0}</span>
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

    // Tab 4: questions to the game masters, then floor resolutions
    this.renderQuestionInbox(proposals);
    const motions = proposals;
    const resList = document.getElementById('admin-resolutions-list');
    if (resList) {
      if (motions.length === 0) {
        resList.innerHTML = '<p class="text-muted" style="font-size:0.8rem; font-family:var(--font-mono);">No floor resolutions registered.</p>';
      } else {
        resList.innerHTML = motions.map(p => {
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

    // News Audit Log
    const newsBox = document.getElementById('admin-news-feed');
    if (newsBox && news_feed) {
      newsBox.innerHTML = news_feed.slice(0, 15).map(n => `
        <div style="border-bottom: 1px solid var(--border-subtle); padding: 8px 0; font-size: 0.8rem;">
          <div style="display:flex; justify-content:space-between; font-family:var(--font-mono); font-size:0.72rem; color: var(--text-muted);">
            <strong style="color: var(--text-primary);">[${n.type.toUpperCase()}] ${n.headline}</strong>
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

  async minorEvent(tone) {
    const res = await (await fetch('/api/admin/event/minor', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ tone })
    })).json();
    showToast(res.message, res.success ? 'info' : 'danger');
    this.pollState();
  }

  async largeEvent() {
    if (!confirm('Strike a random nation with a large disaster now?')) return;
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
    if (!confirm('Restore this save? The current game is replaced (a "Before restore" save is kept on the server).')) return;
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
    const questions = proposals.filter(p => p.effect_type === 'gm_question');
    const toAnswer = questions.filter(p => p.status === 'passed' && !p.answer);
    const badge = document.getElementById('gm-tab-badge');
    if (badge) { badge.innerText = toAnswer.length; badge.style.display = toAnswer.length ? 'inline-block' : 'none'; }
    const count = document.getElementById('gm-inbox-count');
    if (count) count.innerText = toAnswer.length ? `· ${toAnswer.length} to answer` : '';
    const box = document.getElementById('gm-inbox');
    if (!box) return;
    // Re-render only when questions change, so an answer being typed is not wiped by the 1-second refresh.
    const key = questions.map(p => `${p.id}:${p.status}:${p.answer ? 1 : 0}`).join(',');
    if (key === this._inboxKey) return;
    if (this._inboxKey !== undefined && toAnswer.some(p => !this._inboxKey.includes(`${p.id}:passed`))) {
      showToast('The Assembly passed a question for the game masters', 'info');
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
        <div style="font-weight:600; margin-top:4px;">${esc(p.title)}</div>
        <p class="small" style="white-space:pre-line; margin-top:2px;">${esc(p.description)}</p>
        ${p.answer ? `<div class="callout ok mt-1"><b>Answered:</b> ${esc(p.answer)}</div>`
          : p.status === 'passed' ? `
        <div class="callout warn mt-1">Passed by the Assembly: please answer. Everyone sees the answer.</div>
        <textarea class="form-textarea mt-1" rows="2" id="answer-${esc(p.id)}" placeholder="Your answer…"></textarea>
        <button class="btn btn-primary btn-sm mt-1" onclick="adminApp.answerQuestion('${esc(p.id)}')">Publish answer</button>`
          : `<div class="section-sub mt-1">${stateLine(p)}</div>`}
      </div>`).join('') : '<p class="empty-state">No questions yet.</p>';
  }

  async answerQuestion(id) {
    const answer = (document.getElementById(`answer-${id}`) || {}).value || '';
    const res = await (await fetch('/api/admin/question/answer', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id, answer })
    })).json();
    showToast(res.message, res.success ? 'success' : 'danger');
    this.pollState();
  }

  async toggleRealm(realmId, currentActive) {
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
    if (!confirm(`Are you sure you want to permanently remove ${realmName} from the summit?\n\nThis will recalculate active delegations, continental quotas, and mission parameters.`)) return;

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
    if (!confirm(`Configure the summit to ${count} active sovereign nations?\n\nThis will activate the first ${count} standard nations and scale all missions and voting quotas accordingly.`)) return;

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
    if (!confirm(`Clear connected sessions for ${targetLabel}?\n\nThis frees active seats so participants can reconnect.`)) return;

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
