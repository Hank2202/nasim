/**
 * The Summit of Realms - projector screen (ProjectorApp)
 */
'use strict';

// -----------------------------------------------------------------------------
// Projector Overview Screen Logic (ProjectorApp)
// -----------------------------------------------------------------------------
class ProjectorApp {
  constructor() {
    this.isPolling = false;
    this.lastAudioSeq = null;
  }

  start() {
    const mapCanvas = document.getElementById('realm-map');
    if (mapCanvas && window.LivingAtlas) {
      this.map = new window.LivingAtlas(mapCanvas);
      // The sidebar follows whichever nation the map visits (tour, click or chip).
      this.map.onFocus = id => {
        if (!id) return;                      // whole-continent view keeps the last nation in the sidebar
        this.spotlightId = id;
        if (this.lastRealms) this.renderSpotlight(this.lastRealms);
      };
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

    if (this.map) this.map.update(state);
    this.watchBattles(state.battles || []);
    this.renderSieges(state.sieges || []);
    this.renderTicker(news_feed || []);
    this.resolutionTypes = state.resolution_types || this.resolutionTypes;
    this.renderTimeline(meta);

    // Header
    const turnEl = document.getElementById('proj-turn');
    if (turnEl) {
      let phaseLabel = 'WORKING SESSION';
      if (meta.phase === 'plenary_quick') phaseLabel = 'BETWEEN-ROUNDS PLENARY';
      else if (meta.phase === 'grand_plenary_discussion') phaseLabel = 'GRAND PLENARY: DEBATE';
      else if (meta.phase === 'grand_plenary_voting') phaseLabel = 'GRAND PLENARY: VOTE';
      else if (meta.phase === 'turn_summary') phaseLabel = 'PLENARY CONCLUDED';
      else if (meta.phase === 'summit_concluded') phaseLabel = 'SUMMIT CONCLUDED';
      if (meta.phase === 'working' && meta.intermission_end) phaseLabel = 'NEXT TURN STARTS SOON';
      turnEl.innerText = `TURN ${meta.current_turn} • ${phaseLabel}`;
    }

    const timerEl = document.getElementById('proj-timer');
    if (timerEl) {
      timerEl.innerText = formatSeconds(meta.display_timer ? meta.display_timer.seconds : meta.turn_timer_remaining);
      timerEl.title = meta.display_timer ? meta.display_timer.label : '';
    }

    // Audio cues
    if (meta.audio_cue && meta.audio_cue.seq !== undefined) {
      if (this.lastAudioSeq !== null && meta.audio_cue.seq > this.lastAudioSeq) {
        if (meta.audio_cue.type === 'gong' || meta.audio_cue.type === 'turn') synth.playGong();
        else if (meta.audio_cue.type === 'chime' || meta.audio_cue.type === 'trade') synth.playChime();
        else if (meta.audio_cue.type === 'alert') synth.playAlert();
        else if (meta.audio_cue.type === 'battle') synth.playBattle();
      }
      this.lastAudioSeq = meta.audio_cue.seq;
    }

    // Phase Layout Dispatcher
    const mainLayout = document.getElementById('proj-main-layout');
    const quickStage = document.getElementById('proj-quick-plenary-stage');
    const grandStage = document.getElementById('proj-grand-plenary-stage');
    const concludedStage = document.getElementById('proj-concluded-stage');

    const reflectionStage = document.getElementById('proj-reflection-stage');
    const reflecting = meta.phase === 'summit_concluded' && meta.reflection_step !== null && meta.reflection_step !== undefined;
    if (reflectionStage) reflectionStage.style.display = reflecting ? 'flex' : 'none';
    if (reflecting) {
      [mainLayout, quickStage, grandStage, concludedStage].forEach(el => { if (el) el.style.display = 'none'; });
      this.renderReflection(meta.reflection_step, state);
    } else if (meta.phase === 'summit_concluded') {
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
      if (mainLayout) mainLayout.style.display = 'grid';
      this.renderWorkingSession(meta, proposals, realms, news_feed);
    }
  }

  // What the game does if a motion passes, in the words written when it was tabled.
  effectInner(p, type) {
    const esc = escapeHtml;
    const lines = (p.effect_text && p.effect_text.length) ? p.effect_text : [type.effect_plain].filter(Boolean);
    return lines.length ? `<span>If passed:</span> ${lines.map(esc).join(' ')}` : '';
  }

  effectHtml(p, type) {
    const inner = this.effectInner(p, type);
    return inner ? `<div class="motion-effect">${inner}</div>` : '';
  }

  // Armies on the road: a banner above the focused nation, counting down to the arrival.
  renderSieges(sieges) {
    const box = document.getElementById('siege-banner');
    if (!box) return;
    const esc = escapeHtml;
    const html = sieges.map(s => `<div class="siege-row" style="--nc:${esc(s.attacker_color || '#8c7a5e')}">
      <span>🏰 <b>${esc(s.attacker_emoji)} ${esc(s.attacker_name)}</b> marches on <b>${esc(s.defender_emoji)} ${esc(s.defender_name)}</b></span>
      <b class="siege-eta">${Math.floor(s.eta / 60)}:${String(s.eta % 60).padStart(2, '0')}</b></div>`).join('');
    if (html !== this._siegeHtml) { this._siegeHtml = html; box.innerHTML = html; }
  }

  // Battles take over the "Realm in Focus" panel, one after another, for about eleven seconds each.
  watchBattles(battles) {
    if (this._seenBattles === undefined) {                 // first poll: older battles are not replayed
      this._seenBattles = new Set(battles.map(b => b.id));
      this._battleQueue = [];
      return;
    }
    for (const b of battles.slice().reverse()) {
      if (this._seenBattles.has(b.id)) continue;
      this._seenBattles.add(b.id);
      this._battleQueue.push(b);
      if (this.map && this.map.addWar) this.map.addWar(b.attacker_id, b.defender_id, b.outcome);
    }
    if (!this._battleShowing) this.nextBattle();
  }

  nextBattle() {
    const stage = document.getElementById('battle-stage');
    const panel = document.querySelector('.atlas-side');
    const b = this._battleQueue.shift();
    if (!stage || !panel || !b) {
      this._battleShowing = false;
      if (panel) panel.classList.remove('battling');
      return;
    }
    this._battleShowing = true;
    stage.innerHTML = '<div class="battle-pop-inner"></div>';
    panel.classList.add('battling');
    const heading = panel.querySelector('.atlas-heading');
    if (heading) heading.dataset.normal = heading.dataset.normal || heading.innerHTML;
    if (heading) heading.innerHTML = '<span class="flourish">&#9876;</span> Battle <span class="flourish">&#9876;</span>';
    if (this._battleScene) this._battleScene.stop();
    this._battleScene = BattleScene.play(stage.firstElementChild, b, {
      tall: true,
      duration: 15000,
      onDone: () => {
        if (!this._battleQueue.length) {
          panel.classList.remove('battling');
          if (heading && heading.dataset.normal) heading.innerHTML = heading.dataset.normal;
          stage.innerHTML = '';
        }
        setTimeout(() => this.nextBattle(), 400);
      },
    });
  }

  renderSummitConcluded(outcome, proposals, news_feed) {
    if (!outcome) return;

    const verdictTitle = document.getElementById('proj-verdict-title');
    const verdictDesc = document.getElementById('proj-verdict-desc');
    const timestampEl = document.getElementById('proj-concluded-timestamp');
    const badgesEl = document.getElementById('proj-verdict-badges');

    if (verdictTitle) verdictTitle.innerText = outcome.continental_verdict;
    let verdictColor = '#ef4444';
    let verdictIcon = '🔴';
    if (outcome.continental_verdict === 'STABLE CONTINENT') {
      verdictColor = '#10b981';
      verdictIcon = '🟢';
    } else if (outcome.continental_verdict === 'FRAGILE PEACE') {
      verdictColor = '#f59e0b';
      verdictIcon = '🟡';
    }

    if (verdictTitle) verdictTitle.style.color = verdictColor;
    if (verdictDesc) verdictDesc.innerText = outcome.continental_desc;
    if (timestampEl) timestampEl.innerText = `CONCLUDED: ${outcome.concluded_time_str}`;

    if (badgesEl) {
      badgesEl.innerHTML = `
        <span class="badge" style="background:${verdictColor}; color:#fff; padding:4px 10px; font-weight:800;">
          CONTINENTAL OUTCOME: ${outcome.continental_verdict}
        </span>
        <span class="badge" style="background:var(--text-primary); color:var(--bg-surface); padding:4px 10px;">AVERAGE STANDING: ${outcome.avg_standing || 50}%</span>
        <span class="badge" style="background:var(--text-primary); color:var(--bg-surface); padding:4px 10px;">AVERAGE STABILITY: ${outcome.avg_stability}%</span>
        <span class="badge" style="${outcome.starving_count > 0 ? 'background:#ef4444; color:#fff;' : 'background:var(--text-primary); color:var(--bg-surface);'} padding:4px 10px;">
          STARVING REALMS: ${outcome.starving_count}
        </span>
      `;
    }

    const realmsList = document.getElementById('proj-debrief-realms-list');
    if (realmsList && outcome.realm_evaluations) {
      realmsList.innerHTML = outcome.realm_evaluations.map((r, idx) => {
        let pubHtml = '';
        if (r.public_mission_eval) {
          const pm = r.public_mission_eval;
          pubHtml = `
            <div style="background:rgba(120, 90, 40, 0.06); border:1px solid var(--border-subtle); padding:6px 8px; border-radius:3px; margin-top:4px;">
              <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="font-size:0.75rem; color: var(--text-primary);"><strong>Public:</strong> ${pm.title}</span>
                ${pm.achieved ? 
                  '<span class="badge" style="background:#10b981; color:#fff; font-size:0.62rem; padding:1px 6px;">✓ ACHIEVED</span>' : 
                  '<span class="badge" style="background:#ef4444; color:#fff; font-size:0.62rem; padding:1px 6px;">✗ FAILED</span>'}
              </div>
              <div style="font-size:0.68rem; color:var(--text-muted); font-family:var(--font-mono);">${pm.explanation}</div>
            </div>
          `;
        }

        let secretsHtml = '';
        if (r.secret_missions_eval && r.secret_missions_eval.length > 0) {
          secretsHtml = r.secret_missions_eval.map((sm, i) => `
            <div style="background:rgba(120, 90, 40, 0.06); border:1px solid var(--border-subtle); padding:6px 8px; border-radius:3px; margin-top:3px;">
              <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="font-size:0.75rem; color: var(--text-primary);"><strong>Secret #${i+1}:</strong> ${sm.title}</span>
                ${sm.achieved ? 
                  '<span class="badge" style="background:#10b981; color:#fff; font-size:0.62rem; padding:1px 6px;">✓ ACHIEVED</span>' : 
                  '<span class="badge" style="background:#ef4444; color:#fff; font-size:0.62rem; padding:1px 6px;">✗ FAILED</span>'}
              </div>
              <div style="font-size:0.68rem; color:var(--text-muted); font-family:var(--font-mono);">${sm.explanation}</div>
            </div>
          `).join('');
        }

        return `
        <div style="background:var(--bg-surface-sunken); border:1px solid var(--border-subtle); padding:10px 12px; border-radius:var(--radius-sm); margin-bottom:8px;">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <div style="display:flex; align-items:center; gap:8px;">
              <span style="font-family:var(--font-mono); font-weight:900; font-size:1rem; color:var(--text-muted);">#${idx + 1}</span>
              <strong style="font-size:0.95rem; text-transform:uppercase;">${r.name}</strong>
              <span class="badge" style="font-size:0.72rem; background:rgba(120, 90, 40, 0.12);">${r.success_ratio || ''} MANDATES (${r.score}%)</span>
            </div>
            ${r.directive_achieved ? 
              '<span class="badge" style="background:#10b981; color:#fff; font-weight:800; padding:2px 8px;">ALL MANDATES MET</span>' : 
              `<span class="badge" style="background:rgba(120, 90, 40, 0.12); color: var(--text-primary); padding:2px 8px;">${r.achieved_missions}/${r.total_missions} MET</span>`}
          </div>
          ${pubHtml}
          ${secretsHtml}
          <p style="font-size:0.78rem; color:var(--text-secondary); margin-top:6px; line-height:1.35; font-style:italic;">
            "${r.epilogue}"
          </p>
        </div>
      `;
      }).join('');
    }

    const honorsEl = document.getElementById('proj-debrief-honors');
    if (honorsEl && outcome.honors) {
      honorsEl.innerHTML = `
        <div style="background:var(--bg-surface-sunken); padding:8px 12px; border-radius:var(--radius-xs); border:1px solid var(--border-subtle);">
          <div style="font-size:0.72rem; font-family:var(--font-mono); color:var(--text-muted);">ARCH-DIPLOMAT OF THE SPIRE</div>
          <strong style="font-size:0.9rem; color: var(--text-primary);">${outcome.honors.arch_diplomat.name}</strong>
          <span style="font-size:0.75rem; font-family:var(--font-mono); color:var(--text-secondary); margin-left:6px;">(${outcome.honors.arch_diplomat.standing}/100 Standing)</span>
        </div>
        <div style="background:var(--bg-surface-sunken); padding:8px 12px; border-radius:var(--radius-xs); border:1px solid var(--border-subtle);">
          <div style="font-size:0.72rem; font-family:var(--font-mono); color:var(--text-muted);">INDUSTRIAL HEGEMON</div>
          <strong style="font-size:0.9rem; color: var(--text-primary);">${outcome.honors.industrial_hegemon.name}</strong>
          <span style="font-size:0.75rem; font-family:var(--font-mono); color:var(--text-secondary); margin-left:6px;">(${outcome.honors.industrial_hegemon.cores} Cores)</span>
        </div>
        <div style="background:var(--bg-surface-sunken); padding:8px 12px; border-radius:var(--radius-xs); border:1px solid var(--border-subtle);">
          <div style="font-size:0.72rem; font-family:var(--font-mono); color:var(--text-muted);">BREADBASKET OF THE CONTINENT</div>
          <strong style="font-size:0.9rem; color: var(--text-primary);">${outcome.honors.breadbasket.name}</strong>
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

  // Spotlight: one nation, large enough to read on a projector (public info only: tiers, never numbers)
  renderSpotlight(realms) {
    const esc = escapeHtml;
    const active = realms.filter(r => r.active !== false);
    if (!active.length) return;
    if (!active.some(r => r.id === this.spotlightId)) this.spotlightId = active[0].id;
    const r = active.find(x => x.id === this.spotlightId);
    const info = (window.LivingAtlas && window.LivingAtlas.info) || { regions: {}, capitals: {} };
    const level = t => ({ LOW: 1, MEDIUM: 2, HIGH: 3 }[t] || 0);
    const words = { LOW: 'Low', MEDIUM: 'Medium', HIGH: 'High' };
    const row = (icon, label, tier) => `<div class="spot-row"><span class="spot-icon">${icon}</span><span class="spot-label">${label}</span>
      <span class="spot-pips">${[1, 2, 3].map(n => `<em class="${n <= level(tier) ? 'on' : ''}"></em>`).join('')}</span>
      <span class="spot-word">${words[tier] || '—'}</span></div>`;
    const flags = [];
    if (r.is_starving) flags.push('<span class="flag bad">🥀 Famine</span>');
    if (r.is_plutocrat) flags.push('<span class="flag good">👑 Richest realm · +1 vote</span>');
    if (r.is_quarantined) flags.push('<span class="flag good">🛡️ Cordoned</span>');
    const box = document.getElementById('spotlight');
    if (box) box.innerHTML = `
      <div class="spot-head" style="--nc:${esc(r.theme_color || '#8c7a5e')}">
        <span class="crest spot-crest">${esc(r.emoji || '🏛️')}</span>
        <div class="grow">
          <div class="spot-name">${esc(r.name)}</div>
          <div class="spot-sub">${esc(info.regions[r.id] || '')}${info.capitals[r.id] ? ` · capital ${esc(info.capitals[r.id])}` : ''}</div>
        </div>
        <span class="vote-seal spot-seal" title="Assembly votes">${r.assembly_votes}<small>votes</small></span>
      </div>
      <div class="spot-mandate"><span>Public mandate</span><b>${esc(r.public_mission ? r.public_mission.title : '')}</b>
        <p>${esc(r.public_mission ? r.public_mission.description : '')}</p></div>
      <div class="spot-stats">
        ${row('🌾', 'Grain', r.grain_tier)}${row('⚙️', 'Cores', r.cores_tier)}${row('🧵', 'Silk', r.silk_tier)}${row('⚔️', 'Military', r.military_tier)}
        ${row('❤️', 'Vitality', r.vitality_tier)}${row('🤝', 'Standing', r.standing_tier)}${row('🏛️', 'Stability', r.stability_tier)}
      </div>
      ${flags.length ? `<div class="spot-flags">${flags.join('')}</div>` : ''}`;
    const chips = document.getElementById('projector-realms-list');
    if (chips) chips.innerHTML = active.map(x => `
      <button type="button" class="spot-chip ${x.id === r.id ? 'on' : ''}" style="--nc:${esc(x.theme_color || '#8c7a5e')}"
        title="${esc(x.name)}" onclick="projApp.showRealm('${esc(x.id)}')">${esc(x.emoji || '🏛️')}</button>`).join('');
  }

  showRealm(id) {
    this.spotlightId = id;
    if (this.map) this.map.selectRealm(id);
    if (this.lastRealms) this.renderSpotlight(this.lastRealms);
  }

  renderTicker(news) {
    const el = document.getElementById('news-ticker-content');
    if (!el) return;
    const items = news.slice(0, 10);
    const key = items.map(n => n.id || n.headline + n.time_str).join('|');
    if (key === this._tickerKey) return;   // only rebuild when the news changes, so scrolling stays smooth
    this._tickerKey = key;
    const icons = { crisis: '⚡', trade: '🤝', assembly: '📜', lore: '📖', turn: '🔔', diplomacy: '🕊️', war: '⚔️', boon: '🌟' };
    const html = items.map(n => `<span class="ticker-item"><b>${icons[n.type] || '✦'} ${escapeHtml(n.headline)}</b> ${escapeHtml(n.detail)}</span>`).join('');
    el.innerHTML = html + html;  // duplicated so the loop is seamless
    const seconds = Math.max(30, el.scrollWidth / 2 / 70);   // ~70 px per second
    el.style.animationDuration = `${seconds}s`;
    el.style.animationName = 'none';
    void el.offsetWidth;
    el.style.animationName = '';
  }

  // Debrief: one reflection question, large, with the relevant results from this game beside it.
  renderReflection(step, state) {
    const esc = escapeHtml;
    const questions = state.reflection_questions || [];
    const q = questions[step];
    if (!q) return;
    document.getElementById('reflection-kicker').innerText = `Reflection · question ${step + 1} of ${questions.length}`;
    document.getElementById('reflection-question').innerText = q.text;
    document.getElementById('reflection-dots').innerHTML = questions.map((_, i) =>
      `<em class="${i === step ? 'on' : i < step ? 'done' : ''}"></em>`).join('');

    const outcome = state.summit_outcome || {};
    const evals = (outcome.realm_evaluations || []).slice();
    const realms = Object.fromEntries((state.realms || []).map(r => [r.id, r]));
    const crest = id => esc((realms[id] || {}).emoji || '🏛️');
    const color = id => esc((realms[id] || {}).theme_color || '#8c7a5e');
    const tick = ok => ok ? '<b class="ok">✓</b>' : '<b class="no">✗</b>';
    const row = (id, name, cells) => `<div class="rc-row" style="--nc:${color(id)}"><span class="crest small">${crest(id)}</span><span class="rc-name">${esc(name)}</span>${cells}</div>`;
    let html = '';
    if (q.context === 'verdict' && outcome.continental_verdict) {
      html = `<div class="rc-verdict"><b>${esc(outcome.continental_verdict)}</b><p>${esc(outcome.continental_desc || '')}</p></div>`;
    } else if (q.context === 'missions') {
      html = evals.map(e => {
        const secrets = e.secret_missions_eval || [];
        const done = secrets.filter(s => s.achieved).length;
        return row(e.realm_id, e.name, `<span class="rc-cell">Public ${tick(e.public_mission_eval && e.public_mission_eval.achieved)}</span>
          <span class="rc-cell">Secret ${done}/${secrets.length}</span>`);
      }).join('');
    } else if (q.context === 'power') {
      html = Object.values(realms).filter(r => r.active !== false).sort((a, b) => b.assembly_votes - a.assembly_votes).map(r =>
        row(r.id, r.name, `<span class="rc-cell">${r.assembly_votes} vote${r.assembly_votes === 1 ? '' : 's'}</span>
          <span class="rc-cell">Standing ${esc((r.standing_tier || '').toLowerCase())}</span>${r.is_plutocrat ? '<span class="rc-cell">👑 richest</span>' : ''}`)).join('');
    } else if (q.context === 'sizes') {
      html = evals.slice().sort((a, b) => b.player_count - a.player_count).map(e =>
        row(e.realm_id, e.name, `<span class="rc-cell">${'👤'.repeat(e.player_count || 1)}</span><span class="rc-cell">${esc(e.success_ratio || '')} missions</span>`)).join('');
    } else if (q.context === 'winners') {
      html = `<div class="rc-verdict small"><span>The continent:</span> <b>${esc(outcome.continental_verdict || '')}</b></div>` +
        evals.slice().sort((a, b) => b.score - a.score).map((e, i) =>
          row(e.realm_id, `${i + 1}. ${e.name}`, `<span class="rc-cell">${esc(e.success_ratio || '')} missions</span><span class="rc-cell">${e.score}%</span>`)).join('');
    } else if (step === 0) {
      html = '<p class="rc-hint">Put the phones away and sit together in one circle.</p>';
    }
    document.getElementById('reflection-context').innerHTML = html;
  }

  renderTimeline(meta) {
    const el = document.getElementById('proj-timeline');
    if (!el) return;
    const turns = meta.max_turns || 3;
    const steps = [];
    for (let t = 1; t <= turns; t++) {
      steps.push({ key: `turn-${t}`, label: `Turn ${t}` });
      steps.push({ key: `vote-${t}`, label: t === turns ? 'Grand Plenary' : 'Assembly vote' });
    }
    steps.push({ key: 'end', label: 'Debrief' });
    const voting = ['plenary_quick', 'grand_plenary_discussion', 'grand_plenary_voting', 'turn_summary'].includes(meta.phase);
    const current = meta.phase === 'summit_concluded' ? 'end' : `${voting ? 'vote' : 'turn'}-${meta.current_turn}`;
    const idx = steps.findIndex(s => s.key === current);
    el.innerHTML = steps.map((s, i) => `<span class="tl-step ${i < idx ? 'done' : ''} ${i === idx ? 'now' : ''}">${s.label}</span>`).join('<span class="tl-sep"></span>');
  }

  renderWorkingSession(meta, proposals, realms, news_feed) {
    const esc = escapeHtml;
    this.lastRealms = realms || [];
    this.renderSpotlight(this.lastRealms);
    const paused = document.getElementById('tour-paused');
    if (paused && this.map) paused.style.display = this.map.manual ? 'flex' : 'none';

    const motionsTicker = document.getElementById('projector-qualified-motions-list');
    if (motionsTicker) {
      const open = (proposals || []).filter(p => p.status === 'draft' || p.status === 'qualified');
      motionsTicker.innerHTML = open.length ? open.slice(0, 4).map(p => {
        const n = p.support_count ?? (p.support_list || []).length;
        return `<span class="ballot-chip ${n >= 2 ? 'ok' : ''}">${esc(p.title)} <em>${n >= 2 ? 'on the ballot' : `${n}/2 sponsors`}</em></span>`;
      }).join('') : '<span class="atlas-motions-empty">No motions yet. Nations table them from their phones.</span>';
    }
  }

  renderQuickPlenary(meta, proposals, realms) {
    const list = document.getElementById('proj-quick-plenary-docket-list');
    if (!list) return;
    const esc = escapeHtml;
    const docket = meta.plenary_docket || [];
    const docketProps = proposals.filter(p => docket.includes(p.id));
    const types = Object.fromEntries((this.resolutionTypes || []).map(t => [t.id, t]));
    const playing = (realms || []).filter(r => r.active !== false);

    list.innerHTML = docketProps.map((p, idx) => {
      const t = types[p.effect_type] || {};
      const tallies = p.tallies || { support_weight: 0, oppose_weight: 0 };
      const total = tallies.support_weight + tallies.oppose_weight;
      const pct = total > 0 ? (tallies.support_weight / total) * 100 : 50;
      const votes = p.votes || {};
      const ballots = playing.map(r => {
        const v = votes[r.id];
        const cls = v ? v.choice : 'pending';
        const label = !v ? 'Deciding…' : v.choice === 'support' ? `For · ${v.weight}` : v.choice === 'oppose' ? `Against · ${v.weight}` : 'Abstains';
        return `<div class="ballot ${cls}" style="--nc:${esc(r.theme_color || '#8c7a5e')}">
          <span class="crest small">${esc(r.emoji || '🏛️')}</span><span class="grow"><b>${esc(r.name)}</b><em>${label}</em></span></div>`;
      }).join('');
      return `<article class="assembly-motion">
        <div class="row-between" style="align-items:flex-start;">
          <h2>${esc(t.icon || '📜')} ${esc(p.title)}</h2>
          <span class="status-pill">Motion ${idx + 1} of ${docketProps.length}</span>
        </div>
        <div class="motion-sponsor">Tabled by ${esc(p.proposer_name)}</div>
        ${this.effectHtml(p, t)}
        <div class="balance">
          <span class="for">For ${tallies.support_weight}</span>
          <div class="balance-bar"><div style="width:${pct}%"></div></div>
          <span class="against">${tallies.oppose_weight} Against</span>
        </div>
        <div class="ballots">${ballots}</div>
      </article>`;
    }).join('') || '<p class="empty-state">No motions qualified for this vote.</p>';
  }

  renderGrandPlenary(meta, proposals, realms) {
    const docket = meta.plenary_docket || [];
    const idx = meta.current_motion_index || 0;
    const activeProp = proposals.find(p => p.id === docket[idx]);

    if (!activeProp) return;

    document.getElementById('proj-grand-badge').innerText = `GRAND PLENARY RESOLUTION ${idx + 1} OF ${docket.length}`;
    const debateMin = (meta.discussion_timer_total || 300) / 60;
    document.getElementById('proj-grand-phase-label').innerText = meta.phase === 'grand_plenary_discussion'
      ? `${debateMin % 1 ? debateMin.toFixed(1) : debateMin}-MINUTE FLOOR DEBATE` : 'SOVEREIGN ROLL-CALL VOTE';
    document.getElementById('proj-debate-clock').innerText = formatSeconds(meta.discussion_timer_remaining);
    document.getElementById('proj-grand-title').innerText = activeProp.title;
    document.getElementById('proj-grand-sponsors').innerText = `Tabled by ${activeProp.proposer_name}`;
    document.getElementById('proj-grand-desc').innerText = activeProp.description;
    const effectBox = document.getElementById('proj-grand-effect');
    if (effectBox) effectBox.innerHTML = this.effectInner(activeProp, (this.resolutionTypes || []).find(t => t.id === activeProp.effect_type) || {});

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
      grid.innerHTML = realms.filter(r => r.active !== false).map(r => {
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

window.ProjectorApp = ProjectorApp;
