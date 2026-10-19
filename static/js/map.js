/**
 * The Summit of Realms - "Living Atlas": animated map of the Continent for the projector.
 *
 * How it works (cheap enough for any facilitator laptop):
 *   1. A heightmap is generated once from hand-placed terrain blobs that follow the
 *      Spireopedia geography (Aethelgard north, Val-Khor's mountains north-east, Solaris'
 *      plateau east, Sylvan's lowlands south, Umbra's rift west, Aquila's islands in the
 *      southern Sea of Glass, the Neutral Spire in the middle).
 *   2. That heightmap is painted ONCE into an offscreen, hill-shaded "illustrated map"
 *      texture (re-painted only when the roster of playing nations changes).
 *   3. Every frame the texture is drawn through a slowly orbiting, tilted camera, and
 *      upright sprites (mountains, forests, castles, the Spire), clouds, ships, waves,
 *      trade routes and nation banners are drawn on top, sorted by depth.
 *
 * Nations that are not playing are painted as grey "unclaimed lands" without banners.
 */
(function () {
  'use strict';

  // World units: x -500..500 (west..east), y -360..360 (north..south).
  const WORLD_W = 1200, WORLD_H = 900;
  // Quality presets. `tex` = texture pixels per world unit, `grid` = heightmap spacing in world units.
  const QUALITY = {
    high:     { tex: 2.25, grid: 1.5, dpr: 2,   fps: 60, sparkles: true,  glints: true,  birds: true,  cloudShadows: true },
    balanced: { tex: 1.5,  grid: 2,   dpr: 1.5, fps: 60, sparkles: true,  glints: true,  birds: true,  cloudShadows: true },
    low:      { tex: 1,    grid: 4,   dpr: 1,   fps: 30, sparkles: false, glints: false, birds: false, cloudShadows: false },
  };
  const QUALITY_KEY = 'map_quality';
  const SEA_DEEP = [120, 164, 176], SEA_SHALLOW = [178, 211, 205], BG = 'rgb(120,164,176)';

  const CAPITALS = {
    aethelgard: [-70, -215], val_khor: [215, -150], solaria: [275, 30],
    sylvan: [-20, 140], umbra: [-265, 15], aquila: [230, 300],
  };
  const SPIRE = [10, -20];
  // Settlements: [realm, name, x, y, isCapital]. Capitals match the Spireopedia articles.
  const SETTLEMENTS = [
    ['aethelgard', 'Aethelhold', -70, -215, true], ['aethelgard', 'Stonewatch', -230, -200], ['aethelgard', 'Garrowmere', 75, -235],
    ['val_khor', 'Khorgate', 215, -150, true], ['val_khor', 'Khor-Deep', 150, -92], ['val_khor', 'Ironvale', 320, -120],
    ['solaria', 'Helion', 275, 30, true], ['solaria', 'Sunreach', 370, -20], ['solaria', 'Dawnmarket', 225, 110],
    ['sylvan', 'Rootholm', -20, 140, true], ['sylvan', 'Hearthroot', -140, 112], ['sylvan', 'Oakmere', 105, 165],
    ['umbra', 'Lanternfall', -265, 15, true], ['umbra', 'Veilhollow', -330, -95], ['umbra', 'Duskwell', -235, 125],
    ['aquila', 'Halcyon Quay', 230, 300, true], ['aquila', 'Brinegate', 338, 276],
  ];
  const ROADS = [
    ['Aethelhold', 'SPIRE'], ['Khorgate', 'SPIRE'], ['Helion', 'SPIRE'], ['Rootholm', 'SPIRE'], ['Lanternfall', 'SPIRE'],
    ['Aethelhold', 'Khorgate'], ['Khorgate', 'Helion'], ['Helion', 'Rootholm'], ['Rootholm', 'Lanternfall'], ['Lanternfall', 'Aethelhold'],
    ['Stonewatch', 'Aethelhold'], ['Garrowmere', 'Aethelhold'], ['Khor-Deep', 'Khorgate'], ['Ironvale', 'Khorgate'],
    ['Sunreach', 'Helion'], ['Dawnmarket', 'Helion'], ['Hearthroot', 'Rootholm'], ['Oakmere', 'Rootholm'],
    ['Veilhollow', 'Lanternfall'], ['Duskwell', 'Lanternfall'],
  ];
  // Sea lanes for the island league, drawn as dotted routes on the water.
  const SEA_LANES = [['Halcyon Quay', 'Brinegate'], ['Halcyon Quay', 'Oakmere'], ['Brinegate', 'Dawnmarket']];
  const REGION_NAMES = {
    aethelgard: 'Northern Steppes', val_khor: 'Mount Khor Spine', solaria: 'Solar Plateau',
    sylvan: 'Verdant Lowlands', umbra: 'Abyssal Rift', aquila: 'Sea of Glass',
  };
  const DEFAULT_COLORS = {
    aethelgard: '#ec4899', val_khor: '#f59e0b', solaria: '#eab308',
    umbra: '#8b5cf6', aquila: '#06b6d4', sylvan: '#10b981',
  };

  // Terrain blobs: [cx, cy, rx, ry, height]
  const BLOBS = [
    [0, -10, 330, 215, 12],                                             // continent body
    [-60, -215, 190, 95, 10], [-150, -250, 70, 40, 7],                  // Aethelgard steppes
    [200, -150, 120, 70, 16], [165, -170, 34, 22, 34], [215, -140, 28, 22, 40],
    [255, -120, 30, 24, 36], [190, -110, 26, 18, 28], [245, -185, 26, 20, 30],  // Khor spine
    [285, 30, 120, 105, 15], [300, 10, 70, 55, 6],                      // Solar plateau
    [-20, 140, 230, 70, 5],                                             // Sylvan lowlands
    [-265, 15, 135, 140, 11], [-300, -60, 60, 50, 12],                  // Umbra highlands
    [10, -20, 42, 34, 14],                                              // Spire plateau
    // Aquila archipelago
    [230, 300, 72, 27, 16], [338, 276, 42, 19, 13], [128, 318, 40, 17, 12],
    [385, 324, 25, 13, 10], [288, 340, 23, 11, 9], [175, 345, 16, 9, 8],
  ];
  // The Abyssal Rift: a deep, winding chasm through Umbra.
  const RIFT = [[-330, -80], [-300, -30], [-315, 20], [-280, 70], [-295, 120]];

  // Deterministic pseudo-random numbers so the map looks the same every time.
  function rng(seed) { return () => { seed = (seed * 16807) % 2147483647; return (seed - 1) / 2147483646; }; }
  const hexRgb = h => [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)];
  const mix = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

  function elevation(x, y) {
    let h = 0;
    for (const [cx, cy, rx, ry, hh] of BLOBS) {
      const dx = (x - cx) / rx, dy = (y - cy) / ry, d2 = dx * dx + dy * dy;
      if (d2 < 7) h += hh * Math.exp(-d2 * 1.15);
    }
    // gentle hills + irregular coast
    h += 2.6 * Math.sin(x * 0.029 + 0.7) * Math.cos(y * 0.034 + 1.1);
    h += 1.7 * Math.sin(x * 0.071 + 2.3) * Math.cos(y * 0.058 + 0.5);
    h += 0.9 * Math.sin(x * 0.13 + 3.7) * Math.cos(y * 0.11 + 2.1);
    // fine relief (ridges, gullies) that only becomes visible on the sharper quality modes
    h += 0.45 * Math.sin(x * 0.23 + y * 0.07 + 1.3) * Math.cos(y * 0.27 - x * 0.05);
    h += 0.25 * Math.sin(x * 0.41 + 0.4) * Math.sin(y * 0.37 + 2.2);
    // rift chasm
    for (let i = 0; i < RIFT.length - 1; i++) {
      const [ax, ay] = RIFT[i], [bx, by] = RIFT[i + 1];
      const vx = bx - ax, vy = by - ay, t = clamp(((x - ax) * vx + (y - ay) * vy) / (vx * vx + vy * vy), 0, 1);
      const d = Math.hypot(x - (ax + vx * t), y - (ay + vy * t));
      if (d < 16) h -= 9 * (1 - d / 16);
    }
    // sea beyond the continent
    // Southern coast ends before the Sea of Glass so Aquila's islands stand apart.
    const ex = x / 470, ey = (y - 10) / (y > 10 ? 255 : 345), r2 = ex * ex + ey * ey;
    const di = Math.hypot((x - 255) / 175, (y - 305) / 70);          // distance to the archipelago
    const shelter = di < 1 ? 0.25 : di < 1.7 ? 0.25 + 0.75 * (di - 1) / 0.7 : 1;
    if (r2 > 0.8) h -= 30 * (r2 - 0.8) * shelter;
    return h - 4.2;  // sea level
  }

  function owner(x, y) {
    if (y > 255 && x > 60) return 'aquila';
    let best = null, bd = Infinity;
    for (const [id, [cx, cy]] of Object.entries(CAPITALS)) {
      if (id === 'aquila') continue;
      // Slightly warped distance makes borders look hand-drawn rather than straight.
      const d = Math.hypot(x - cx, y - cy) + 14 * Math.sin(x * 0.02 + y * 0.03);
      if (d < bd) { bd = d; best = id; }
    }
    return best;
  }

  class LivingAtlas {
    constructor(canvas) {
      this.canvas = canvas;
      this.ctx = canvas.getContext('2d');
      let saved = null;
      try { saved = localStorage.getItem(QUALITY_KEY); } catch (e) {}
      this.qualityMode = QUALITY[saved] || saved === 'auto' ? saved : 'auto';   // what the facilitator chose
      this.quality = this.qualityMode === 'auto' ? 'balanced' : this.qualityMode; // what is in effect
      this.q = QUALITY[this.quality];
      this.dpr = Math.min(window.devicePixelRatio || 1, this.q.dpr);
      this.fpsProbe = this.qualityMode === 'auto' ? { start: null, frames: 0 } : null;
      this.lastDraw = 0;
      this.reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      this.realms = {};
      this.trades = [];
      this.rosterKey = '';
      this.focus = null;                 // realm id the camera is visiting, or null for overview
      this.onFocus = null;               // callback(realmId|null)
      this.cam = { yaw: -0.18, tilt: 0.62, zoom: 1, x: 0, y: 0, tx: 0, ty: 0, tzoom: 1 };
      this.tourStep = 0;
      this.events = [];
      this.wars = [];                       // real battles between nations: an arc of fire between their capitals
      this.eventClock = 0;
      this.nextEvent = 5;
      // Weather appears roughly once per cycle of ten events, i.e. every few minutes.
      this.eventQueue = ['dragon', 'whale', 'tornado', 'battle', 'serpent', 'storm', 'dragon', 'battle', 'whale', 'serpent'];
      this.manualUntil = 0;              // while exploring by hand, the automatic tour and orbit pause
      this.hits = [];
      this.flash = 0;
      this.flocks = [{ x: -700, y: -120, speed: 9 }, { x: 100, y: 180, speed: 7 }];
      this.tourClock = 0;
      this.last = performance.now();

      this.buildTerrain();
      this.buildScenery();
      this.paintTexture();
      this.resize();
      window.addEventListener('resize', () => this.resize());
      this.initControls();
      requestAnimationFrame(t => this.frame(t));
    }

    /* ------------------------------------------------------------ controls */
    initControls() {
      const cv = this.canvas;
      cv.style.cursor = 'grab';
      cv.style.touchAction = 'none';
      cv.addEventListener('wheel', e => { e.preventDefault(); this.zoomBy(Math.exp(-e.deltaY * 0.0015)); }, { passive: false });
      let down = null;
      cv.addEventListener('pointerdown', e => {
        down = { x: e.clientX, y: e.clientY, lastX: e.clientX, lastY: e.clientY, dragging: false };
        cv.setPointerCapture(e.pointerId);
      });
      cv.addEventListener('pointermove', e => {
        if (!down) return;
        if (!down.dragging && Math.hypot(e.clientX - down.x, e.clientY - down.y) > 5) { down.dragging = true; cv.style.cursor = 'grabbing'; }
        if (down.dragging) this.panByScreen(e.clientX - down.lastX, e.clientY - down.lastY);
        down.lastX = e.clientX; down.lastY = e.clientY;
      });
      cv.addEventListener('pointerup', e => {
        if (down && !down.dragging) {
          const r = cv.getBoundingClientRect();
          this.click(e.clientX - r.left, e.clientY - r.top);
        }
        down = null; cv.style.cursor = 'grab';
      });
      window.addEventListener('keydown', e => {
        if (e.target && /input|textarea|select/i.test(e.target.tagName)) return;
        const pan = 60;
        if (e.key === '+' || e.key === '=') this.zoomBy(1.25);
        else if (e.key === '-' || e.key === '_') this.zoomBy(0.8);
        else if (e.key === '0') this.home();
        else if (e.key === 'ArrowLeft') this.panByScreen(pan, 0);
        else if (e.key === 'ArrowRight') this.panByScreen(-pan, 0);
        else if (e.key === 'ArrowUp') this.panByScreen(0, pan);
        else if (e.key === 'ArrowDown') this.panByScreen(0, -pan);
        else return;
        e.preventDefault();
      });
    }

    /* --------------------------------------------------------------- quality */
    // mode: 'auto' | 'high' | 'balanced' | 'low'. Rebuilds terrain, scenery and texture at the new detail.
    setQuality(mode, { persist = true } = {}) {
      if (mode !== 'auto' && !QUALITY[mode]) return;
      if (persist) {
        this.qualityMode = mode;
        try { localStorage.setItem(QUALITY_KEY, mode); } catch (e) {}
      }
      const effective = mode === 'auto' ? (persist ? 'balanced' : this.quality) : mode;
      this.fpsProbe = this.qualityMode === 'auto' && persist ? { start: null, frames: 0 } : null;
      if (effective !== this.quality || !this.texture) {
        this.quality = effective;
        this.q = QUALITY[effective];
        this.buildTerrain();
        this.buildScenery();
        this.paintTexture();
        this.resize();
      }
      if (this.onQuality) this.onQuality(this.qualityMode, this.quality);
    }

    // Auto mode: watch the frame rate for a few seconds, then settle on a mode once.
    probeFrameRate(now) {
      const p = this.fpsProbe;
      if (!p) return;
      if (p.start === null) { if (now - this.paintedAt > 1500) { p.start = now; p.frames = 0; } return; }
      p.frames++;
      if (now - p.start < 5000) return;
      const fps = p.frames * 1000 / (now - p.start);
      this.fpsProbe = null;
      this.measuredFps = Math.round(fps);
      const cores = navigator.hardwareConcurrency || 4;
      if (fps < 32) this.setQuality('low', { persist: false });
      else if (fps > 55 && cores >= 8) this.setQuality('high', { persist: false });
      else if (this.onQuality) this.onQuality(this.qualityMode, this.quality);
    }

    get manual() { return this.time < this.manualUntil; }
    touch() { this.manualUntil = (this.time || 0) + 45; }   // tour resumes 45 s after the last interaction

    zoomBy(f) {
      this.cam.tzoom = clamp(this.cam.tzoom * f, 0.6, 3.6);
      this.touch();
    }

    panByScreen(dx, dy) {
      const c = this.cam, s = this.baseScale * c.zoom;
      const rx = dx / s, ry = dy / (s * c.tilt), cos = Math.cos(c.yaw), sin = Math.sin(c.yaw);
      const wx = rx * cos + ry * sin, wy = -rx * sin + ry * cos;
      c.tx = clamp(c.tx - wx, -560, 560); c.ty = clamp(c.ty - wy, -430, 430);
      c.x = clamp(c.x - wx, -560, 560); c.y = clamp(c.y - wy, -430, 430);
      this.touch();
    }

    home() {
      this.manualUntil = 0;
      this.tourClock = 0;
      this.setFocus(null);
    }

    selectRealm(id) {
      if (!this.isActive(id)) return;
      this.setFocus(id);
      this.touch();
    }

    click(x, y) {
      const hit = this.hits.find(h => x >= h.x0 && x <= h.x1 && y >= h.y0 && y <= h.y1);
      if (hit) this.selectRealm(hit.id);
    }

    summon(type) {
      if (['dragon', 'storm', 'tornado', 'battle', 'serpent', 'whale'].includes(type)) this.spawn(type);
    }

    /* ------------------------------------------------------------------ terrain */
    buildTerrain() {
      const step = this.q.grid;                   // heightmap spacing, sampled bilinearly
      const W = Math.round(WORLD_W / step), H = Math.round(WORLD_H / step);
      this.grid = { W, H, step, h: new Float32Array(W * H) };
      for (let j = 0; j < H; j++) for (let i = 0; i < W; i++) {
        this.grid.h[j * W + i] = elevation(i * step - WORLD_W / 2, j * step - WORLD_H / 2);
      }
    }

    heightAt(x, y) {
      const { W, H, h, step } = this.grid;
      const gx = clamp((x + WORLD_W / 2) / step, 0, W - 1.001), gy = clamp((y + WORLD_H / 2) / step, 0, H - 1.001);
      const i = Math.floor(gx), j = Math.floor(gy), fx = gx - i, fy = gy - j;
      const a = h[j * W + i], b = h[j * W + i + 1], c = h[(j + 1) * W + i], d = h[(j + 1) * W + i + 1];
      return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy;
    }

    buildScenery() {
      const rand = rng(304);
      this.sprites = [];
      const add = (type, x, y, extra) => this.sprites.push({ type, x, y, h: Math.max(0, this.heightAt(x, y)), ...extra });
      // mountains on high ground (rejection sampling), each slightly asymmetric
      for (let n = 0; n < 4000 && this.sprites.length < 64; n++) {
        const x = (rand() - 0.5) * 900, y = (rand() - 0.5) * 640, h = this.heightAt(x, y);
        if (h > 17 && !this.sprites.some(s => Math.hypot(s.x - x, s.y - y) < 24)) {
          add('mountain', x, y, { size: 9 + h * 0.42, lean: (rand() - 0.5) * 0.35, tone: rand() });
        }
      }
      // groves: small clusters of trees (broadleaf in the warm south, conifers in the north and west)
      let trees = 0;
      for (let n = 0; n < 6000 && trees < 170; n++) {
        const x = (rand() - 0.5) * 900, y = (rand() - 0.5) * 640, h = this.heightAt(x, y);
        if (h < 1.8 || h > 13) continue;
        const o = owner(x, y);
        const p = o === 'sylvan' ? 0.16 : o === 'umbra' || o === 'aethelgard' ? 0.03 : 0.012;
        if (rand() > p) continue;
        const kind = (o === 'aethelgard' || o === 'umbra' || y < -120) ? 'conifer' : 'broadleaf';
        const count = 2 + Math.floor(rand() * 4);
        for (let k = 0; k < count; k++) {
          const tx = x + (rand() - 0.5) * 22, ty = y + (rand() - 0.5) * 14;
          const th = this.heightAt(tx, ty);
          if (th < 1.2 || th > 14) continue;
          add('tree', tx, ty, { kind, size: 5 + rand() * 2.5, tone: rand() });
          trees++;
        }
      }
      // settlements, nudged onto suitable land if a coordinate falls in water or on a peak
      this.settlements = {};
      for (const [id, name, sx, sy, capital] of SETTLEMENTS) {
        const [x, y] = this.placeOnLand(sx, sy);
        this.settlements[name] = { id, name, x, y, capital: !!capital };
        add('city', x, y, { id, name, capital: !!capital, seed: name.length * 7 + name.charCodeAt(0) });
      }
      // keep groves and mountains from growing through towns
      this.sprites = this.sprites.filter(sp => sp.type === 'city' || !Object.values(this.settlements)
        .some(t => Math.hypot(t.x - sp.x, t.y - sp.y) < (t.capital ? 26 : 18)));
      this.buildRoads();

      [[-160, -230], [20, -250], [-30, -170]].forEach(([x, y]) => add('castle', x, y));
      [[240, 60], [320, -10]].forEach(([x, y]) => add('temple', x, y));
      add('spire', SPIRE[0], SPIRE[1]);
      for (const [id, [x, y]] of Object.entries(CAPITALS)) add('capital', x, y, { id });

      // rivers: follow the slope downhill from highland springs to the sea
      this.rivers = [[215, -150], [160, -175], [-90, -225], [-300, -60], [25, -45], [290, 15], [-200, 60]]
        .map(([sx, sy]) => this.traceRiver(sx, sy, rand)).filter(r => r.length > 25);

      // water sparkle points
      this.sparkles = [];
      for (let n = 0; n < 6000 && this.sparkles.length < 150; n++) {
        const x = (rand() - 0.5) * 1100, y = (rand() - 0.5) * 820;
        if (this.heightAt(x, y) < -2) this.sparkles.push({ x, y, phase: rand() * 6.28 });
      }
      // ships: elliptical routes through the seas
      this.ships = [
        { cx: 240, cy: 255, rx: 210, ry: 18, speed: 0.018, phase: 0 },
        { cx: -120, cy: 300, rx: 260, ry: 26, speed: -0.012, phase: 2 },
        { cx: -420, cy: -40, rx: 40, ry: 260, speed: 0.01, phase: 4 },
        { cx: 60, cy: -330, rx: 320, ry: 22, speed: 0.011, phase: 1 },
      ];
      this.clouds = Array.from({ length: 8 }, (_, i) => ({ x: -900 + i * 225 + rand() * 80, y: -300 + rand() * 600, s: 0.8 + rand() * 0.9 }));
    }

    placeOnLand(x, y) {
      const ok = (px, py) => { const h = this.heightAt(px, py); return h > 1.6 && h < 22; };
      if (ok(x, y)) return [x, y];
      for (let r = 8; r <= 90; r += 8) for (let a = 0; a < 6.283; a += 0.5) {
        const px = x + Math.cos(a) * r, py = y + Math.sin(a) * r;
        if (ok(px, py)) return [px, py];
      }
      return [x, y];
    }

    // Roads are routed with A* over a coarse cost grid: cheap across lowland, dearer uphill,
    // impossible over water, and cheaper along existing roads so the network merges naturally.
    buildRoads() {
      const C = 8, GW = Math.floor(WORLD_W / C), GH = Math.floor(WORLD_H / C);
      const cost = new Float32Array(GW * GH);
      for (let j = 0; j < GH; j++) for (let i = 0; i < GW; i++) {
        const x = i * C - WORLD_W / 2 + C / 2, y = j * C - WORLD_H / 2 + C / 2, h = this.heightAt(x, y);
        const slope = Math.hypot(this.heightAt(x + 4, y) - this.heightAt(x - 4, y), this.heightAt(x, y + 4) - this.heightAt(x, y - 4));
        cost[j * GW + i] = h < 0.8 ? Infinity : 1 + slope * 0.6 + (h > 22 ? (h - 22) * 0.5 : 0);
      }
      const idx = (x, y) => clamp(Math.floor((y + WORLD_H / 2) / C), 0, GH - 1) * GW + clamp(Math.floor((x + WORLD_W / 2) / C), 0, GW - 1);
      const centre = n => [(n % GW) * C - WORLD_W / 2 + C / 2, Math.floor(n / GW) * C - WORLD_H / 2 + C / 2];
      const place = name => name === 'SPIRE' ? { x: SPIRE[0], y: SPIRE[1] } : this.settlements[name];

      const astar = (a, b) => {
        const start = idx(a.x, a.y), goal = idx(b.x, b.y);
        const g = new Float32Array(GW * GH).fill(Infinity), from = new Int32Array(GW * GH).fill(-1);
        const heap = [];   // binary heap of [f, node]
        const push = (f, n) => { heap.push([f, n]); let i = heap.length - 1; while (i > 0) { const p = (i - 1) >> 1; if (heap[p][0] <= heap[i][0]) break; [heap[p], heap[i]] = [heap[i], heap[p]]; i = p; } };
        const pop = () => { const top = heap[0], last = heap.pop(); if (heap.length) { heap[0] = last; let i = 0; for (;;) { const l = 2 * i + 1, r = l + 1; let m = i; if (l < heap.length && heap[l][0] < heap[m][0]) m = l; if (r < heap.length && heap[r][0] < heap[m][0]) m = r; if (m === i) break; [heap[m], heap[i]] = [heap[i], heap[m]]; i = m; } } return top; };
        const [gx, gy] = [goal % GW, Math.floor(goal / GW)];
        g[start] = 0; push(0, start);
        while (heap.length) {
          const [, n] = pop();
          if (n === goal) break;
          const nx = n % GW, ny = Math.floor(n / GW);
          for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
            if (!dx && !dy) continue;
            const mx = nx + dx, my = ny + dy;
            if (mx < 0 || my < 0 || mx >= GW || my >= GH) continue;
            const mI = my * GW + mx;
            const c = mI === goal ? 1 : cost[mI];
            if (!isFinite(c)) continue;
            const ng = g[n] + c * (dx && dy ? 1.414 : 1);
            if (ng < g[mI]) { g[mI] = ng; from[mI] = n; push(ng + Math.hypot(mx - gx, my - gy) * 0.9, mI); }
          }
        }
        if (from[goal] < 0) return null;
        const path = [];
        for (let n = goal; n !== -1; n = from[n]) { path.push(centre(n)); cost[n] = Math.min(cost[n], 0.55); }
        path.reverse();
        path[0] = [a.x, a.y]; path[path.length - 1] = [b.x, b.y];
        return path;
      };
      const chaikin = pts => {
        let p = pts;
        for (let it = 0; it < 2; it++) {
          const q = [p[0]];
          for (let i = 0; i < p.length - 1; i++) {
            const [x0, y0] = p[i], [x1, y1] = p[i + 1];
            q.push([x0 * 0.75 + x1 * 0.25, y0 * 0.75 + y1 * 0.25], [x0 * 0.25 + x1 * 0.75, y0 * 0.25 + y1 * 0.75]);
          }
          q.push(p[p.length - 1]); p = q;
        }
        return p;
      };
      this.roads = [];
      for (const [a, b] of ROADS) {
        const A = place(a), B = place(b);
        if (!A || !B) continue;
        const path = astar(A, B);
        if (path && path.length > 2) this.roads.push({ from: a, to: b, pts: chaikin(path) });
      }
      this.seaLanes = SEA_LANES.map(([a, b]) => [place(a), place(b)]).filter(([a, b]) => a && b);
      // travellers: one cart per road, moving back and forth at walking pace
      this.carts = this.roads.map((road, i) => {
        let len = 0; const acc = [0];
        for (let k = 1; k < road.pts.length; k++) { len += Math.hypot(road.pts[k][0] - road.pts[k - 1][0], road.pts[k][1] - road.pts[k - 1][1]); acc.push(len); }
        return { road, acc, len, u: (i * 0.37) % 1, dir: i % 2 ? 1 : -1 };
      });
    }

    traceRiver(x, y, rand) {
      const pts = [[x, y]];
      let dx = 0, dy = 0, lastH = this.heightAt(x, y), stuck = 0;
      for (let i = 0; i < 600; i++) {
        const gx = this.heightAt(x + 2, y) - this.heightAt(x - 2, y);
        const gy = this.heightAt(x, y + 2) - this.heightAt(x, y - 2);
        const g = Math.hypot(gx, gy) || 1;
        // downhill + momentum + a little wander so rivers meander
        dx = dx * 0.55 - gx / g * 0.45 + (rand() - 0.5) * 0.35;
        dy = dy * 0.55 - gy / g * 0.45 + (rand() - 0.5) * 0.35;
        const d = Math.hypot(dx, dy) || 1;
        x += dx / d * 3; y += dy / d * 3;
        pts.push([x, y]);
        const h = this.heightAt(x, y);
        if (h < -0.6) break;                       // reached the sea
        stuck = h >= lastH - 0.01 ? stuck + 1 : 0;
        if (stuck > 40) break;                     // ends in a lake basin
        lastH = Math.min(lastH, h);
      }
      return pts;
    }

    /* ------------------------------------------------- the illustrated texture */
    paintTexture() {
      const S = this.q.tex, TW = Math.round(WORLD_W * S), TH = Math.round(WORLD_H * S);
      const tex = this.texture || (this.texture = document.createElement('canvas'));
      tex.width = TW; tex.height = TH;
      const tctx = tex.getContext('2d');
      const img = tctx.createImageData(TW, TH);
      const data = img.data;
      const rand = rng(77);
      const tint = {};
      for (const id of Object.keys(CAPITALS)) {
        const r = this.realms[id];
        tint[id] = r && r.active !== false ? hexRgb((r.theme_color || DEFAULT_COLORS[id])) : null;
      }
      // 1. sample the height of every pixel once; shading and coastlines reuse it
      const H = new Float32Array(TW * TH);
      for (let py = 0; py < TH; py++) {
        const y = py / S - WORLD_H / 2;
        for (let px = 0; px < TW; px++) H[py * TW + px] = this.heightAt(px / S - WORLD_W / 2, y);
      }
      const d = Math.max(1, Math.round(2 * S));     // shading baseline: about 2 world units
      const owners = new Array(TW * TH);
      for (let py = 0; py < TH; py++) {
        for (let px = 0; px < TW; px++) {
          const i = py * TW + px, h = H[i];
          let c;
          if (h < 0) {
            const t = clamp(-h / 14, 0, 1);
            c = mix(SEA_SHALLOW, SEA_DEEP, Math.pow(t, 0.7));
            if (h > -1.2) c = mix(c, [232, 238, 226], 0.55);       // surf
          } else {
            // biome by height
            if (h < 1.2) c = [226, 214, 172];                       // beach
            else if (h < 7) c = mix([178, 196, 132], [160, 170, 110], h / 7);
            else if (h < 18) c = mix([160, 170, 110], [168, 150, 108], (h - 7) / 11);
            else if (h < 34) c = mix([150, 132, 104], [126, 112, 98], (h - 18) / 16);
            else c = mix([200, 196, 186], [246, 242, 232], clamp((h - 34) / 10, 0, 1));
            const o = owner(px / S - WORLD_W / 2, py / S - WORLD_H / 2);
            owners[i] = o;
            const t = tint[o];
            if (t) c = mix(c, t, 0.30);
            else c = mix(mix(c, [205, 196, 176], 0.65), [190, 182, 166], 0.2);   // unclaimed: faded parchment
            // hill shading (light from the north-west)
            const dx = H[py * TW + Math.min(TW - 1, px + d)] - H[py * TW + Math.max(0, px - d)];
            const dy = H[Math.min(TH - 1, py + d) * TW + px] - H[Math.max(0, py - d) * TW + px];
            const shade = clamp(1 + (-dx - dy) * 0.045, 0.62, 1.25);
            c = [c[0] * shade, c[1] * shade, c[2] * shade];
          }
          const grain = (rand() - 0.5) * 7;                          // paper grain
          const k = i * 4;
          data[k] = clamp(c[0] + grain, 0, 255); data[k + 1] = clamp(c[1] + grain, 0, 255);
          data[k + 2] = clamp(c[2] + grain, 0, 255); data[k + 3] = 255;
        }
      }
      // borders: dashed ink where ownership changes
      const dash = Math.round(9 * S), gap = Math.round(6 * S);
      for (let py = 1; py < TH - 1; py++) for (let px = 1; px < TW - 1; px++) {
        const o = owners[py * TW + px];
        if (!o) continue;
        const r = owners[py * TW + px + 1], dn = owners[(py + 1) * TW + px];
        if ((r && r !== o) || (dn && dn !== o)) {
          if ((px + py) % dash > gap) continue;
          const k = (py * TW + px) * 4;
          data[k] *= 0.45; data[k + 1] *= 0.42; data[k + 2] *= 0.4;
        }
      }
      tctx.putImageData(img, 0, 0);
      // rivers: tapered, widening towards the sea, with a pale highlight
      tctx.save();
      tctx.scale(S, S);                         // rivers and roads are drawn in world units
      tctx.translate(WORLD_W / 2, WORLD_H / 2);
      tctx.lineCap = 'round'; tctx.lineJoin = 'round';
      for (const river of this.rivers) {
        for (let i = 1; i < river.length; i++) {
          const t = i / river.length;
          tctx.strokeStyle = 'rgba(70,122,150,0.95)';
          tctx.lineWidth = 1.6 + t * 5;
          tctx.beginPath(); tctx.moveTo(river[i - 1][0], river[i - 1][1]); tctx.lineTo(river[i][0], river[i][1]); tctx.stroke();
        }
        tctx.strokeStyle = 'rgba(205,230,232,0.6)'; tctx.lineWidth = 1;
        tctx.beginPath(); river.forEach(([rx, ry], i) => tctx[i ? 'lineTo' : 'moveTo'](rx - 0.6, ry - 0.6)); tctx.stroke();
      }
      // roads: a pale track with a dashed brown centre line, like an old map
      const trace = pts => { tctx.beginPath(); pts.forEach(([rx, ry], i) => tctx[i ? 'lineTo' : 'moveTo'](rx, ry)); };
      for (const road of this.roads) {
        tctx.setLineDash([]);
        tctx.strokeStyle = 'rgba(238,224,186,0.85)'; tctx.lineWidth = 3.6; trace(road.pts); tctx.stroke();
        tctx.strokeStyle = 'rgba(122,90,52,0.9)'; tctx.lineWidth = 1.3; tctx.setLineDash([5, 3]); trace(road.pts); tctx.stroke();
      }
      // sea lanes for Aquila's ships
      tctx.strokeStyle = 'rgba(70,95,110,0.55)'; tctx.lineWidth = 1.4; tctx.setLineDash([2, 6]);
      for (const [a, b] of this.seaLanes) {
        tctx.beginPath(); tctx.moveTo(a.x, a.y);
        tctx.quadraticCurveTo((a.x + b.x) / 2 + (b.y - a.y) * 0.2, (a.y + b.y) / 2 - (b.x - a.x) * 0.2, b.x, b.y);
        tctx.stroke();
      }
      tctx.setLineDash([]);
      tctx.restore();
      // coastline ink
      tctx.globalCompositeOperation = 'multiply';
      tctx.strokeStyle = 'rgba(90,65,34,0.55)';
      tctx.lineWidth = 1.4 * S;
      tctx.beginPath();
      const cs = Math.max(1, Math.round(S));    // one ink mark per world unit along the coast
      for (let py = 0; py < TH - d; py += cs) for (let px = 0; px < TW - d; px += cs) {
        if (H[py * TW + px] < 0) continue;
        if (H[py * TW + px + d] < 0 || H[(py + d) * TW + px] < 0) { tctx.moveTo(px, py); tctx.lineTo(px + cs * 0.6, py + cs * 0.6); }
      }
      tctx.stroke();
      tctx.globalCompositeOperation = 'source-over';
      // fade texture edges into the open sea so the rotating rectangle never shows
      const fade = (x0, y0, x1, y1) => {
        const g = tctx.createLinearGradient(x0, y0, x1, y1);
        g.addColorStop(0, BG); g.addColorStop(1, 'rgba(120,164,176,0)');
        return g;
      };
      const F = 60 * S;
      tctx.fillStyle = fade(0, 0, 0, F); tctx.fillRect(0, 0, TW, F);
      tctx.fillStyle = fade(0, TH, 0, TH - F); tctx.fillRect(0, TH - F, TW, F);
      tctx.fillStyle = fade(0, 0, F, 0); tctx.fillRect(0, 0, F, TH);
      tctx.fillStyle = fade(TW, 0, TW - F, 0); tctx.fillRect(TW - F, 0, F, TH);
      this.paintedAt = performance.now();
    }

    /* ------------------------------------------------------------ state input */
    update(state) {
      const realms = (state && state.realms) || [];
      this.realms = Object.fromEntries(realms.map(r => [r.id, r]));
      this.trades = (state && state.trades) || [];
      const key = realms.map(r => `${r.id}:${r.active !== false}:${r.theme_color}`).join(',');
      if (key !== this.rosterKey) {
        this.rosterKey = key;
        this.paintTexture();
        if (this.focus && !this.isActive(this.focus)) this.setFocus(null);
      }
    }

    isActive(id) { const r = this.realms[id]; return !!r && r.active !== false; }

    setFocus(id) {
      this.focus = id;
      const [x, y] = id ? CAPITALS[id] : [0, 10];
      this.cam.tx = id ? x * 0.75 : 0;
      this.cam.ty = id ? y * 0.75 : 10;
      this.cam.tzoom = id ? 1.32 : 1;
      if (this.onFocus) this.onFocus(id);
    }

    /* ---------------------------------------------------------------- camera */
    resize() {
      const r = this.canvas.getBoundingClientRect();
      this.W = Math.max(320, r.width); this.H = Math.max(240, r.height);
      this.dpr = Math.min(window.devicePixelRatio || 1, this.q.dpr);
      this.canvas.width = Math.round(this.W * this.dpr); this.canvas.height = Math.round(this.H * this.dpr);
      // fit the continent (~940 x 640 world units) into the visible area, leaving room for the side panel
      this.baseScale = Math.min(this.W * 0.62 / 940, this.H / (640 * this.cam.tilt) * 0.82);
      this.centerX = this.W * 0.38;
      // Lettering scales with the screen: readable on a projector, never swamping the terrain.
      this.ui = clamp(this.W / 1500, 0.72, 1.2);
      this.centerY = this.H * 0.47;
    }

    project(x, y, h = 0) {
      const c = this.cam, s = this.baseScale * c.zoom;
      const dx = x - c.x, dy = y - c.y;
      const cos = Math.cos(c.yaw), sin = Math.sin(c.yaw);
      const rx = dx * cos - dy * sin, ry = dx * sin + dy * cos;
      return { x: this.centerX + rx * s, y: this.centerY + ry * s * c.tilt - h * s * 1.4, depth: ry };
    }

    /* ----------------------------------------------------------------- frame */
    frame(now) {
      // Low mode draws at most 30 frames per second.
      if (this.q.fps < 60 && now - this.lastDraw < 1000 / this.q.fps - 2) {
        requestAnimationFrame(t => this.frame(t));
        return;
      }
      this.lastDraw = now;
      this.probeFrameRate(now);
      const dt = Math.min(0.05, (now - this.last) / 1000);
      this.last = now;
      this.time = now / 1000;
      const motion = this.reduceMotion ? 0.15 : 1;

      // camera: slow orbit with gentle swaying, gliding between nations
      const c = this.cam;
      if (!this.manual) c.yaw += dt * 0.022 * motion;
      c.tilt = 0.6 + 0.04 * Math.sin(this.time * 0.13);
      c.x += (c.tx - c.x) * dt * 0.6;
      c.y += (c.ty - c.y) * dt * 0.6;
      c.zoom += (c.tzoom - c.zoom) * dt * 0.6;
      if (!this.manual) this.tourClock += dt;
      if (this.tourClock > 12) {
        this.tourClock = 0;
        const active = Object.keys(CAPITALS).filter(id => this.isActive(id));
        this.tourStep = (this.tourStep + 1) % (active.length + 1);
        this.setFocus(this.tourStep === active.length ? null : active[this.tourStep]);
      }

      this.updateEvents(dt * motion);
      this.draw();
      requestAnimationFrame(t => this.frame(t));
    }

    draw() {
      const ctx = this.ctx, c = this.cam, s = this.baseScale * c.zoom;
      ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
      ctx.fillStyle = BG;
      ctx.fillRect(0, 0, this.W, this.H);

      // 1. terrain texture through the camera (rotate, then flatten for the tilt)
      ctx.save();
      ctx.translate(this.centerX, this.centerY);
      ctx.scale(s, s * c.tilt);
      ctx.rotate(c.yaw);
      ctx.translate(-c.x, -c.y);
      ctx.imageSmoothingQuality = 'high';
      ctx.drawImage(this.texture, -WORLD_W / 2, -WORLD_H / 2, WORLD_W, WORLD_H);
      ctx.restore();

      if (this.q.glints) this.drawRiverGlints(ctx);
      if (this.q.sparkles) this.drawSparkles(ctx, s);
      this.drawEvents(ctx, s, 'sea');
      this.drawShips(ctx, s);
      this.drawCarts(ctx, s);
      this.drawTrades(ctx, s);
      this.drawWars(ctx, s);
      this.hits = [];

      // 2. upright scenery and banners, back to front
      const items = this.sprites.map(sp => ({ sp, p: this.project(sp.x, sp.y, sp.h) }));
      items.sort((a, b) => a.p.depth - b.p.depth);
      for (const { sp, p } of items) this.drawSprite(ctx, sp, p, s);
      for (const { sp, p } of items) if (sp.type === 'capital') this.drawBanner(ctx, sp.id, p, s);

      this.drawEvents(ctx, s, 'air');
      if (this.q.birds) this.drawBirds(ctx, s);
      this.drawClouds(ctx, s);
      if (this.flash > 0) {                                           // lightning lights up the whole map
        ctx.fillStyle = `rgba(255,255,245,${this.flash * 0.18})`;
        ctx.fillRect(0, 0, this.W, this.H);
        this.flash = Math.max(0, this.flash - 0.12);
      }
    }

    /* ------------------------------------------------------- living details */
    drawCarts(ctx, s) {
      const k = Math.max(0.6, s);
      for (const cart of this.carts) {
        cart.u += cart.dir * (5 / cart.len) * 0.016 * (this.reduceMotion ? 0.2 : 1);
        if (cart.u > 1 || cart.u < 0) { cart.dir *= -1; cart.u = clamp(cart.u, 0, 1); }
        const d = cart.u * cart.len, pts = cart.road.pts;
        let i = 1; while (i < cart.acc.length - 1 && cart.acc[i] < d) i++;
        const f = (d - cart.acc[i - 1]) / Math.max(0.001, cart.acc[i] - cart.acc[i - 1]);
        const x = pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * f, y = pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * f;
        const p = this.project(x, y, Math.max(0, this.heightAt(x, y)));
        ctx.fillStyle = 'rgba(50,35,20,0.25)'; ctx.beginPath(); ctx.ellipse(p.x + 1, p.y + 1, 3 * k, 1.2 * k, 0, 0, 6.283); ctx.fill();
        ctx.fillStyle = '#7a5532'; ctx.fillRect(p.x - 2.5 * k, p.y - 3 * k, 5 * k, 2.6 * k);
        ctx.fillStyle = '#efe3c4'; ctx.fillRect(p.x - 2 * k, p.y - 5 * k, 4 * k, 2.2 * k);
      }
    }

    drawRiverGlints(ctx) {
      ctx.save();
      ctx.strokeStyle = 'rgba(255,255,255,0.4)'; ctx.lineWidth = 1;
      ctx.setLineDash([2, 22]); ctx.lineDashOffset = -this.time * 3.5;   // a lazy, gentle current
      for (const river of this.rivers) {
        ctx.beginPath();
        for (let i = 0; i < river.length; i += 2) {
          const p = this.project(river[i][0], river[i][1], 0);
          ctx[i ? 'lineTo' : 'moveTo'](p.x, p.y);
        }
        ctx.stroke();
      }
      ctx.restore();
    }

    seaSpot(minDepth = 7) {
      for (let n = 0; n < 200; n++) {
        const a = Math.random() * 6.283, r = 300 + Math.random() * 230;
        const x = Math.cos(a) * r * 1.05, y = Math.sin(a) * r * 0.75 + 10;
        if (this.heightAt(x, y) < -minDepth && this.heightAt(x + 40, y) < -3 && this.heightAt(x - 40, y) < -3) return [x, y];
      }
      return [-430, 300];
    }

    // A battle has been fought: draw a burning arc from the attacker's capital to the defender's for a while.
    addWar(attackerId, defenderId, outcome) {
      if (!CAPITALS[attackerId] || !CAPITALS[defenderId]) return;
      this.wars.push({ a: attackerId, d: defenderId, age: 0, dur: 30, outcome });
      if (this.wars.length > 4) this.wars.shift();
    }

    drawWars(ctx, s) {
      for (const w of this.wars) {
        const A = CAPITALS[w.a], D = CAPITALS[w.d];
        const vis = Math.min(1, w.age / 1.5, (w.dur - w.age) / 3);
        const pa = this.project(A[0], A[1], 6), pb = this.project(D[0], D[1], 6);
        const mx = (pa.x + pb.x) / 2, my = (pa.y + pb.y) / 2 - 80 * s;
        const wonByAttacker = /^attacker/.test(w.outcome);
        ctx.save();
        ctx.globalAlpha = vis;
        ctx.strokeStyle = 'rgba(190,48,36,0.9)'; ctx.lineWidth = 3.5; ctx.setLineDash([10, 7]); ctx.lineDashOffset = -this.time * 44;
        ctx.beginPath(); ctx.moveTo(pa.x, pa.y); ctx.quadraticCurveTo(mx, my, pb.x, pb.y); ctx.stroke();
        ctx.setLineDash([]);
        for (let i = 0; i < 5; i++) {                                    // embers racing along the arc
          const u = (this.time * 0.35 + i * 0.2) % 1;
          const qx = (1 - u) * (1 - u) * pa.x + 2 * (1 - u) * u * mx + u * u * pb.x;
          const qy = (1 - u) * (1 - u) * pa.y + 2 * (1 - u) * u * my + u * u * pb.y;
          ctx.fillStyle = i % 2 ? '#ffb347' : '#ff6a3d';
          ctx.beginPath(); ctx.arc(qx, qy, 3.5, 0, 6.283); ctx.fill();
        }
        // shockwaves ring the nation that took the brunt of it
        const loser = wonByAttacker ? pb : pa;
        for (let k = 0; k < 3; k++) {
          const r = ((this.time * 0.6 + k / 3) % 1);
          ctx.strokeStyle = `rgba(190,48,36,${(1 - r) * 0.7})`; ctx.lineWidth = 2.5;
          ctx.beginPath(); ctx.ellipse(loser.x, loser.y, (14 + r * 46) * s * 1.2, (6 + r * 20) * s * 1.2, 0, 0, 6.283); ctx.stroke();
        }
        ctx.restore();
      }
    }

    updateEvents(dt) {
      for (const w of this.wars) w.age += dt;
      this.wars = this.wars.filter(w => w.age < w.dur);
      this.eventClock += dt;
      for (const ev of this.events) ev.age += dt;
      this.events = this.events.filter(ev => ev.age < ev.dur);
      if (this.eventClock >= this.nextEvent && this.events.length < 2) {
        const type = this.eventQueue.shift();
        this.eventQueue.push(type);
        this.spawn(type);
        this.nextEvent = this.eventClock + 9 + Math.random() * 10;
      }
      for (const f of this.flocks) { f.x += f.speed * dt; if (f.x > 700) { f.x = -700; f.y = -250 + Math.random() * 500; } }
    }

    spawn(type) {
      const ev = { type, age: 0 };
      if (type === 'dragon') {
        const a = Math.random() * 6.283, off = (Math.random() - 0.5) * 260;
        const dx = Math.cos(a), dy = Math.sin(a);
        ev.from = [-dx * 760 - dy * off, -dy * 560 + dx * off];
        ev.to = [dx * 760 - dy * off, dy * 560 + dx * off];
        ev.dur = 24; ev.color = Math.random() < 0.5 ? [150, 48, 40] : [52, 100, 72];
      } else if (type === 'serpent') {
        ev.at = this.seaSpot(8); ev.dir = Math.random() * 6.283; ev.dur = 11;
      } else if (type === 'whale') {
        ev.at = this.seaSpot(6); ev.dur = 7;
      } else if (type === 'battle') {
        const [x, y] = this.seaSpot(5);
        const playing = Object.keys(CAPITALS).filter(id => this.isActive(id));
        const pick = () => (this.realms[playing[Math.floor(Math.random() * playing.length)]] || {}).theme_color || '#8c7a5e';
        ev.a = [x - 22, y]; ev.b = [x + 22, y + 6]; ev.colors = [pick(), pick()];
        ev.dur = 16; ev.loser = Math.random() < 0.5 ? 0 : 1;
      } else if (type === 'storm') {
        // sweeps right across the continent, from the sea on one side to the sea on the other
        const a = Math.random() * 6.283, dx = Math.cos(a), dy = Math.sin(a), off = (Math.random() - 0.5) * 240;
        ev.from = [-dx * 540 - dy * off, -dy * 390 + dx * off];
        ev.to = [dx * 540 - dy * off, dy * 390 + dx * off];
        ev.dur = 46; ev.bolts = []; ev.nextBolt = 4;
      } else if (type === 'tornado') {
        let x = 0, y = 0;
        for (let n = 0; n < 100; n++) {                               // start somewhere on land
          x = (Math.random() - 0.5) * 600; y = (Math.random() - 0.5) * 380;
          if (this.heightAt(x, y) > 2 && this.heightAt(x, y) < 14) break;
        }
        ev.at = [x, y]; ev.dir = Math.random() * 6.283; ev.dur = 24;
      }
      this.events.push(ev);
    }

    drawEvents(ctx, s, layer) {
      for (const ev of this.events) {
        const t = ev.age / ev.dur;
        const vis = Math.min(1, ev.age / 1.5, (ev.dur - ev.age) / 1.5);   // fade in and out
        if (ev.type === 'dragon') this.drawDragonEvent(ctx, s, ev, t, vis, layer);
        else if (layer !== 'sea') continue;
        else if (ev.type === 'serpent') this.drawSerpent(ctx, s, ev, vis);
        else if (ev.type === 'whale') this.drawWhale(ctx, s, ev, vis);
        else if (ev.type === 'battle') this.drawBattle(ctx, s, ev, vis);
      }
      for (const ev of this.events) {
        const vis = Math.min(1, ev.age / 2.5, (ev.dur - ev.age) / 2.5);
        if (ev.type === 'storm') this.drawStorm(ctx, s, ev, vis, layer);
        else if (ev.type === 'tornado') this.drawTornado(ctx, s, ev, vis, layer);
      }
    }

    drawDragonEvent(ctx, s, ev, t, vis, layer) {
      const x = ev.from[0] + (ev.to[0] - ev.from[0]) * t, y = ev.from[1] + (ev.to[1] - ev.from[1]) * t;
      const alt = 95 + 15 * Math.sin(ev.age * 0.8);
      if (layer === 'sea') {                                    // shadow gliding over land and sea
        const g = this.project(x, y, 0), k = Math.max(0.9, s * 1.5);
        ctx.fillStyle = `rgba(40,30,20,${0.18 * vis})`;
        ctx.beginPath(); ctx.ellipse(g.x, g.y, 26 * k, 7 * k, 0, 0, 6.283); ctx.fill();
        return;
      }
      const p = this.project(x, y, alt), q = this.project(x + (ev.to[0] - ev.from[0]) * 0.01, y + (ev.to[1] - ev.from[1]) * 0.01, alt);
      let ang = Math.atan2(q.y - p.y, q.x - p.x);
      const left = Math.abs(ang) > Math.PI / 2;
      if (left) ang = Math.PI - ang;                                  // mirror instead of flying upside down
      ang = Math.max(-0.45, Math.min(0.45, ang > Math.PI ? ang - 2 * Math.PI : ang));
      const k = Math.max(0.9, s * 1.5);
      // wing beat: up-stroke to down-stroke, never swinging through the body
      const beat = Math.sin(ev.age * 4.2);
      const span = 0.55 + 0.45 * beat;                                // 0.1 (folded down) .. 1 (raised)
      const [r, g, b] = ev.color;
      ctx.save();
      ctx.globalAlpha = vis;
      ctx.translate(p.x, p.y + beat * 1.5 * k);                       // body bobs with each beat
      if (left) ctx.scale(-1, 1);
      ctx.rotate(ang);
      const body = `rgb(${r},${g},${b})`;
      const wingFar = `rgba(${r * 0.75 | 0},${g * 0.75 | 0},${b * 0.75 | 0},0.92)`;
      const wingNear = `rgba(${Math.min(255, r + 45)},${Math.min(255, g + 35)},${Math.min(255, b + 30)},0.95)`;
      const wing = (fill, reach, lift) => {
        // shoulder at (2,-2); bat-like wing with three finger tips
        const tipY = -6 * k - 22 * k * lift, midY = -4 * k - 14 * k * lift;
        ctx.fillStyle = fill;
        ctx.beginPath();
        ctx.moveTo(4 * k, -2 * k);
        ctx.quadraticCurveTo(-2 * k * reach, midY, -10 * k * reach, tipY);
        ctx.lineTo(-13 * k * reach, midY + 4 * k);
        ctx.lineTo(-17 * k * reach, tipY + 9 * k);
        ctx.lineTo(-19 * k * reach, midY + 9 * k);
        ctx.quadraticCurveTo(-10 * k, 0, -6 * k, 0);
        ctx.closePath(); ctx.fill();
        ctx.strokeStyle = 'rgba(40,20,15,0.35)'; ctx.lineWidth = 0.8;
        ctx.beginPath(); ctx.moveTo(4 * k, -2 * k); ctx.lineTo(-10 * k * reach, tipY); ctx.stroke();
      };
      wing(wingFar, 0.85, span * 0.8);                                 // far wing, slightly behind
      // tail
      ctx.strokeStyle = body; ctx.lineWidth = 3 * k; ctx.lineCap = 'round';
      ctx.beginPath(); ctx.moveTo(-10 * k, 0); ctx.quadraticCurveTo(-22 * k, 5 * k * Math.sin(ev.age * 1.6), -32 * k, 2 * k); ctx.stroke();
      ctx.fillStyle = body;
      ctx.beginPath(); ctx.moveTo(-32 * k, 2 * k); ctx.lineTo(-38 * k, -2 * k); ctx.lineTo(-37 * k, 6 * k); ctx.closePath(); ctx.fill();
      // body, neck and head
      ctx.beginPath(); ctx.ellipse(0, 0, 13 * k, 4.5 * k, 0, 0, 6.283); ctx.fill();
      ctx.lineWidth = 3.2 * k;
      ctx.beginPath(); ctx.moveTo(10 * k, -1 * k); ctx.quadraticCurveTo(16 * k, -6 * k, 21 * k, -5 * k); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(19 * k, -8 * k); ctx.lineTo(28 * k, -5 * k); ctx.lineTo(19 * k, -2 * k); ctx.closePath(); ctx.fill();
      ctx.fillStyle = '#ffd36b'; ctx.beginPath(); ctx.arc(22 * k, -5.5 * k, 0.9 * k, 0, 6.283); ctx.fill();
      wing(wingNear, 1, span);                                         // near wing in front
      // a puff of fire now and then
      const fire = (ev.age % 7) / 7;
      if (fire > 0.55 && fire < 0.7) {
        const f = (fire - 0.55) / 0.15;
        const grd = ctx.createRadialGradient(34 * k, -5 * k, 1, 34 * k + 14 * k * f, -5 * k, 12 * k);
        grd.addColorStop(0, 'rgba(255,240,170,0.95)'); grd.addColorStop(0.5, 'rgba(255,140,40,0.8)'); grd.addColorStop(1, 'rgba(200,60,20,0)');
        ctx.fillStyle = grd; ctx.beginPath(); ctx.ellipse(34 * k + 10 * k * f, -5 * k, 14 * k * f + 3, 6 * k, 0, 0, 6.283); ctx.fill();
      }
      ctx.restore();
    }

    drawStorm(ctx, s, ev, vis, layer) {
      const t = ev.age / ev.dur;
      const x = ev.from[0] + (ev.to[0] - ev.from[0]) * t, y = ev.from[1] + (ev.to[1] - ev.from[1]) * t;
      const k = Math.max(0.8, s * 1.3);
      const g = this.project(x, y, 0), c = this.project(x, y, 115);
      const R = 95 * k;
      if (layer === 'sea') {
        // shadow of the storm on land and sea
        const sh = ctx.createRadialGradient(g.x, g.y, 0, g.x, g.y, R * 1.2);
        sh.addColorStop(0, `rgba(30,35,45,${0.32 * vis})`); sh.addColorStop(1, 'rgba(30,35,45,0)');
        ctx.fillStyle = sh; ctx.beginPath(); ctx.ellipse(g.x, g.y, R * 1.2, R * 0.55, 0, 0, 6.283); ctx.fill();
        // rain: slanted streaks falling from the cloud base to the ground
        ctx.strokeStyle = `rgba(200,212,226,${0.6 * vis})`; ctx.lineWidth = 1.1;
        ctx.beginPath();
        for (let i = 0; i < 120; i++) {
          const u = ((i * 0.6180339) % 1) * 2 - 1, w = ((i * 0.3819) % 1);
          const fall = (this.time * 1.6 + w) % 1;
          const rx = c.x + u * R * 0.9, top = c.y + 10 * k + fall * (g.y - c.y);
          ctx.moveTo(rx, top); ctx.lineTo(rx - 4 * k, top + 12 * k);
        }
        ctx.stroke();
        return;
      }
      // the thunderhead: a stack of dark puffs
      for (let i = 0; i < 7; i++) {
        const ox = Math.cos(i * 2.4 + ev.age * 0.15) * R * 0.55, oy = Math.sin(i * 2.4) * R * 0.18;
        ctx.fillStyle = `rgba(${70 + i * 6},${76 + i * 6},${90 + i * 6},${0.78 * vis})`;
        this.puff(ctx, c.x + ox, c.y + oy - i * 2 * k, R * (0.55 + (i % 3) * 0.1));
      }
      // billowing lighter tops give the thunderhead volume
      for (let i = 0; i < 5; i++) {
        const ox = Math.cos(i * 1.9 + ev.age * 0.12) * R * 0.45, oy = -R * 0.22 - (i % 2) * 6 * k;
        ctx.fillStyle = `rgba(${150 + i * 8},${154 + i * 8},${166 + i * 6},${0.5 * vis})`;
        this.puff(ctx, c.x + ox, c.y + oy, R * (0.32 + (i % 3) * 0.06));
      }
      // lightning
      if (ev.age >= ev.nextBolt && vis > 0.6) {
        ev.nextBolt = ev.age + 1.8 + Math.random() * 3;
        const pts = [[c.x + (Math.random() - 0.5) * R * 0.8, c.y + 8 * k]];
        const steps = 6;
        for (let i = 1; i <= steps; i++) {
          const f = i / steps;
          pts.push([pts[0][0] + (Math.random() - 0.5) * 24 * k + (g.x - c.x) * f * 0.2, pts[0][1] + (g.y + 6 * k - pts[0][1]) * f]);
        }
        ev.bolts.push({ pts, age: 0 });
        this.flash = 1;
      }
      ev.bolts = ev.bolts.filter(b => (b.age += 0.016) < 0.25);
      for (const bolt of ev.bolts) {
        const a = 1 - bolt.age / 0.25;
        ctx.strokeStyle = `rgba(255,250,210,${a})`; ctx.lineWidth = 2.2;
        ctx.shadowColor = 'rgba(255,255,220,0.9)'; ctx.shadowBlur = 10;
        ctx.beginPath(); bolt.pts.forEach(([px, py], i) => ctx[i ? 'lineTo' : 'moveTo'](px, py)); ctx.stroke();
        ctx.shadowBlur = 0;
      }
    }

    drawTornado(ctx, s, ev, vis, layer) {
      const k = Math.max(0.8, s * 1.3);
      // wanders slowly, weaving left and right
      const dist = ev.age * 11;
      const x = ev.at[0] + Math.cos(ev.dir) * dist + Math.sin(ev.age * 0.7) * 12;
      const y = ev.at[1] + Math.sin(ev.dir) * dist + Math.cos(ev.age * 0.5) * 8;
      const g = this.project(x, y, Math.max(0, this.heightAt(x, y)));
      if (layer === 'sea') {
        ctx.fillStyle = `rgba(120,100,70,${0.25 * vis})`;          // dust ring at the base
        ctx.beginPath(); ctx.ellipse(g.x, g.y, 20 * k, 6 * k, 0, 0, 6.283); ctx.fill();
        return;
      }
      ctx.save();
      ctx.globalAlpha = vis;
      const layers = 16, height = 110 * k;
      for (let i = layers; i >= 0; i--) {
        const f = i / layers;
        const sway = Math.sin(this.time * 2.2 + f * 3) * 8 * k * f;
        const cx = g.x + sway + f * 10 * k, cy = g.y - f * height;
        const rx = (3 + f * f * 26) * k, ry = rx * 0.3;
        ctx.fillStyle = `rgba(${150 - f * 30},${145 - f * 30},${138 - f * 25},${0.28 + f * 0.1})`;
        ctx.beginPath(); ctx.ellipse(cx, cy, rx, ry, 0, 0, 6.283); ctx.fill();
        ctx.strokeStyle = 'rgba(240,236,228,0.35)'; ctx.lineWidth = 1;
        const spin = this.time * 6 + f * 4;
        ctx.beginPath(); ctx.ellipse(cx, cy, rx, ry, 0, spin % 6.283, spin % 6.283 + 2); ctx.stroke();
      }
      // debris whirling around the base
      ctx.fillStyle = 'rgba(90,70,45,0.8)';
      for (let i = 0; i < 8; i++) {
        const a = this.time * 4 + i * 0.785, r = (8 + (i % 3) * 5) * k;
        ctx.fillRect(g.x + Math.cos(a) * r, g.y - 6 * k - (i % 4) * 5 * k + Math.sin(a) * r * 0.3, 2, 2);
      }
      ctx.restore();
    }

    ripple(ctx, p, r, a, k) {
      ctx.strokeStyle = `rgba(255,255,255,${a})`; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.ellipse(p.x, p.y, r * k, r * k * 0.35, 0, 0, 6.283); ctx.stroke();
    }

    drawSerpent(ctx, s, ev, vis) {
      const k = Math.max(0.85, s * 1.4), [x, y] = ev.at;
      const swim = ev.age * 4;                                   // moves forward slowly
      const cx = x + Math.cos(ev.dir) * swim, cy = y + Math.sin(ev.dir) * swim;
      ctx.save(); ctx.globalAlpha = vis;
      for (let i = 0; i < 4; i++) {
        const along = -i * 11;
        const p = this.project(cx + Math.cos(ev.dir) * along, cy + Math.sin(ev.dir) * along, 0);
        const rise = Math.max(0, Math.sin(ev.age * 2.2 - i * 0.9));
        this.ripple(ctx, p, 9 + (ev.age * 3 + i) % 6, 0.45 * vis, k);
        if (rise < 0.05) continue;
        ctx.fillStyle = '#3f7d6e';
        ctx.beginPath(); ctx.ellipse(p.x, p.y, 6.5 * k, 7 * k * rise, 0, Math.PI, 0); ctx.fill();
        ctx.strokeStyle = '#8fc4a6'; ctx.lineWidth = 1;
        ctx.beginPath(); ctx.ellipse(p.x, p.y, 6.5 * k, 7 * k * rise, 0, Math.PI * 1.15, Math.PI * 1.85); ctx.stroke();
      }
      // head rising at the front
      const h = this.project(cx + Math.cos(ev.dir) * 12, cy + Math.sin(ev.dir) * 12, 0);
      const up = Math.max(0, Math.sin(ev.age * 1.3));
      if (up > 0.1) {
        ctx.fillStyle = '#356b5e';
        ctx.beginPath(); ctx.moveTo(h.x - 3 * k, h.y); ctx.quadraticCurveTo(h.x - 2 * k, h.y - 14 * k * up, h.x + 6 * k, h.y - 15 * k * up);
        ctx.lineTo(h.x + 9 * k, h.y - 12 * k * up); ctx.quadraticCurveTo(h.x + 2 * k, h.y - 9 * k * up, h.x + 3 * k, h.y); ctx.closePath(); ctx.fill();
        ctx.fillStyle = '#ffe28a'; ctx.beginPath(); ctx.arc(h.x + 5 * k, h.y - 14 * k * up, 0.9 * k, 0, 6.283); ctx.fill();
      }
      ctx.restore();
    }

    drawWhale(ctx, s, ev, vis) {
      const k = Math.max(0.85, s * 1.4), p = this.project(ev.at[0] + ev.age * 2, ev.at[1], 0);
      ctx.save(); ctx.globalAlpha = vis;
      this.ripple(ctx, p, 14 + ev.age * 2, 0.4, k);
      ctx.fillStyle = '#4c5f6e';
      ctx.beginPath(); ctx.ellipse(p.x, p.y, 15 * k, 4.5 * k, 0, Math.PI, 0); ctx.fill();
      // tail flukes at the end of the dive
      if (ev.age > 4.5) {
        const f = Math.min(1, (ev.age - 4.5) / 1.2);
        ctx.beginPath(); ctx.moveTo(p.x - 15 * k, p.y); ctx.lineTo(p.x - 20 * k, p.y - 9 * k * f); ctx.lineTo(p.x - 14 * k, p.y - 6 * k * f);
        ctx.lineTo(p.x - 8 * k, p.y - 9 * k * f); ctx.closePath(); ctx.fill();
      }
      // spout
      if (ev.age > 0.8 && ev.age < 4) {
        const sp = Math.sin((ev.age - 0.8) / 3.2 * Math.PI);
        ctx.strokeStyle = `rgba(255,255,255,${0.8 * sp})`; ctx.lineWidth = 1.4;
        for (const side of [-1, 0, 1]) {
          ctx.beginPath(); ctx.moveTo(p.x + 4 * k, p.y - 4 * k);
          ctx.quadraticCurveTo(p.x + 4 * k + side * 3 * k, p.y - 22 * k * sp, p.x + 4 * k + side * 9 * k, p.y - 14 * k * sp); ctx.stroke();
        }
        ctx.fillStyle = `rgba(255,255,255,${0.35 * sp})`;
        ctx.beginPath(); ctx.arc(p.x + 4 * k, p.y - 20 * k * sp, 5 * k, 0, 6.283); ctx.fill();
      }
      ctx.restore();
    }

    drawShipAt(ctx, p, k, dir, sail, tilt = 0, alpha = 1) {
      ctx.save(); ctx.globalAlpha = alpha; ctx.translate(p.x, p.y); ctx.rotate(tilt);
      ctx.fillStyle = '#6b4a2a';
      ctx.beginPath(); ctx.moveTo(-10 * k, 0); ctx.lineTo(10 * k, 0); ctx.lineTo(7 * k, 4.5 * k); ctx.lineTo(-7 * k, 4.5 * k); ctx.closePath(); ctx.fill();
      ctx.strokeStyle = '#5a3d22'; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(0, -18 * k); ctx.stroke();
      ctx.fillStyle = '#fbf3e0';
      ctx.beginPath(); ctx.moveTo(0.5, -2 * k); ctx.lineTo(0.5, -17 * k); ctx.lineTo(dir * 10 * k, -4 * k); ctx.closePath(); ctx.fill();
      ctx.fillStyle = sail;
      ctx.beginPath(); ctx.moveTo(0, -18 * k); ctx.lineTo(dir * 6 * k, -16 * k); ctx.lineTo(0, -14 * k); ctx.closePath(); ctx.fill();
      ctx.restore();
    }

    drawBattle(ctx, s, ev, vis) {
      const k = Math.max(0.9, s * 1.4);
      const pa = this.project(ev.a[0], ev.a[1], 0), pb = this.project(ev.b[0], ev.b[1], 0);
      const sinking = Math.max(0, (ev.age - (ev.dur - 4)) / 4);
      const ships = [[pa, 1, ev.colors[0]], [pb, -1, ev.colors[1]]];
      ships.forEach(([p, dir, col], i) => {
        const lost = i === ev.loser ? sinking : 0;
        const bob = Math.sin(this.time * 2 + i) * 0.04;
        this.ripple(ctx, p, 11, 0.35 * vis, k);
        this.drawShipAt(ctx, { x: p.x, y: p.y + lost * 6 * k }, k, dir, col, bob + lost * 0.6 * dir, vis * (1 - lost));
      });
      // cannon fire: alternate broadsides with muzzle flashes, smoke and splashes
      for (let shot = 0; shot < 12; shot++) {
        const t0 = 1 + shot * 0.95;
        const age = ev.age - t0;
        if (age < 0 || age > 2.4 || ev.age > ev.dur - 3.5) continue;
        const from = shot % 2 ? pb : pa, to = shot % 2 ? pa : pb;
        const fx = from.x + (to.x - from.x) * 0.18, fy = from.y - 3 * k;
        if (age < 0.15) {
          ctx.fillStyle = 'rgba(255,190,80,0.9)'; ctx.beginPath(); ctx.arc(fx, fy, 3.5 * k, 0, 6.283); ctx.fill();
        }
        const r = (3 + age * 5) * k;
        ctx.fillStyle = `rgba(245,242,235,${0.7 * (1 - age / 2.4) * vis})`;
        ctx.beginPath(); ctx.arc(fx, fy - age * 5 * k, r, 0, 6.283); ctx.arc(fx + r * 0.6, fy - age * 4 * k, r * 0.7, 0, 6.283); ctx.fill();
        if (age > 0.35 && age < 0.9) {                                  // splash near the target
          const sx = to.x + ((shot * 37) % 13 - 6) * k, sy = to.y + 2 * k, sa = 1 - (age - 0.35) / 0.55;
          ctx.strokeStyle = `rgba(255,255,255,${0.8 * sa})`; ctx.lineWidth = 1.2;
          ctx.beginPath(); ctx.moveTo(sx - 2 * k, sy); ctx.lineTo(sx, sy - 8 * k * sa); ctx.lineTo(sx + 2 * k, sy); ctx.stroke();
        }
      }
    }

    drawBirds(ctx, s) {
      const k = Math.max(0.6, s);
      ctx.strokeStyle = 'rgba(50,40,30,0.7)'; ctx.lineWidth = 1.1;
      for (const f of this.flocks) {
        const fade = clamp((700 - Math.abs(f.x)) / 250, 0, 1);
        if (fade <= 0) continue;
        ctx.globalAlpha = fade;
        for (let i = 0; i < 6; i++) {
          const bx = f.x - (i % 3) * 12 - Math.floor(i / 3) * 6, by = f.y + ((i % 3) - 1) * 9 + Math.floor(i / 3) * 14;
          const p = this.project(bx, by, 60);
          const w = 4 * k, flap = Math.sin(this.time * 6 + i) * 2 * k;
          ctx.beginPath(); ctx.moveTo(p.x - w, p.y - flap); ctx.quadraticCurveTo(p.x - w / 2, p.y - 1.5 * k, p.x, p.y);
          ctx.quadraticCurveTo(p.x + w / 2, p.y - 1.5 * k, p.x + w, p.y - flap); ctx.stroke();
        }
      }
      ctx.globalAlpha = 1;
    }

    drawSparkles(ctx, s) {
      ctx.strokeStyle = 'rgba(255,255,255,0.75)';
      ctx.lineWidth = 1.2;
      for (const w of this.sparkles) {
        const a = 0.5 + 0.5 * Math.sin(this.time * 1.4 + w.phase);
        if (a < 0.55) continue;
        const p = this.project(w.x + Math.sin(this.time * 0.3 + w.phase) * 6, w.y, 0);
        ctx.globalAlpha = (a - 0.55) * 1.8;
        ctx.beginPath();
        ctx.arc(p.x, p.y, 4 * s, Math.PI * 1.1, Math.PI * 1.9);
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
    }

    drawShips(ctx, s) {
      for (const sh of this.ships) {
        const a = this.time * sh.speed + sh.phase;
        const x = sh.cx + Math.cos(a) * sh.rx, y = sh.cy + Math.sin(a) * sh.ry;
        if (this.heightAt(x, y) > -1.5) continue;           // never sail over land
        const p = this.project(x, y, 0), k = Math.max(0.7, s * 1.1);
        const dir = Math.sign(-Math.sin(a) * sh.speed * Math.cos(this.cam.yaw)) || 1;
        ctx.save();
        ctx.translate(p.x, p.y);
        // wake
        ctx.strokeStyle = 'rgba(255,255,255,0.7)'; ctx.lineWidth = 1.2;
        ctx.beginPath(); ctx.moveTo(-dir * 8 * k, 2 * k); ctx.quadraticCurveTo(-dir * 18 * k, 4 * k, -dir * 28 * k, 3 * k); ctx.stroke();
        // hull + sail
        ctx.fillStyle = '#6b4a2a';
        ctx.beginPath(); ctx.moveTo(-9 * k, 0); ctx.lineTo(9 * k, 0); ctx.lineTo(6 * k, 4 * k); ctx.lineTo(-6 * k, 4 * k); ctx.closePath(); ctx.fill();
        ctx.fillStyle = '#fbf3e0'; ctx.strokeStyle = '#6b4a2a'; ctx.lineWidth = 0.8;
        ctx.beginPath(); ctx.moveTo(0, -1); ctx.lineTo(0, -16 * k); ctx.lineTo(dir * 9 * k, -3 * k); ctx.closePath(); ctx.fill(); ctx.stroke();
        ctx.restore();
      }
    }

    drawTrades(ctx, s) {
      const recent = this.trades.filter(t => t.status === 'accepted').slice(-6);
      recent.forEach((t, i) => {
        const a = CAPITALS[t.sender_id], b = CAPITALS[t.receiver_id];
        if (!a || !b || !this.isActive(t.sender_id) || !this.isActive(t.receiver_id)) return;
        const pa = this.project(a[0], a[1], 4), pb = this.project(b[0], b[1], 4);
        const mx = (pa.x + pb.x) / 2, my = (pa.y + pb.y) / 2 - 60 * s;
        ctx.strokeStyle = 'rgba(168,116,18,0.75)'; ctx.lineWidth = 2; ctx.setLineDash([6, 6]);
        ctx.lineDashOffset = -this.time * 20;
        ctx.beginPath(); ctx.moveTo(pa.x, pa.y); ctx.quadraticCurveTo(mx, my, pb.x, pb.y); ctx.stroke();
        ctx.setLineDash([]);
        const u = (this.time * 0.25 + i * 0.37) % 1;
        const qx = (1 - u) * (1 - u) * pa.x + 2 * (1 - u) * u * mx + u * u * pb.x;
        const qy = (1 - u) * (1 - u) * pa.y + 2 * (1 - u) * u * my + u * u * pb.y;
        ctx.fillStyle = '#e2b23c'; ctx.beginPath(); ctx.arc(qx, qy, 4, 0, 6.283); ctx.fill();
      });
    }

    // Soft contact shadow so sprites sit on the land instead of floating above it.
    groundShadow(ctx, x, y, rx, ry, a = 0.18) {
      ctx.fillStyle = `rgba(60, 45, 25, ${a})`;
      ctx.beginPath(); ctx.ellipse(x + rx * 0.25, y + ry * 0.2, rx, ry, 0, 0, 6.283); ctx.fill();
    }

    drawSprite(ctx, sp, p, s) {
      const k = Math.max(0.5, s * 0.95);
      if (sp.type === 'mountain') {
        const w = sp.size * k, h = sp.size * 1.05 * k, peak = p.x + w * sp.lean;
        this.groundShadow(ctx, p.x, p.y, w * 1.15, w * 0.32, 0.16);
        // sunlit west face blends from the terrain colour into pale stone
        const lit = ctx.createLinearGradient(0, p.y - h, 0, p.y);
        lit.addColorStop(0, sp.h > 26 ? '#f3eee2' : '#c9b693');
        lit.addColorStop(0.45, '#b9a27c');
        lit.addColorStop(1, 'rgba(170,150,110,0.55)');
        ctx.fillStyle = lit;
        ctx.beginPath(); ctx.moveTo(p.x - w, p.y); ctx.quadraticCurveTo(peak - w * 0.35, p.y - h * 0.55, peak, p.y - h);
        ctx.lineTo(peak + w * 0.08, p.y); ctx.closePath(); ctx.fill();
        // shadowed east face
        const dark = ctx.createLinearGradient(0, p.y - h, 0, p.y);
        dark.addColorStop(0, sp.h > 26 ? '#cfc8bb' : '#8e7a60');
        dark.addColorStop(1, 'rgba(110,92,70,0.5)');
        ctx.fillStyle = dark;
        ctx.beginPath(); ctx.moveTo(peak, p.y - h); ctx.quadraticCurveTo(peak + w * 0.45, p.y - h * 0.5, p.x + w, p.y);
        ctx.lineTo(peak + w * 0.08, p.y); ctx.closePath(); ctx.fill();
        // a hint of ink on the ridge line only, like an engraved map
        ctx.strokeStyle = 'rgba(90,68,42,0.35)'; ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(p.x - w * 0.55, p.y - h * 0.38); ctx.quadraticCurveTo(peak - w * 0.2, p.y - h * 0.7, peak, p.y - h);
        ctx.quadraticCurveTo(peak + w * 0.3, p.y - h * 0.62, p.x + w * 0.6, p.y - h * 0.3); ctx.stroke();
      } else if (sp.type === 'tree') {
        const r = sp.size * k;
        this.groundShadow(ctx, p.x, p.y, r * 0.9, r * 0.3, 0.14);
        if (sp.kind === 'conifer') {
          const g = sp.tone > 0.5 ? '#5f8160' : '#6a8a63';
          ctx.fillStyle = g;
          ctx.beginPath(); ctx.moveTo(p.x - r * 0.7, p.y - r * 0.2); ctx.quadraticCurveTo(p.x - r * 0.2, p.y - r * 1.4, p.x, p.y - r * 2.3);
          ctx.quadraticCurveTo(p.x + r * 0.2, p.y - r * 1.4, p.x + r * 0.7, p.y - r * 0.2); ctx.closePath(); ctx.fill();
          ctx.fillStyle = 'rgba(40,60,40,0.22)';
          ctx.beginPath(); ctx.moveTo(p.x, p.y - r * 2.3); ctx.quadraticCurveTo(p.x + r * 0.2, p.y - r * 1.4, p.x + r * 0.7, p.y - r * 0.2);
          ctx.lineTo(p.x, p.y - r * 0.2); ctx.closePath(); ctx.fill();
        } else {
          const base = sp.tone > 0.6 ? [124, 160, 98] : sp.tone > 0.3 ? [112, 150, 92] : [134, 166, 102];
          ctx.fillStyle = '#7a6046'; ctx.fillRect(p.x - 0.8, p.y - r * 0.9, 1.6, r * 0.9);
          const blob = (dx, dy, rr, shade) => {
            ctx.fillStyle = `rgba(${base[0] * shade | 0},${base[1] * shade | 0},${base[2] * shade | 0},0.95)`;
            ctx.beginPath(); ctx.arc(p.x + dx * r, p.y + dy * r, rr * r, 0, 6.283); ctx.fill();
          };
          blob(0.25, -1.05, 0.62, 0.82); blob(-0.3, -1.15, 0.6, 0.95); blob(0.05, -1.5, 0.58, 1.05);
        }
      } else if (sp.type === 'city') {
        const r = this.realms[sp.id], active = this.isActive(sp.id);
        const roof = active ? this.shade((r && r.theme_color) || DEFAULT_COLORS[sp.id], 0.78) : '#9c8f7a';
        const rand = rng(sp.seed);
        const n = sp.capital ? 7 : 3, spread = sp.capital ? 12 : 7;
        this.groundShadow(ctx, p.x, p.y, (spread + 6) * k, (spread * 0.4 + 2) * k, 0.16);
        const houses = Array.from({ length: n }, () => [(rand() - 0.5) * 2 * spread, (rand() - 0.5) * spread * 0.7]);
        houses.sort((a, b) => a[1] - b[1]);
        for (const [hx, hy] of houses) {
          const x = p.x + hx * k, y = p.y + hy * k, w = 3.4 * k, h = 3 * k;
          ctx.fillStyle = '#eadfc4'; ctx.fillRect(x - w, y - h, w * 2, h);
          ctx.fillStyle = '#d3c5a4'; ctx.fillRect(x + w * 0.3, y - h, w * 0.7, h);
          ctx.fillStyle = roof;
          ctx.beginPath(); ctx.moveTo(x - w - 0.6, y - h); ctx.lineTo(x, y - h - 3.2 * k); ctx.lineTo(x + w + 0.6, y - h); ctx.closePath(); ctx.fill();
        }
        if (sp.capital) {                                            // the keep of the capital
          ctx.fillStyle = '#d8cab0'; ctx.fillRect(p.x - 2.6 * k, p.y - 15 * k, 5.2 * k, 12 * k);
          ctx.fillStyle = '#c4b597'; ctx.fillRect(p.x + 0.4 * k, p.y - 15 * k, 2.2 * k, 12 * k);
          ctx.fillStyle = roof;
          ctx.beginPath(); ctx.moveTo(p.x - 3.4 * k, p.y - 15 * k); ctx.lineTo(p.x, p.y - 21 * k); ctx.lineTo(p.x + 3.4 * k, p.y - 15 * k); ctx.closePath(); ctx.fill();
        }
        this.mapText(ctx, sp.name, p.x, p.y + (sp.capital ? 10 : 8) * k, {
          size: sp.capital ? 12 : 10.5, italic: true, bold: sp.capital, color: active ? 'rgba(52,36,20,0.92)' : 'rgba(110,98,80,0.75)' });
      } else if (sp.type === 'castle') {
        const w = 6.5 * k, owner = this.realms.aethelgard;
        const pennant = owner && owner.active !== false ? (owner.theme_color || DEFAULT_COLORS.aethelgard) : '#b8ab92';
        this.groundShadow(ctx, p.x, p.y, w * 1.6, w * 0.45, 0.18);
        ctx.fillStyle = '#b3a283';
        ctx.fillRect(p.x - w, p.y - w * 1.5, w * 2, w * 1.5);
        ctx.fillStyle = '#9a8a6c';
        ctx.fillRect(p.x + w * 0.2, p.y - w * 1.5, w * 0.8, w * 1.5);
        ctx.fillStyle = '#c2b292';
        ctx.fillRect(p.x - w * 1.25, p.y - w * 2.3, w * 0.75, w * 2.3); ctx.fillRect(p.x + w * 0.5, p.y - w * 2.3, w * 0.75, w * 2.3);
        ctx.fillStyle = '#8b6f52';
        ctx.beginPath(); ctx.moveTo(p.x - w * 1.35, p.y - w * 2.3); ctx.lineTo(p.x - w * 0.88, p.y - w * 3.1); ctx.lineTo(p.x - w * 0.4, p.y - w * 2.3); ctx.fill();
        ctx.beginPath(); ctx.moveTo(p.x + w * 0.4, p.y - w * 2.3); ctx.lineTo(p.x + w * 0.88, p.y - w * 3.1); ctx.lineTo(p.x + w * 1.35, p.y - w * 2.3); ctx.fill();
        ctx.strokeStyle = '#5d4630'; ctx.lineWidth = 0.8;
        ctx.beginPath(); ctx.moveTo(p.x + w * 0.88, p.y - w * 3.1); ctx.lineTo(p.x + w * 0.88, p.y - w * 3.9); ctx.stroke();
        ctx.fillStyle = pennant;
        ctx.beginPath(); ctx.moveTo(p.x + w * 0.88, p.y - w * 3.9); ctx.lineTo(p.x + w * 1.7, p.y - w * 3.65 + Math.sin(this.time * 3) * 1.2); ctx.lineTo(p.x + w * 0.88, p.y - w * 3.4); ctx.fill();
      } else if (sp.type === 'temple') {
        const w = 7 * k;
        this.groundShadow(ctx, p.x, p.y, w * 1.4, w * 0.4, 0.16);
        ctx.fillStyle = '#f4ead0'; ctx.fillRect(p.x - w, p.y - w * 0.35, w * 2, w * 0.35);
        ctx.fillStyle = '#efe2c2';
        for (let i = -2; i <= 2; i++) ctx.fillRect(p.x + i * w * 0.42 - 0.9 * k, p.y - w * 1.25, 1.8 * k, w * 0.95);
        ctx.fillStyle = '#d9a93c';
        ctx.beginPath(); ctx.moveTo(p.x - w * 1.1, p.y - w * 1.25); ctx.lineTo(p.x, p.y - w * 1.8); ctx.lineTo(p.x + w * 1.1, p.y - w * 1.25); ctx.closePath(); ctx.fill();
      } else if (sp.type === 'spire') {
        const pulse = 0.5 + 0.5 * Math.sin(this.time * 1.2);
        const top = p.y - 44 * k;
        const glow = ctx.createRadialGradient(p.x, top, 1, p.x, top, (28 + pulse * 12) * k);
        glow.addColorStop(0, 'rgba(255,233,170,0.85)'); glow.addColorStop(1, 'rgba(255,233,170,0)');
        ctx.fillStyle = glow; ctx.beginPath(); ctx.arc(p.x, top, (28 + pulse * 12) * k, 0, 6.283); ctx.fill();
        this.groundShadow(ctx, p.x, p.y, 12 * k, 3.5 * k, 0.25);
        const body = ctx.createLinearGradient(p.x - 8 * k, 0, p.x + 8 * k, 0);
        body.addColorStop(0, '#5a5262'); body.addColorStop(0.5, '#3a3442'); body.addColorStop(1, '#25212b');
        ctx.fillStyle = body;
        ctx.beginPath(); ctx.moveTo(p.x - 8 * k, p.y); ctx.quadraticCurveTo(p.x - 4 * k, p.y - 26 * k, p.x - 2 * k, p.y - 44 * k);
        ctx.lineTo(p.x, p.y - 54 * k); ctx.lineTo(p.x + 2 * k, p.y - 44 * k);
        ctx.quadraticCurveTo(p.x + 4 * k, p.y - 26 * k, p.x + 8 * k, p.y); ctx.closePath(); ctx.fill();
        ctx.fillStyle = '#ffe9a8'; ctx.beginPath(); ctx.arc(p.x, top, 2.2 * k, 0, 6.283); ctx.fill();
        this.mapText(ctx, 'The Neutral Spire', p.x, p.y + 12 * k, { size: 12, italic: true, color: 'rgba(59,42,26,0.85)', spacing: 1 });
      }
    }

    // Cartographer-style ribbon: parchment scroll with folded tails in the nation's colour,
    // a heraldic shield above it and a wax seal carrying the nation's Assembly votes.
    drawBanner(ctx, id, p, s) {
      const r = this.realms[id];
      if (!this.isActive(id)) {
        this.mapText(ctx, REGION_NAMES[id].toUpperCase(), p.x, p.y - 4, { size: 13, color: 'rgba(110,98,80,0.9)', spacing: 3 });
        this.mapText(ctx, 'unclaimed lands', p.x, p.y + 12, { size: 12, italic: true, color: 'rgba(120,108,90,0.85)' });
        return;
      }
      const focused = this.focus === id;
      const sc = (focused ? 1.12 : 0.9) * this.ui;
      const color = r.theme_color || DEFAULT_COLORS[id];
      const deep = this.shade(color, 0.72);
      const name = r.name.toUpperCase();
      ctx.save();
      ctx.font = `600 ${Math.round(13 * sc)}px "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif`;
      if ('letterSpacing' in ctx) ctx.letterSpacing = `${(2 * sc).toFixed(1)}px`;
      const tw = ctx.measureText(name).width;
      const bw = tw + 26 * sc, bh = 21 * sc;
      const keepTop = 22 * Math.max(0.5, s * 0.95);                  // top of the capital's keep
      const lift = keepTop + 22 * sc + (focused ? 3 * Math.sin(this.time * 1.6) : 0);
      const cx = p.x, cy = p.y - lift;
      const x0 = cx - bw / 2, x1 = cx + bw / 2, y0 = cy - bh / 2, y1 = cy + bh / 2, bow = 4 * sc;

      // fine leader line from the ribbon down to the capital's keep
      ctx.strokeStyle = 'rgba(70,50,28,0.5)'; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(p.x, p.y - keepTop); ctx.lineTo(cx, y1 + bow); ctx.stroke();

      // folded tails (behind the ribbon), in the nation's colour
      const tail = (dir) => {
        const xe = dir < 0 ? x0 : x1, xo = xe + dir * 16 * sc;
        ctx.fillStyle = deep;
        ctx.beginPath();
        ctx.moveTo(xe - dir * 6 * sc, y0 + 6 * sc); ctx.lineTo(xo, y0 + 6 * sc);
        ctx.lineTo(xo - dir * 6 * sc, cy + 5 * sc); ctx.lineTo(xo, y1 + 6 * sc); ctx.lineTo(xe - dir * 6 * sc, y1 + 6 * sc);
        ctx.closePath(); ctx.fill();
      };
      tail(-1); tail(1);

      // ribbon body with a gentle bow
      const paper = ctx.createLinearGradient(0, y0, 0, y1);
      paper.addColorStop(0, '#fdf6e4'); paper.addColorStop(1, '#ecdcb7');
      ctx.shadowColor = 'rgba(60,40,15,0.3)'; ctx.shadowBlur = focused ? 12 : 5; ctx.shadowOffsetY = 2;
      ctx.fillStyle = paper;
      ctx.beginPath();
      ctx.moveTo(x0, y0); ctx.quadraticCurveTo(cx, y0 - bow, x1, y0);
      ctx.lineTo(x1, y1); ctx.quadraticCurveTo(cx, y1 - bow, x0, y1); ctx.closePath(); ctx.fill();
      ctx.shadowColor = 'transparent';
      ctx.strokeStyle = deep; ctx.lineWidth = focused ? 1.8 : 1.2; ctx.stroke();

      // lettering
      ctx.fillStyle = '#3a2a18'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(name, cx, cy - bow * 0.35 + 1);
      if ('letterSpacing' in ctx) ctx.letterSpacing = '0px';

      // heraldic shield above the ribbon, bearing the nation's initial
      const sw = 11 * sc, sh = 13 * sc, sy = y0 - bow - sh - 2 * sc;
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.moveTo(cx - sw, sy); ctx.lineTo(cx + sw, sy); ctx.lineTo(cx + sw, sy + sh * 0.55);
      ctx.quadraticCurveTo(cx + sw, sy + sh * 1.15, cx, sy + sh * 1.5);
      ctx.quadraticCurveTo(cx - sw, sy + sh * 1.15, cx - sw, sy + sh * 0.55); ctx.closePath(); ctx.fill();
      ctx.strokeStyle = '#c9a23f'; ctx.lineWidth = 2 * sc; ctx.stroke();
      ctx.fillStyle = '#fffaf0';
      ctx.font = `700 ${Math.round(12 * sc)}px "Palatino Linotype", Palatino, Georgia, serif`;
      ctx.fillText(this.initial(r.name), cx, sy + sh * 0.62);

      // wax seal with the vote count on the right tail
      const wx = x1 + 12 * sc, wy = y1 - 2 * sc, wr = 10 * sc;
      ctx.fillStyle = '#9e2c25';
      ctx.beginPath();
      for (let i = 0; i <= 12; i++) {
        const a = i / 12 * 6.283, rr = wr * (i % 2 ? 0.88 : 1);
        ctx[i ? 'lineTo' : 'moveTo'](wx + Math.cos(a) * rr, wy + Math.sin(a) * rr);
      }
      ctx.closePath(); ctx.fill();
      ctx.fillStyle = '#c4473f'; ctx.beginPath(); ctx.arc(wx - wr * 0.15, wy - wr * 0.15, wr * 0.55, 0, 6.283); ctx.fill();
      ctx.fillStyle = '#fff3e0';
      ctx.font = `700 ${Math.round(11 * sc)}px "Palatino Linotype", Palatino, Georgia, serif`;
      ctx.fillText(String(r.assembly_votes), wx, wy + 0.5);

      this.hits.push({ id, x0: x0 - 18 * sc, x1: x1 + 24 * sc, y0: y0 - 34 * sc, y1: y1 + 8 * sc });
      // warnings, written beneath like a map annotation
      const flags = [];
      if (r.is_starving) flags.push('famine');
      if (r.is_plutocrat) flags.push('richest realm');
      if (r.is_quarantined) flags.push('borders sealed');
      ctx.restore();
      if (flags.length) this.mapText(ctx, flags.join(' · '), p.x, p.y + 26 * (this.ui || 1), { size: 12, italic: true, color: '#8a2c25' });
    }

    drawClouds(ctx, s) {
      const motion = this.reduceMotion ? 0.2 : 1;
      for (const cl of this.clouds) {
        cl.x += 0.035 * motion;
        if (cl.x > 900) cl.x = -900;
        // fade in/out far from the continent so clouds never pop on or off screen
        const fade = clamp((900 - Math.abs(cl.x)) / 380, 0, 1);
        const eased = fade * fade * (3 - 2 * fade);
        if (eased <= 0.01) continue;
        const p = this.project(cl.x, cl.y, 0);
        const shadow = this.project(cl.x + 30, cl.y + 40, 0);
        const r = 50 * cl.s * s;
        if (this.q.cloudShadows) {
          ctx.fillStyle = `rgba(60,50,30,${0.07 * eased})`;
          this.puff(ctx, shadow.x, shadow.y, r);
        }
        ctx.fillStyle = `rgba(255,255,255,${0.55 * eased})`;
        this.puff(ctx, p.x, p.y - 120 * s, r);
      }
    }

    puff(ctx, x, y, r) {
      // Separate sub-paths (moveTo before each ellipse) so no stray connecting lines appear.
      ctx.beginPath();
      for (const [ox, oy, rx, ry] of [[0, 0, 1, 0.42], [-0.55, 0.08, 0.6, 0.3], [0.6, 0.1, 0.55, 0.28]]) {
        ctx.moveTo(x + ox * r + rx * r, y + oy * r);
        ctx.ellipse(x + ox * r, y + oy * r, rx * r, ry * r, 0, 0, 6.283);
      }
      ctx.fill();
    }

    // Map lettering: serif with a soft parchment halo, optional letter-spacing.
    mapText(ctx, text, x, y, { size = 14, italic = false, bold = false, color = '#2b2016', spacing = 0 } = {}) {
      ctx.save();
      size = Math.round(size * (this.ui || 1));
      ctx.font = `${italic ? 'italic ' : ''}${bold ? '700 ' : ''}${size}px "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif`;
      if ('letterSpacing' in ctx) ctx.letterSpacing = `${spacing}px`;
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.lineWidth = 3.5; ctx.strokeStyle = 'rgba(250,244,228,0.75)'; ctx.lineJoin = 'round';
      ctx.strokeText(text, x, y);
      ctx.fillStyle = color; ctx.fillText(text, x, y);
      ctx.restore();
    }

    initial(name) {
      const words = String(name).split(/\s+/).filter(w => !/^(the|of|iron)$/i.test(w));
      return (words[0] || name || '?')[0].toUpperCase();
    }

    shade(hex, f) {
      const [r, g, b] = hexRgb(hex);
      return `rgb(${Math.round(r * f)},${Math.round(g * f)},${Math.round(b * f)})`;
    }

  }

  LivingAtlas.QUALITY = QUALITY;
  LivingAtlas.info = {
    regions: REGION_NAMES,
    capitals: Object.fromEntries(SETTLEMENTS.filter(s => s[4]).map(s => [s[0], s[1]])),
  };
  window.LivingAtlas = LivingAtlas;
})();
