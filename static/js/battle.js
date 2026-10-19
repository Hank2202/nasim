/**
 * The Summit of Realms - battle animation, shared by the projector (a pop-up at the side) and the phones.
 *
 *   BattleScene.play(container, battle, { onDone, onResult, duration })   builds the scene inside `container`, returns { stop() }
 *
 * Two armies of little soldiers march onto a field (drawn from the battle's ground and weather), meet in the middle and
 * fight. The line of battle moves towards the weaker side, soldiers fall (the more Military a nation lost, the more of its
 * soldiers fall), and then the loser's army routs while the winner raises its swords. The result, the spoils and the losses
 * appear afterwards. Only public facts are used (outcome, share, losses, ground, weather), never a nation's hidden numbers.
 */
'use strict';

const BATTLE_OUTCOMES = {
  attacker_crushing: { text: 'Crushing victory', winner: 'attacker' },
  attacker_victory: { text: 'Victory', winner: 'attacker' },
  attacker_narrow: { text: 'Narrow victory', winner: 'attacker' },
  stalemate: { text: 'Bloody stalemate', winner: null },
  defender_narrow: { text: 'Narrow defence', winner: 'defender' },
  defender_victory: { text: 'Attack repelled', winner: 'defender' },
  defender_crushing: { text: 'Army routed', winner: 'defender' },
};
const BATTLE_RES_ICONS = { grain: '🌾', cores: '⚙️', silk: '🧵', military: '⚔️' };

// The field is drawn in these units and scaled to the real size of the canvas.
const BS_W = 380, BS_H = 170, BS_HORIZON = 76;
const BS_ROWS = 4, BS_COLS = 5, BS_ROW_GAP = 18, BS_COL_GAP = 13, BS_FIRST_ROW_Y = 96;
// Timeline (milliseconds): march in, fight, rout, then the result.
const BS_T_MARCH = 1700, BS_T_ROUT = 5600, BS_T_RESULT = 7400;

const bsClamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
const bsLerp = (a, b, t) => a + (b - a) * t;
const bsEaseOut = t => 1 - Math.pow(1 - t, 3);
const bsEaseInOut = t => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);

// A small repeatable random generator, so a replay of the same battle looks the same.
function bsRandom(seedText) {
  let h = 1779033703 ^ String(seedText).length;
  for (let i = 0; i < String(seedText).length; i++) { h = Math.imul(h ^ String(seedText).charCodeAt(i), 3432918353); h = (h << 13) | (h >>> 19); }
  let a = h >>> 0;
  return () => { a |= 0; a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}

function bsShade(hex, amount) {                          // lighten (+) or darken (-) a #rrggbb colour
  const m = /^#?([0-9a-f]{6})$/i.exec(hex || '');
  if (!m) return hex || '#8c7a5e';
  const n = parseInt(m[1], 16);
  const ch = v => bsClamp(Math.round(v + 255 * amount), 0, 255);
  return `rgb(${ch(n >> 16)}, ${ch((n >> 8) & 255)}, ${ch(n & 255)})`;
}

class BattleScene {
  static outcome(b) {
    return BATTLE_OUTCOMES[b.outcome] || BATTLE_OUTCOMES.stalemate;
  }

  // ----- the two armies -----------------------------------------------------------------------------------------------
  static _buildArmy(b, side, loser, rng) {
    const lost = b.military_lost || {};
    const mine = lost[b[`${side}_id`]] ?? 0, other = lost[b[`${side === 'attacker' ? 'defender' : 'attacker'}_id`]] ?? 0;
    const falls = bsClamp(Math.round(1 + 11 * (mine / Math.max(mine, other, 1))), 1, BS_ROWS * BS_COLS - 4);
    const soldiers = [];
    for (let row = 0; row < BS_ROWS; row++) {
      for (let col = 0; col < BS_COLS; col++) {
        soldiers.push({ side, row, col, id: soldiers.length, seed: rng(), fallAt: null, fled: side === loser ? 600 + rng() * 900 : 0,
          // a little disorder in the ranks
          dx: (rng() - 0.5) * 5, dy: (rng() - 0.5) * 3 });
      }
    }
    // the front ranks fall first
    const order = soldiers.slice().sort((p, q) => (p.col + rng() * 2.6) - (q.col + rng() * 2.6));
    order.slice(0, falls).forEach(s => { s.fallAt = bsClamp(BS_T_MARCH + 500 + rng() * (BS_T_ROUT - BS_T_MARCH - 900), 0, BS_T_ROUT); });
    return soldiers;
  }

  // Where the two fronts are at time t.
  static _fronts(t, shiftMax, stalemate) {
    const mid = BS_W / 2;
    if (t < BS_T_MARCH) {
      const e = bsEaseOut(t / BS_T_MARCH);
      return { xa: bsLerp(-46, mid - 13, e), xd: bsLerp(BS_W + 46, mid + 13, e) };
    }
    const q = bsClamp((t - BS_T_MARCH) / (BS_T_ROUT - BS_T_MARCH), 0, 1);
    const sway = Math.sin(t / 85) * 2.5 + Math.sin(t / 310) * 4;
    let shift = shiftMax * bsEaseInOut(q) + sway;
    let xa = mid - 13 + shift, xd = mid + 13 + shift;
    if (t > BS_T_ROUT) {
      const r = bsEaseOut(bsClamp((t - BS_T_ROUT) / 1400, 0, 1));
      if (stalemate) { xa -= 34 * r; xd += 34 * r; }               // both sides draw back
      else { xa += shiftMax * 0.35 * r; xd += shiftMax * 0.35 * r; } // the winner presses on
    }
    return { xa, xd };
  }

  static play(container, b, opts = {}) {
    const esc = escapeHtml;
    const info = BattleScene.outcome(b);
    const winnerId = b.winner_id;
    const spoils = Object.entries(b.plunder || {}).map(([res, n]) =>
      `<span class="bs-chip">+${n} ${BATTLE_RES_ICONS[res] || ''} ${esc(RESOURCE_SHORT[res] || res)}</span>`).join('');
    const lost = b.military_lost || {};
    const tag = (kind) => {
      const id = b[`${kind}_id`];
      return `<div class="bs-side bs-${kind === 'attacker' ? 'left' : 'right'}" data-id="${esc(id)}" style="--nc:${esc(b[`${kind}_color`] || '#8c7a5e')}">
        <span class="crest bs-crest">${esc(b[`${kind}_emoji`] || '🏛️')}</span>
        <span class="bs-tag"><b>${esc(b[`${kind}_name`])}</b><em>${kind === 'attacker' ? 'attacks' : 'defends'}</em></span>
      </div>`;
    };
    container.innerHTML = `<div class="bs">
      <div class="bs-head">⚔️ <b>Battle</b> · turn ${esc(b.turn)} · ${esc((b.weather || {}).name || '')} · ${esc((b.terrain || {}).name || '')}</div>
      <div class="bs-arena">
        <canvas class="bs-field"></canvas>
        ${tag('attacker')}
        ${tag('defender')}
      </div>
      <div class="bs-bar"><div class="bs-bar-a" style="background:${esc(b.attacker_color || '#a87412')}"></div><div class="bs-bar-d" style="background:${esc(b.defender_color || '#7a6142')}"></div></div>
      <div class="bs-result">
        <div class="bs-outcome">${esc(info.text)}</div>
        <div class="bs-headline">${esc(b.verdict || b.headline)}</div>
        <div class="bs-spoils">${spoils || '<span class="bs-chip none">No spoils</span>'}</div>
        <div class="bs-losses">Soldiers lost: ${esc(b.attacker_name)} ${esc(lost[b.attacker_id] ?? 0)} · ${esc(b.defender_name)} ${esc(lost[b.defender_id] ?? 0)} Military</div>
      </div>
    </div>`;
    const root = container.firstElementChild;
    const canvas = root.querySelector('canvas');
    const cssW = canvas.getBoundingClientRect().width || canvas.offsetWidth || BS_W;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const scale = cssW / BS_W;
    canvas.width = Math.round(cssW * dpr);
    canvas.height = Math.round(cssW * (BS_H / BS_W) * dpr);
    const ctx = canvas.getContext ? canvas.getContext('2d') : null;
    const barA = root.querySelector('.bs-bar-a');
    const barD = root.querySelector('.bs-bar-d');

    const rng = bsRandom(`${b.id}:${b.attacker_id}:${b.defender_id}`);
    const loserSide = info.winner ? (info.winner === 'attacker' ? 'defender' : 'attacker') : null;
    const colours = { attacker: b.attacker_color || '#a87412', defender: b.defender_color || '#6b5a42' };
    const army = { attacker: BattleScene._buildArmy(b, 'attacker', loserSide, rng), defender: BattleScene._buildArmy(b, 'defender', loserSide, rng) };
    const share = bsClamp(b.share ?? 0.5, 0.05, 0.95);
    const shiftMax = bsClamp((share - 0.5) * 2.2, -0.9, 0.9) * 78;
    const stalemate = !info.winner;
    const terrainId = (b.terrain || {}).id || '';
    const weatherId = (b.weather || {}).id || 'clear';

    // rain, snow-like streaks: fixed positions, moved every frame
    const streaks = Array.from({ length: weatherId === 'storm' ? 70 : 46 }, () => ({ x: rng() * BS_W, y: rng() * BS_H, v: 3 + rng() * 3 }));
    const sparks = [];
    const puffs = [];
    const timers = [];
    let raf = 0, stopped = false, start = 0, resultShown = false, lastBar = -1;
    const setBar = pct => { if (Math.abs(pct - lastBar) > 0.3) { lastBar = pct; barA.style.width = `${pct}%`; barD.style.width = `${100 - pct}%`; } };
    setBar(50);

    // Where a soldier stands at time t (before the effects of falling and fleeing).
    const base = (s, t, fr) => {
      const rowY = BS_FIRST_ROW_Y + s.row * BS_ROW_GAP + s.dy;
      const stagger = (s.row % 2) * 4;
      const x = s.side === 'attacker' ? fr.xa - s.col * BS_COL_GAP - stagger + s.dx : fr.xd + s.col * BS_COL_GAP + stagger + s.dx;
      return { x, y: rowY };
    };
    const place = (s, t) => {
      const dir = s.side === 'attacker' ? 1 : -1;
      if (s.fallAt !== null && t >= s.fallAt) {                       // lying where he fell
        const p = base(s, s.fallAt, BattleScene._fronts(s.fallAt, shiftMax, stalemate));
        return { x: p.x, y: p.y, state: 'down', dir, t0: s.fallAt };
      }
      let fr = BattleScene._fronts(t, shiftMax, stalemate);
      if (s.side === loserSide && t > BS_T_ROUT + s.fled) {            // the beaten army runs for home
        const t0 = BS_T_ROUT + s.fled;
        const p = base(s, t0, BattleScene._fronts(t0, shiftMax, stalemate));
        const run = (t - t0) * (0.05 + (t - t0) * 0.00004);
        return { x: p.x - dir * run, y: p.y, state: 'flee', dir: -dir, t0 };
      }
      const p = base(s, t, fr);
      let state = t < BS_T_MARCH ? 'march' : (t < BS_T_ROUT ? (s.col <= 1 ? 'fight' : 'march') : (stalemate ? 'march' : 'cheer'));
      if (state === 'march' && t >= BS_T_MARCH && t < BS_T_ROUT) state = 'hold';
      return { x: p.x, y: p.y, state, dir, t0: 0 };
    };

    const burst = (x, y, n, color) => {
      for (let i = 0; i < n; i++) {
        const a = Math.random() * Math.PI * 2, v = 0.6 + Math.random() * 2.2;
        sparks.push({ x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v - 0.8, life: 1, color });
      }
    };

    // ----- drawing --------------------------------------------------------------------------------------------------
    const drawBackdrop = (t) => {
      const night = weatherId === 'night', storm = weatherId === 'storm';
      const sky = ctx.createLinearGradient(0, 0, 0, BS_HORIZON);
      if (night) { sky.addColorStop(0, '#1a2038'); sky.addColorStop(1, '#3a4468'); }
      else if (storm) { sky.addColorStop(0, '#4a4f5c'); sky.addColorStop(1, '#8a8f98'); }
      else if (weatherId === 'heat') { sky.addColorStop(0, '#f6c56a'); sky.addColorStop(1, '#fbe3a8'); }
      else { sky.addColorStop(0, '#9cc7e6'); sky.addColorStop(1, '#f3ead2'); }
      ctx.fillStyle = sky; ctx.fillRect(0, 0, BS_W, BS_HORIZON + 2);
      if (night) { ctx.fillStyle = '#f4efd2'; ctx.beginPath(); ctx.arc(310, 22, 9, 0, 6.3); ctx.fill(); ctx.fillStyle = '#2a3252'; ctx.beginPath(); ctx.arc(314, 20, 8, 0, 6.3); ctx.fill(); }
      else if (!storm && weatherId !== 'fog') { ctx.fillStyle = 'rgba(255, 244, 190, 0.9)'; ctx.beginPath(); ctx.arc(310, 24, 11, 0, 6.3); ctx.fill(); }
      // the far land
      const ridge = { volcanic_mountains: '#5d4a44', abyssal_chasm: '#43385a', northern_steppes: '#b9b078', verdant_lowlands: '#8fb36a',
        solar_plateau: '#d2b26a', coastal_archipelago: '#7fa7b8' }[terrainId] || '#9a8a6a';
      ctx.fillStyle = bsShade(ridge, -0.04);
      ctx.beginPath(); ctx.moveTo(0, BS_HORIZON);
      if (terrainId === 'volcanic_mountains') {
        for (let x = 0; x <= BS_W; x += 38) { ctx.lineTo(x + 14, BS_HORIZON - 34 - ((x / 38) % 2) * 18); ctx.lineTo(x + 38, BS_HORIZON); }
      } else if (terrainId === 'solar_plateau') {
        ctx.lineTo(0, BS_HORIZON - 22); ctx.lineTo(130, BS_HORIZON - 22); ctx.lineTo(150, BS_HORIZON - 4); ctx.lineTo(240, BS_HORIZON - 4);
        ctx.lineTo(262, BS_HORIZON - 24); ctx.lineTo(BS_W, BS_HORIZON - 24);
      } else {
        for (let x = 0; x <= BS_W; x += 20) ctx.lineTo(x, BS_HORIZON - 8 - Math.sin(x / 41 + 1) * 8 - Math.sin(x / 17) * 3);
      }
      ctx.lineTo(BS_W, BS_HORIZON); ctx.closePath(); ctx.fill();
      if (terrainId === 'coastal_archipelago') {
        ctx.fillStyle = '#5f8fa8'; ctx.fillRect(0, BS_HORIZON - 12, BS_W, 12);
        ctx.fillStyle = 'rgba(255,255,255,0.45)';
        for (let i = 0; i < 8; i++) ctx.fillRect(((i * 53 + t / 60) % BS_W), BS_HORIZON - 9 + (i % 3) * 3, 14, 1.4);
      }
      // the ground
      const gc = { volcanic_mountains: '#7a6a5a', abyssal_chasm: '#5b4d6a', northern_steppes: '#cdbf86', verdant_lowlands: '#9cc072',
        solar_plateau: '#dcc07a', coastal_archipelago: '#d9c9a0' }[terrainId] || '#b8a67a';
      const ground = ctx.createLinearGradient(0, BS_HORIZON, 0, BS_H);
      ground.addColorStop(0, bsShade(gc, 0.06)); ground.addColorStop(1, bsShade(gc, -0.12));
      ctx.fillStyle = ground; ctx.fillRect(0, BS_HORIZON, BS_W, BS_H - BS_HORIZON);
      if (terrainId === 'abyssal_chasm') {                             // the Rift cuts across the far field
        ctx.strokeStyle = 'rgba(20, 8, 40, 0.8)'; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(30, BS_HORIZON + 6);
        ctx.lineTo(110, BS_HORIZON + 12); ctx.lineTo(160, BS_HORIZON + 7); ctx.lineTo(250, BS_HORIZON + 13); ctx.lineTo(340, BS_HORIZON + 8); ctx.stroke();
      }
      ctx.fillStyle = 'rgba(70, 50, 30, 0.10)';                         // trampled earth
      for (let i = 0; i < 22; i++) ctx.fillRect((i * 97) % BS_W, BS_HORIZON + 8 + ((i * 41) % (BS_H - BS_HORIZON - 12)), 14, 2);
    };

    const drawSoldier = (s, pos, t) => {
      const c = colours[s.side], dir = pos.dir, bob = Math.sin(t / 95 + s.seed * 9);
      let x = pos.x, y = pos.y;
      ctx.save();
      ctx.translate(x, y);
      ctx.scale(1.2, 1.2);
      if (pos.state === 'down') {                                      // fallen: lying on the ground, a little faded
        const fall = bsClamp((t - pos.t0) / 260, 0, 1);
        ctx.globalAlpha = 0.9 - 0.3 * fall;
        ctx.rotate(-dir * 1.5 * bsEaseOut(fall));
        ctx.translate(0, fall * 3);
      }
      const running = pos.state === 'march' || pos.state === 'flee';
      const step = running ? Math.sin(t / (pos.state === 'flee' ? 55 : 120) + s.seed * 9) : 0;
      if (pos.state !== 'down') {                                      // shadow
        ctx.fillStyle = 'rgba(40, 28, 16, 0.28)'; ctx.beginPath(); ctx.ellipse(0, 1, 6, 2, 0, 0, 6.3); ctx.fill();
        if (pos.state === 'cheer') ctx.translate(0, -Math.abs(Math.sin(t / 150 + s.seed * 6)) * 4);
      }
      // legs
      ctx.strokeStyle = '#3a2c20'; ctx.lineWidth = 1.8; ctx.beginPath();
      ctx.moveTo(-1.6, -5); ctx.lineTo(-1.6 + step * 2.4, 0); ctx.moveTo(1.6, -5); ctx.lineTo(1.6 - step * 2.4, 0); ctx.stroke();
      // body
      ctx.fillStyle = c; ctx.fillRect(-3.6, -13, 7.2, 9);
      ctx.fillStyle = bsShade(c, -0.18); ctx.fillRect(-3.6, -7, 7.2, 2);
      // head and helmet
      ctx.fillStyle = '#e8c9a0'; ctx.beginPath(); ctx.arc(0, -15.4, 2.9, 0, 6.3); ctx.fill();
      ctx.fillStyle = '#8f949c'; ctx.beginPath(); ctx.arc(0, -16, 3.1, Math.PI, 0); ctx.fill();
      // shield on the front arm
      ctx.fillStyle = bsShade(c, 0.22); ctx.strokeStyle = '#3a2c20'; ctx.lineWidth = 0.9;
      ctx.beginPath(); ctx.ellipse(dir * 4.6, -8.5, 2.6, 4, 0, 0, 6.3); ctx.fill(); ctx.stroke();
      // sword
      let ang = -0.9;
      if (pos.state === 'fight') ang = -1.9 + Math.sin(t / 70 + s.seed * 11) * 1.25;
      else if (pos.state === 'cheer') ang = -2.5;
      else if (pos.state === 'flee' || pos.state === 'down') ang = 0.6;
      const hx = dir * 3.4, hy = -9.5, len = 9.5;
      ctx.strokeStyle = '#e8ecf2'; ctx.lineWidth = 1.4; ctx.beginPath();
      ctx.moveTo(hx, hy); ctx.lineTo(hx + dir * Math.cos(ang) * len, hy + Math.sin(ang) * len); ctx.stroke();
      ctx.restore();
    };

    const drawBanner = (side, t, fr) => {                              // each army carries its nation's crest on a pole
      const s = army[side][Math.floor(BS_ROWS / 2) * BS_COLS + BS_COLS - 1];
      const flightT = t;
      const pos = place(s, t);
      if (pos.state === 'down') return;
      const dir = side === 'attacker' ? 1 : -1;
      const x = pos.x - dir * 8, y = pos.y;
      ctx.strokeStyle = '#5b4126'; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x, y - 36); ctx.stroke();
      const wave = Math.sin(flightT / 140 + (dir > 0 ? 0 : 2)) * 2;
      ctx.fillStyle = colours[side];
      ctx.beginPath(); ctx.moveTo(x, y - 36); ctx.lineTo(x - dir * 17, y - 34 + wave); ctx.lineTo(x - dir * 16, y - 24 + wave); ctx.lineTo(x, y - 24); ctx.closePath(); ctx.fill();
      ctx.font = '9px serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillStyle = '#fff';
      ctx.fillText(b[`${side}_emoji`] || '🏛️', x - dir * 8.5, y - 29.5 + wave * 0.6);
    };

    const drawWeather = (t) => {
      if (weatherId === 'rain' || weatherId === 'storm') {
        ctx.strokeStyle = 'rgba(210, 225, 245, 0.55)'; ctx.lineWidth = 1; ctx.beginPath();
        for (const p of streaks) { p.y += p.v; p.x -= 1.2; if (p.y > BS_H) { p.y = -8; p.x = Math.random() * (BS_W + 30); } ctx.moveTo(p.x, p.y); ctx.lineTo(p.x - 2.2, p.y + 8); }
        ctx.stroke();
        ctx.fillStyle = `rgba(30, 40, 60, ${weatherId === 'storm' ? 0.22 : 0.12})`; ctx.fillRect(0, 0, BS_W, BS_H);
        if (weatherId === 'storm' && Math.sin(t / 620) > 0.96) { ctx.fillStyle = 'rgba(255, 255, 255, 0.5)'; ctx.fillRect(0, 0, BS_W, BS_H); }
      } else if (weatherId === 'fog') {
        const g = ctx.createLinearGradient(0, 40, 0, BS_H);
        g.addColorStop(0, 'rgba(245, 245, 240, 0.0)'); g.addColorStop(0.5, 'rgba(245, 245, 240, 0.5)'); g.addColorStop(1, 'rgba(245, 245, 240, 0.25)');
        ctx.fillStyle = g; ctx.fillRect(0, 0, BS_W, BS_H);
      } else if (weatherId === 'night') {
        ctx.fillStyle = 'rgba(14, 20, 50, 0.40)'; ctx.fillRect(0, 0, BS_W, BS_H);
      } else if (weatherId === 'heat') {
        ctx.fillStyle = 'rgba(255, 150, 40, 0.13)'; ctx.fillRect(0, 0, BS_W, BS_H);
      } else if (weatherId === 'tailwind') {
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.5)'; ctx.lineWidth = 1; ctx.beginPath();
        for (const p of streaks.slice(0, 18)) { p.x += p.v * 1.6; if (p.x > BS_W + 20) p.x = -20; ctx.moveTo(p.x, p.y * 0.6 + 20); ctx.lineTo(p.x + 14, p.y * 0.6 + 20); }
        ctx.stroke();
      }
    };

    // ----- the loop -------------------------------------------------------------------------------------------------
    const everyone = army.attacker.concat(army.defender);
    const fell = new Set();
    const frame = (now) => {
      if (stopped) return;
      if (!start) start = now;
      const t = now - start;
      if (ctx) {
        ctx.setTransform(canvas.width / BS_W, 0, 0, canvas.width / BS_W, 0, 0);
        ctx.clearRect(0, 0, BS_W, BS_H);
        drawBackdrop(t);
        const placed = everyone.map(s => ({ s, p: place(s, t) }));
        placed.sort((u, v) => (u.p.state === 'down' ? -1 : 0) - (v.p.state === 'down' ? -1 : 0) || u.p.y - v.p.y);
        for (const { s, p } of placed) {
          if (p.x < -24 || p.x > BS_W + 24) continue;
          drawSoldier(s, p, t);
          if (p.state === 'down' && !fell.has(s.side + s.id)) { fell.add(s.side + s.id); puffs.push({ x: p.x, y: p.y - 2, life: 1 }); burst(p.x, p.y - 8, 6, '#e8d9a8'); }
        }
        drawBanner('attacker', t); drawBanner('defender', t);
        // dust at the places where soldiers fell
        for (const d of puffs) { d.life -= 0.02; d.x += 0.1; if (d.life > 0) { ctx.fillStyle = `rgba(200, 180, 140, ${d.life * 0.5})`; ctx.beginPath(); ctx.arc(d.x, d.y - (1 - d.life) * 6, 5 + (1 - d.life) * 7, 0, 6.3); ctx.fill(); } }
        for (let i = puffs.length - 1; i >= 0; i--) if (puffs[i].life <= 0) puffs.splice(i, 1);
        // sparks where the swords meet
        if (t > BS_T_MARCH && t < BS_T_ROUT) {
          const fr = BattleScene._fronts(t, shiftMax, stalemate);
          if (Math.random() < 0.55) burst((fr.xa + fr.xd) / 2, BS_FIRST_ROW_Y - 10 + Math.random() * 50, 3, Math.random() < 0.5 ? '#ffd27a' : '#ffffff');
        }
        ctx.globalCompositeOperation = 'lighter';
        for (const p of sparks) {
          p.x += p.vx; p.y += p.vy; p.vy += 0.09; p.life -= 0.035;
          if (p.life > 0) { ctx.strokeStyle = p.color; ctx.globalAlpha = Math.max(0, p.life); ctx.lineWidth = 1.4; ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(p.x - p.vx * 2, p.y - p.vy * 2); ctx.stroke(); }
        }
        ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';
        for (let i = sparks.length - 1; i >= 0; i--) if (sparks[i].life <= 0) sparks.splice(i, 1);
        drawWeather(t);
      }
      // the bar follows the line of battle
      const fr = BattleScene._fronts(Math.min(t, BS_T_ROUT), shiftMax, stalemate);
      setBar(bsClamp(50 + ((fr.xa + fr.xd) / 2 - BS_W / 2) / (BS_W / 2) * 55, 8, 92));
      if (!resultShown && t >= BS_T_RESULT) {
        resultShown = true;
        root.classList.add('bs-done', info.winner ? `bs-win-${info.winner}` : 'bs-draw');
        barA.style.transition = barD.style.transition = 'width 0.9s ease-out';
        const winnerEl = winnerId ? root.querySelector(`.bs-side[data-id="${CSS.escape(String(winnerId))}"]`) : null;
        if (winnerEl) winnerEl.classList.add('bs-winner');
        if (opts.onResult) opts.onResult();
      }
      raf = requestAnimationFrame(frame);
    };
    root.classList.add('bs-enter');
    raf = requestAnimationFrame(frame);
    if (opts.duration) timers.push(setTimeout(() => { if (!stopped) { api.stop(); if (opts.onDone) opts.onDone(); } }, opts.duration));

    const api = {
      stop() {
        stopped = true;
        cancelAnimationFrame(raf);
        timers.forEach(clearTimeout);
      },
    };
    return api;
  }
}

window.BattleScene = BattleScene;
