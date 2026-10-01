/**
 * The Summit of Realms — Topographical Island Map Engine (v11)
 *
 * Changes from v10:
 *   • Continent is now a clearly-defined ISLAND surrounded by water.
 *   • Removed blueprint grid — pure topological map with contour lines.
 *   • Each country is filled with its own colour from scenario_config.
 *   • Spotlight country card is a LARGE sidebar panel (wall-projection sized).
 *   • Light & dark mode support — reads body.classList for 'theme-light'.
 *   • Compact badges on-map for non-spotlight countries.
 */

class World3DMap {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');

    this.dpr = Math.min(window.devicePixelRatio || 1, 2);
    this.width  = this.canvas.clientWidth  || 1200;
    this.height = this.canvas.clientHeight || 750;

    // ── Camera ──────────────────────────────────────────────
    this.camera = {
      yaw: 0.5, pitch: 0.85, distance: 600,
      tYaw: 0.5, tPitch: 0.85, tDist: 600,
      autoOrbit: true, speed: 0.0014,
      dragging: false, last: { x: 0, y: 0 }
    };

    // ── Tour ────────────────────────────────────────────────
    this.tour = ['aethelgard','val_khor','solaria','umbra','aquila','sylvan'];
    this.spotIdx = 0;
    this.selectedRealmId = 'aethelgard';
    this.tourClock = 0;
    this.tourInterval = 8;
    this.userTime = 0;

    // ── State ───────────────────────────────────────────────
    this.realms = [];
    this.trades = [];
    this.meta   = null;

    // ── Animation ───────────────────────────────────────────
    this.t = 0;
    this.pulse = 0;
    this.hits = [];

    // ── Terrain grid (wide enough for ocean rim around island) ─
    this.GC = 72;
    this.GR = 54;
    this.CS = 14;

    // ── Country theme colours (from scenario_config) ────────
    this._colors = {
      aethelgard: '#ec4899',
      val_khor:   '#f59e0b',
      solaria:    '#eab308',
      umbra:      '#8b5cf6',
      aquila:     '#06b6d4',
      sylvan:     '#10b981'
    };

    // ── Build ───────────────────────────────────────────────
    this._buildTerrain();
    this._initEvents();
    this._resize();

    this.alive = true;
    this._frame = this._frame.bind(this);
    requestAnimationFrame(this._frame);
  }

  /* ================================================================
   *  THEME
   * ================================================================ */

  get isDark() {
    try { return !document.body.classList.contains('theme-light'); }
    catch(e) { return true; }
  }
  get bg()      { return this.isDark ? '#060911' : '#f0efe8'; }
  get water()   { return this.isDark ? '#0a0f1e' : '#c8dbe8'; }
  get contour() { return this.isDark ? 'rgba(255,255,255,' : 'rgba(40,40,40,'; }
  get textCol() { return this.isDark ? '#ffffff' : '#1e293b'; }
  get cardBg()  { return this.isDark ? '#0c1525' : '#ffffff'; }
  get cardBdr() { return this.isDark ? 'rgba(255,255,255,0.22)' : 'rgba(0,0,0,0.12)'; }
  get mutedTxt(){ return this.isDark ? 'rgba(200,210,225,0.7)' : 'rgba(80,80,80,0.7)'; }

  /* ================================================================
   *  TERRAIN GENERATION
   * ================================================================ */

  _buildTerrain() {
    this._caps = {
      aethelgard: [75, -175],
      val_khor:   [255, 10],
      solaria:    [125, 150],
      umbra:      [-135, 95],
      aquila:     [-285, -80],
      sylvan:     [-125, -45]
    };

    // Gaussian blobs: [cx, cy, rx, ry, height]
    // The island body is smaller than v10 — clearly surrounded by ocean.
    this._blobs = [
      // ── Main island body (reduced radius → water all around) ──
      [15, 12, 210, 135, 18],

      // ── AETHELGARD — northern peninsula ──
      [55, -150, 80, 105, 22],
      [82, -220, 42, 62, 16],
      [65, -175, 22, 60, 28],

      // ── VAL-KHOR — eastern volcanic range ──
      [225, -5, 100, 85, 24],
      [215, -25, 26, 50, 42],
      [255, 18, 22, 38, 48],
      [275, 60, 18, 30, 38],

      // ── SOLARIA — southern coast ──
      [85, 140, 135, 55, 12],
      [175, 158, 58, 38, 10],

      // ── UMBRA — southwest ──
      [-145, 80, 95, 70, 16],
      [-105, 128, 55, 45, 11],

      // ── SYLVAN — western forests ──
      [-115, -40, 100, 85, 14],
      [-145, -68, 34, 40, 21],

      // ── AQUILA — archipelago (6 islands) ──
      [-275, -78, 38, 32, 11],
      [-312, -45, 28, 24, 9],
      [-255, -118, 24, 28, 9],
      [-298, -108, 19, 19, 7],
      [-335, -78, 15, 19, 6],
      [-265, -48, 30, 25, 10],

      // ── GEOGRAPHIC FEATURES ──
      [5, -12, 48, 38, -38],        // Lake Seraph
      [30, -185, 12, 46, -35],      // fjord 1
      [95, -192, 10, 42, -32],      // fjord 2
      [-40, 32, 12, 68, -26],       // river valley
      [-118, 112, 11, 46, -24],     // Umbra canyon
      [-210, -30, 32, 88, -30],     // Aquila channel
      [-232, -65, 26, 55, -24],     // secondary channel
    ];

    // ── Build heightmap + country assignment ──
    this.hmap = [];
    this.cmap = [];
    for (let r = 0; r < this.GR; r++) {
      this.hmap[r] = [];
      this.cmap[r] = [];
      for (let c = 0; c < this.GC; c++) {
        const wx = (c - this.GC / 2) * this.CS;
        const wy = (r - this.GR / 2) * this.CS;
        const h  = this._elev(wx, wy);
        this.hmap[r][c] = h;
        this.cmap[r][c] = h > 0 ? this._owner(wx, wy) : null;
      }
    }

    // ── Realm metadata ──
    this.realmsData = {};
    const names = {
      aethelgard: ['Aethelgard Dominion',   'Valenhold Citadel'],
      val_khor:   ['Iron Val-Khor',         'Mount Khor Foundry'],
      solaria:    ['Solaris Ascendancy',     'Solaris Sun Terraces'],
      umbra:      ['Umbral Enclave',         'Abyssal Catacombs'],
      aquila:     ['Aquila Maritime League', 'Glass Harbor Sea-Gate'],
      sylvan:     ['Sylvan Concordat',       'Sylva Arbor Canopy'],
    };
    for (const id of this.tour) {
      const [wx, wy] = this._caps[id];
      const wz = Math.max(this._elev(wx, wy), 3);
      this.realmsData[id] = {
        id, name: names[id][0], themeColor: this._colors[id],
        capital: { name: names[id][1], pos: [wx, wy, wz] },
        center: [wx, wy, wz]
      };
    }

    // ── Peaks ──
    this.peaks = [];
    for (let r = 2; r < this.GR - 2; r++) {
      for (let c = 2; c < this.GC - 2; c++) {
        const h = this.hmap[r][c];
        if (h < 26) continue;
        let max = true;
        for (let dr = -2; dr <= 2 && max; dr++)
          for (let dc = -2; dc <= 2 && max; dc++)
            if ((dr || dc) && this.hmap[r+dr][c+dc] >= h) max = false;
        if (max) this.peaks.push({
          wx: (c - this.GC/2) * this.CS,
          wy: (r - this.GR/2) * this.CS, wz: h,
          label: `▲ ${Math.round(h * 48)}m`
        });
      }
    }

    this._buildContours();
    this._buildBorders();
  }

  _elev(wx, wy) {
    let h = 0;
    for (const b of this._blobs) {
      const dx = (wx - b[0]) / b[2], dy = (wy - b[1]) / b[3];
      const d2 = dx*dx + dy*dy;
      if (d2 < 6) h += b[4] * Math.exp(-d2);
    }
    h += 2.5 * Math.sin(wx*0.031+0.7) * Math.cos(wy*0.037+1.1);
    h += 1.8 * Math.sin(wx*0.067+2.3) * Math.cos(wy*0.053+0.5);
    h += 1.2 * Math.sin(wx*0.11+3.7)  * Math.cos(wy*0.09+2.1);
    // Ocean falloff — force water beyond island boundary
    // Asymmetric: wider west (for Aquila islands) and north (for Aethelgard peninsula)
    const rx = wx < 15 ? 400 : 340;
    const ry = wy < 0 ? 310 : 260;
    const ex = (wx - 15) / rx, ey = wy / ry;
    const r2 = ex*ex + ey*ey;
    if (r2 > 0.64) h -= 35 * Math.max(0, (r2 - 0.64) / 0.36);
    return h;
  }

  _owner(wx, wy) {
    if (wx < -228) return 'aquila';
    let best = null, bd = Infinity;
    for (const id in this._caps) {
      if (id === 'aquila') continue;
      const d = Math.hypot(wx - this._caps[id][0], wy - this._caps[id][1]);
      if (d < bd) { bd = d; best = id; }
    }
    return best;
  }

  /* ── Marching-squares contours ────────────────────────────── */

  _buildContours() {
    this._CL = [
      [],[[3,2]],[[2,1]],[[3,1]],[[0,1]],[[3,0],[2,1]],[[0,2]],[[0,3]],
      [[0,3]],[[0,2]],[[0,1],[3,2]],[[0,1]],[[3,1]],[[2,1]],[[3,2]],[]
    ];
    const levels = [
      { z: 0,  w: 2.2, a: 0.85 },
      { z: 4,  w: 0.5, a: 0.18 },
      { z: 8,  w: 0.6, a: 0.22 },
      { z: 13, w: 0.7, a: 0.30 },
      { z: 20, w: 0.9, a: 0.42 },
      { z: 32, w: 1.0, a: 0.48 },
      { z: 44, w: 0.8, a: 0.38 },
    ];
    this.contours = [];
    for (const lv of levels) {
      const segs = [];
      for (let r = 0; r < this.GR - 1; r++) {
        for (let c = 0; c < this.GC - 1; c++) {
          const tl=this.hmap[r][c], tr=this.hmap[r][c+1];
          const bl=this.hmap[r+1][c], br=this.hmap[r+1][c+1];
          const cfg=(tl>lv.z?8:0)|(tr>lv.z?4:0)|(br>lv.z?2:0)|(bl>lv.z?1:0);
          if (!cfg || cfg===15) continue;
          for (const [e1,e2] of this._CL[cfg]) {
            const p1=this._cEdge(e1,r,c,tl,tr,br,bl,lv.z);
            const p2=this._cEdge(e2,r,c,tl,tr,br,bl,lv.z);
            segs.push(p1[0],p1[1],p2[0],p2[1]);
          }
        }
      }
      this.contours.push({ z:lv.z, w:lv.w, a:lv.a, segs });
    }
  }

  _cEdge(edge,row,col,tl,tr,br,bl,z) {
    const s=this.CS, ox=-(this.GC/2)*s, oy=-(this.GR/2)*s;
    const x0=ox+col*s, y0=oy+row*s;
    let h1,h2,ax,ay,bx,by;
    switch(edge) {
      case 0: h1=tl;h2=tr;ax=x0;ay=y0;bx=x0+s;by=y0;break;
      case 1: h1=tr;h2=br;ax=x0+s;ay=y0;bx=x0+s;by=y0+s;break;
      case 2: h1=bl;h2=br;ax=x0;ay=y0+s;bx=x0+s;by=y0+s;break;
      case 3: h1=tl;h2=bl;ax=x0;ay=y0;bx=x0;by=y0+s;break;
    }
    const t=(z-h1)/(h2-h1||1);
    return [ax+t*(bx-ax), ay+t*(by-ay)];
  }

  /* ── Borders ──────────────────────────────────────────────── */

  _buildBorders() {
    this.borders = [];
    const s=this.CS, ox=-(this.GC/2)*s, oy=-(this.GR/2)*s;
    for (let r=0; r<this.GR; r++) {
      for (let c=0; c<this.GC; c++) {
        const me = this.cmap[r][c]; if (!me) continue;
        if (c<this.GC-1) { const rt=this.cmap[r][c+1]; if(rt&&rt!==me) {
          const h=(this.hmap[r][c]+this.hmap[r][c+1])/2;
          this.borders.push(ox+(c+1)*s, oy+r*s, h, ox+(c+1)*s, oy+(r+1)*s, h);
        }}
        if (r<this.GR-1) { const bt=this.cmap[r+1][c]; if(bt&&bt!==me) {
          const h=(this.hmap[r][c]+this.hmap[r+1][c])/2;
          this.borders.push(ox+c*s, oy+(r+1)*s, h, ox+(c+1)*s, oy+(r+1)*s, h);
        }}
      }
    }
  }

  /* ================================================================
   *  3D PROJECTION
   * ================================================================ */

  project(x, y, z) {
    const { yaw, pitch, distance: D } = this.camera;
    const cp=Math.cos(pitch), sp=Math.sin(pitch);
    const cy=Math.cos(yaw), sy=Math.sin(yaw);
    const cx=D*cp*sy, cY=-D*cp*cy, cz=D*sp;
    const fx=-cp*sy, fy=cp*cy, fz=-sp;
    const rx=cy, ry=sy, rz=0;
    const ux=-sp*sy, uy=sp*cy, uz=cp;
    const vx=x-cx, vy=y-cY, vz=z-cz;
    const zC=vx*fx+vy*fy+vz*fz;
    if (zC<=1) return null;
    const xC=vx*rx+vy*ry+vz*rz;
    const yC=vx*ux+vy*uy+vz*uz;
    const F=650;
    return { x:this.width/2+(xC*F)/zC, y:this.height/2-(yC*F)/zC, depth:zC };
  }

  /* ================================================================
   *  EVENTS
   * ================================================================ */

  _initEvents() {
    window.addEventListener('resize', () => this._resize());
    this.canvas.addEventListener('mousedown', e => {
      this.camera.dragging=true;
      this.camera.last={x:e.clientX,y:e.clientY};
      this.userTime=Date.now();
    });
    window.addEventListener('mousemove', e => {
      if (!this.camera.dragging) return;
      this.camera.tYaw  -= (e.clientX-this.camera.last.x)*0.005;
      this.camera.tPitch = Math.max(0.68, Math.min(1.08,
        this.camera.tPitch+(e.clientY-this.camera.last.y)*0.004));
      this.camera.last={x:e.clientX,y:e.clientY};
      this.userTime=Date.now();
    });
    window.addEventListener('mouseup', () => { this.camera.dragging=false; });
    this.canvas.addEventListener('wheel', e => {
      e.preventDefault();
      this.camera.tDist = Math.max(420, Math.min(780,
        this.camera.tDist*(e.deltaY<0?0.93:1.07)));
      this.userTime=Date.now();
    }, { passive:false });
    this.canvas.addEventListener('click', e => {
      const r=this.canvas.getBoundingClientRect();
      this._click(e.clientX-r.left, e.clientY-r.top);
    });
  }

  _resize() {
    this.width  = this.canvas.clientWidth  || 1200;
    this.height = this.canvas.clientHeight || 750;
    this.canvas.width  = Math.floor(this.width  * this.dpr);
    this.canvas.height = Math.floor(this.height * this.dpr);
    this.ctx.setTransform(this.dpr,0,0,this.dpr,0,0);
  }

  _click(mx,my) {
    for (const h of this.hits) {
      if (mx>=h.x && mx<=h.x+h.w && my>=h.y && my<=h.y+h.h) {
        this._sel(h.id); return;
      }
    }
    for (const id of this.tour) {
      const p = this.project(...this.realmsData[id].capital.pos);
      if (p && Math.hypot(mx-p.x,my-p.y)<40) { this._sel(id); return; }
    }
  }

  _sel(id) {
    const i=this.tour.indexOf(id); if(i<0) return;
    this.spotIdx=i; this.selectedRealmId=id;
    this.tourClock=0; this.userTime=Date.now(); this._pills();
  }

  /* ================================================================
   *  STATE MANAGEMENT
   * ================================================================ */

  updateState(s) {
    if (!s) return;
    this.realms=s.realms||[]; this.trades=s.trades||[]; this.meta=s.meta||null;
    this._pills();
  }
  _pills() {
    for (const id of this.tour) {
      const el=document.getElementById('pill-'+id);
      if(el) el.classList.toggle('active', id===this.selectedRealmId);
    }
  }
  resetCamera() { this.camera.tYaw=0.5; this.camera.tPitch=0.85; this.camera.tDist=600;
    this.spotIdx=0; this.selectedRealmId=this.tour[0]; this._pills(); }
  toggleDrift() { this.camera.autoOrbit=!this.camera.autoOrbit; return this.camera.autoOrbit; }
  toggleSpeed() { return '1x'; }
  destroy() { this.alive=false; }

  _tier(v) {
    const t=String(v||'').toLowerCase();
    if (/low|deplet|scarce|neglig|defens/.test(t)) return 1;
    if (/high|abund|surpl|lavish|formid|overwh/.test(t)) return 3;
    return 2;
  }

  /* ================================================================
   *  RENDER LOOP
   * ================================================================ */

  _frame(ts) {
    if (!this.alive) return;
    this.t = (ts||0)*0.001;
    this.pulse = (this.t*1.6)%(Math.PI*2);

    const idle = Date.now()-this.userTime > 6000;
    if (this.camera.autoOrbit && idle) {
      this.camera.tYaw += this.camera.speed;
      this.camera.tPitch = 0.85 + 0.05*Math.sin(this.t*0.22);
      this.camera.tDist  = 600  + 15 *Math.cos(this.t*0.18);
      this.tourClock += 0.016;
      if (this.tourClock >= this.tourInterval) {
        this.tourClock=0;
        this.spotIdx=(this.spotIdx+1)%this.tour.length;
        this.selectedRealmId=this.tour[this.spotIdx]; this._pills();
      }
    }

    const cam=this.camera;
    cam.yaw      += (cam.tYaw  -cam.yaw)     *0.08;
    cam.pitch    += (cam.tPitch-cam.pitch)   *0.08;
    cam.distance += (cam.tDist -cam.distance)*0.08;
    cam.pitch = Math.max(0.68, Math.min(1.08, cam.pitch));

    const ctx=this.ctx;
    this.hits=[];

    // background
    ctx.fillStyle = this.bg;
    ctx.fillRect(0,0,this.width,this.height);

    this._drawWater();
    this._drawLand();
    this._drawContours();
    this._drawBorders();
    this._drawPeaks();
    this._drawSpire();
    this._drawCapitals();
    this._drawTrades();
    this._drawMiniBadges();
    this._drawSidebar();

    requestAnimationFrame(this._frame);
  }

  /* ================================================================
   *  DRAWING
   * ================================================================ */

  /* ── Water fill (subtle ocean) ──────────────────────────────── */
  _drawWater() {
    const ctx=this.ctx, s=this.CS;
    const ox=-(this.GC/2)*s, oy=-(this.GR/2)*s;
    ctx.fillStyle = this.water;
    // Draw water cells
    ctx.beginPath();
    for (let r=0; r<this.GR-1; r++) {
      for (let c=0; c<this.GC-1; c++) {
        if (this.hmap[r][c]>0 && this.hmap[r][c+1]>0 &&
            this.hmap[r+1][c]>0 && this.hmap[r+1][c+1]>0) continue;
        const a=this.project(ox+c*s,oy+r*s,0);
        const b=this.project(ox+(c+1)*s,oy+r*s,0);
        const d=this.project(ox+(c+1)*s,oy+(r+1)*s,0);
        const e=this.project(ox+c*s,oy+(r+1)*s,0);
        if (a&&b&&d&&e) {
          ctx.moveTo(a.x,a.y); ctx.lineTo(b.x,b.y);
          ctx.lineTo(d.x,d.y); ctx.lineTo(e.x,e.y); ctx.closePath();
        }
      }
    }
    ctx.fill();
  }

  /* ── Country-coloured land fills ────────────────────────────── */
  _drawLand() {
    const ctx=this.ctx, s=this.CS;
    const ox=-(this.GC/2)*s, oy=-(this.GR/2)*s;
    const dark = this.isDark;
    // Batch per country
    for (const id of this.tour) {
      const col = this._colors[id];
      // Parse hex to rgba
      const r2=parseInt(col.slice(1,3),16), g2=parseInt(col.slice(3,5),16), b2=parseInt(col.slice(5,7),16);
      ctx.fillStyle = dark
        ? `rgba(${r2},${g2},${b2},0.25)`
        : `rgba(${r2},${g2},${b2},0.30)`;
      ctx.beginPath();
      for (let r=0; r<this.GR-1; r++) {
        for (let c=0; c<this.GC-1; c++) {
          // Cell belongs to this country if majority of vertices do
          const owners = [this.cmap[r][c],this.cmap[r][c+1],
                          this.cmap[r+1][c],this.cmap[r+1][c+1]];
          const cnt = owners.filter(o=>o===id).length;
          if (cnt < 2) continue;

          const h00=Math.max(this.hmap[r][c],0), h10=Math.max(this.hmap[r][c+1],0);
          const h01=Math.max(this.hmap[r+1][c],0), h11=Math.max(this.hmap[r+1][c+1],0);
          const a=this.project(ox+c*s,oy+r*s,h00);
          const b=this.project(ox+(c+1)*s,oy+r*s,h10);
          const d=this.project(ox+(c+1)*s,oy+(r+1)*s,h11);
          const e=this.project(ox+c*s,oy+(r+1)*s,h01);
          if (a&&b&&d&&e) {
            ctx.moveTo(a.x,a.y); ctx.lineTo(b.x,b.y);
            ctx.lineTo(d.x,d.y); ctx.lineTo(e.x,e.y); ctx.closePath();
          }
        }
      }
      ctx.fill();
    }
  }

  /* ── Contour lines ──────────────────────────────────────────── */
  _drawContours() {
    const ctx=this.ctx, pre=this.contour;
    for (const cl of this.contours) {
      ctx.strokeStyle = pre + cl.a + ')';
      ctx.lineWidth = cl.w;
      ctx.beginPath();
      const sg=cl.segs;
      for (let i=0; i<sg.length; i+=4) {
        const p1=this.project(sg[i],sg[i+1],cl.z);
        const p2=this.project(sg[i+2],sg[i+3],cl.z);
        if (p1&&p2) { ctx.moveTo(p1.x,p1.y); ctx.lineTo(p2.x,p2.y); }
      }
      ctx.stroke();
    }
  }

  /* ── Country borders ────────────────────────────────────────── */
  _drawBorders() {
    const ctx=this.ctx, bd=this.borders;
    ctx.strokeStyle = this.isDark ? 'rgba(255,255,255,0.45)' : 'rgba(0,0,0,0.25)';
    ctx.lineWidth = 1.4;
    ctx.setLineDash([5,4]);
    ctx.beginPath();
    for (let i=0; i<bd.length; i+=6) {
      const a=this.project(bd[i],bd[i+1],bd[i+2]);
      const b=this.project(bd[i+3],bd[i+4],bd[i+5]);
      if (a&&b) { ctx.moveTo(a.x,a.y); ctx.lineTo(b.x,b.y); }
    }
    ctx.stroke();
    ctx.setLineDash([]);
  }

  /* ── Peaks ──────────────────────────────────────────────────── */
  _drawPeaks() {
    const ctx=this.ctx;
    for (const pk of this.peaks) {
      const p=this.project(pk.wx,pk.wy,pk.wz); if(!p) continue;
      ctx.fillStyle = this.textCol;
      ctx.beginPath(); ctx.arc(p.x,p.y,2.5,0,6.28); ctx.fill();
      ctx.font = 'bold 7.5px monospace'; ctx.textAlign='left';
      ctx.fillStyle = this.mutedTxt;
      ctx.fillText(pk.label, p.x+5, p.y+3);
    }
  }

  /* ── Neutral Spire ──────────────────────────────────────────── */
  _drawSpire() {
    const ctx=this.ctx;
    const base=this.project(0,-10,0), tip=this.project(0,-10,65);
    if (!base||!tip) return;
    for (let i=1; i<=3; i++) {
      const rr=i*11+(this.t*13)%22;
      const al=Math.max(0,0.35-rr/50);
      ctx.beginPath(); ctx.arc(base.x,base.y,rr,0,6.28);
      ctx.strokeStyle = this.contour+al+')'; ctx.lineWidth=0.8; ctx.stroke();
    }
    ctx.beginPath(); ctx.moveTo(base.x,base.y); ctx.lineTo(tip.x,tip.y);
    ctx.strokeStyle=this.textCol; ctx.lineWidth=2; ctx.stroke();
    ctx.beginPath(); ctx.arc(tip.x,tip.y,3.5,0,6.28);
    ctx.fillStyle=this.textCol; ctx.fill();
    ctx.font='bold 8px monospace'; ctx.textAlign='center';
    ctx.fillStyle=this.mutedTxt;
    ctx.fillText('NEUTRAL SPIRE', base.x, base.y+14);
  }

  /* ── Capital beacons ────────────────────────────────────────── */
  _drawCapitals() {
    const ctx=this.ctx;
    for (const id of this.tour) {
      const g=this.realmsData[id], spot=id===this.selectedRealmId;
      const p=this.project(...g.capital.pos); if(!p) continue;
      const col = this._colors[id];
      const rr = spot ? 10+3*Math.sin(this.pulse) : 5;
      ctx.beginPath(); ctx.arc(p.x,p.y,rr,0,6.28);
      ctx.strokeStyle = col; ctx.lineWidth = spot?1.8:1; ctx.stroke();
      ctx.beginPath(); ctx.arc(p.x,p.y,spot?3:2,0,6.28);
      ctx.fillStyle = col; ctx.fill();
    }
  }

  /* ── Trade arcs ─────────────────────────────────────────────── */
  _drawTrades() {
    const ctx=this.ctx;
    const acc=(this.trades||[]).filter(t=>t.status==='accepted');
    if (!acc.length) return;
    ctx.save();
    for (const tr of acc) {
      const gA=this.realmsData[tr.sender_id], gB=this.realmsData[tr.receiver_id];
      if (!gA||!gB) continue;
      const [ax,ay,az]=gA.capital.pos, [bx,by,bz]=gB.capital.pos;
      ctx.beginPath(); let f=true;
      for (let s=0; s<=16; s++) {
        const t=s/16, arc=Math.sin(t*Math.PI)*60;
        const p=this.project(ax+(bx-ax)*t, ay+(by-ay)*t, az+(bz-az)*t+arc);
        if(p) { f?ctx.moveTo(p.x,p.y):ctx.lineTo(p.x,p.y); f=false; }
      }
      ctx.strokeStyle=this.textCol; ctx.lineWidth=1.5;
      ctx.setLineDash([5,4]); ctx.stroke(); ctx.setLineDash([]);
    }
    ctx.restore();
  }

  /* ── Compact on-map badges for non-spotlight countries ──────── */
  _drawMiniBadges() {
    const ctx=this.ctx;
    const cards=[];
    for (const id of this.tour) {
      if (id===this.selectedRealmId) continue;
      const g=this.realmsData[id];
      const p=this.project(g.capital.pos[0], g.capital.pos[1], g.capital.pos[2]+28);
      if (p) cards.push({ id, g, p, depth: p.depth,
        rd:(this.realms||[]).find(r=>r.id===id)||{} });
    }
    cards.sort((a,b)=>b.depth-a.depth);

    for (const c of cards) {
      const { g, p, rd, id } = c;
      const W=140, H=42;
      let bx=p.x-W/2, by=p.y-H-6;
      bx=Math.max(8, Math.min(this.width-W-8, bx));
      by=Math.max(8, Math.min(this.height-H-8, by));
      this.hits.push({ id, x:bx, y:by, w:W, h:H });

      const col=this._colors[id];
      // leader
      ctx.strokeStyle=col+'77'; ctx.lineWidth=0.6; ctx.setLineDash([2,3]);
      const cp2=this.project(...g.capital.pos);
      if(cp2) { ctx.beginPath(); ctx.moveTo(cp2.x,cp2.y); ctx.lineTo(bx+W/2,by+H); ctx.stroke(); }
      ctx.setLineDash([]);

      // card
      ctx.fillStyle = this.cardBg;
      ctx.fillRect(bx,by,W,H);
      ctx.strokeStyle = col; ctx.lineWidth=1.5;
      ctx.strokeRect(bx,by,W,H);
      // left colour strip
      ctx.fillStyle = col; ctx.fillRect(bx,by,4,H);

      // name
      ctx.fillStyle = this.textCol; ctx.font='bold 9px monospace'; ctx.textAlign='left';
      ctx.fillText(g.name.toUpperCase().substring(0,18), bx+10, by+14);

      // mini resource bars
      const tiers = [
        ['🌾',rd.grain_tier],['⚙️',rd.cores_tier],
        ['🧵',rd.silk_tier],['⚔️',rd.military_tier]
      ];
      let ix=bx+8;
      for (const [ico,tier] of tiers) {
        const bars=this._tier(tier);
        ctx.fillStyle=this.mutedTxt; ctx.font='8px monospace'; ctx.textAlign='left';
        ctx.fillText(ico,ix,by+32);
        for (let b=1;b<=3;b++) {
          const tx=ix+13+(b-1)*4;
          if (b<=bars) { ctx.fillStyle=col; ctx.fillRect(tx,by+25,2.5,6); }
          else { ctx.strokeStyle=this.isDark?'rgba(255,255,255,0.15)':'rgba(0,0,0,0.12)';
                 ctx.lineWidth=0.5; ctx.strokeRect(tx,by+25,2.5,6); }
        }
        ix+=32;
      }
    }
  }

  /* ── LARGE sidebar panel for spotlight country ─────────────── */
  _drawSidebar() {
    const ctx=this.ctx;
    const id=this.selectedRealmId;
    const g=this.realmsData[id];
    const rd=(this.realms||[]).find(r=>r.id===id)||{};
    const col=this._colors[id];
    const dark=this.isDark;

    // ── Panel dimensions (right side, wall-projection large) ──
    const PW = Math.min(360, Math.floor(this.width * 0.28));
    const PH = Math.floor(this.height * 0.82);
    const px = this.width - PW - 16;
    const py = Math.floor((this.height - PH) / 2);

    // Parse colour
    const r2=parseInt(col.slice(1,3),16), g2=parseInt(col.slice(3,5),16), b2=parseInt(col.slice(5,7),16);

    // ── Panel background with transparency ──
    ctx.fillStyle = dark ? 'rgba(8,14,28,0.88)' : 'rgba(255,255,255,0.92)';
    ctx.fillRect(px, py, PW, PH);

    // ── Left colour accent strip ──
    ctx.fillStyle = col;
    ctx.fillRect(px, py, 5, PH);

    // ── Border ──
    ctx.strokeStyle = col + '88';
    ctx.lineWidth = 1.5;
    ctx.strokeRect(px, py, PW, PH);

    // ── Title area ──
    const tx = px + 20, tw = PW - 40;
    let ty = py + 32;

    // Country colour dot + name
    ctx.beginPath(); ctx.arc(tx, ty-4, 6, 0, 6.28);
    ctx.fillStyle = col; ctx.fill();

    ctx.fillStyle = this.textCol;
    ctx.font = 'bold 18px monospace'; ctx.textAlign = 'left';
    ctx.fillText(g.name.toUpperCase(), tx + 14, ty);
    ty += 18;

    // Capital
    ctx.fillStyle = this.mutedTxt;
    ctx.font = '11px monospace';
    ctx.fillText(g.capital.name.toUpperCase(), tx, ty);
    ty += 10;

    // Votes
    const votes = rd.assembly_votes || 1;
    ctx.fillText(`ASSEMBLY VOTES: ${votes}`, tx, ty);
    ty += 22;

    // ── Divider ──
    ctx.strokeStyle = dark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.08)';
    ctx.lineWidth = 0.8;
    ctx.beginPath(); ctx.moveTo(tx, ty); ctx.lineTo(tx + tw, ty); ctx.stroke();
    ty += 20;

    // ── Resource section header ──
    ctx.fillStyle = this.mutedTxt; ctx.font = 'bold 10px monospace';
    ctx.fillText('RESOURCES', tx, ty);
    ty += 20;

    // ── 4 resources with LARGE 3-bar gauges ──
    const res = [
      ['🌾', 'GRAIN',    rd.grain_tier],
      ['⚙️', 'CORES',    rd.cores_tier],
      ['🧵', 'SILK',     rd.silk_tier],
      ['⚔️', 'MILITARY', rd.military_tier],
    ];

    const barW = Math.floor((tw - 80) / 3);
    const barH = 16;

    for (const [ico, lbl, tier] of res) {
      const bars = this._tier(tier);

      // icon + label
      ctx.fillStyle = this.textCol; ctx.font = '13px monospace'; ctx.textAlign = 'left';
      ctx.fillText(`${ico} ${lbl}`, tx, ty);

      // Level label (right-aligned)
      const lvl = bars === 1 ? 'LOW' : bars === 3 ? 'HIGH' : 'MED';
      ctx.font = 'bold 12px monospace'; ctx.textAlign = 'right';
      ctx.fillStyle = bars===1 ? (dark?'#f87171':'#dc2626') :
                      bars===3 ? (dark?'#4ade80':'#16a34a') :
                                 (dark?'#fbbf24':'#ca8a04');
      ctx.fillText(lvl, tx + tw, ty);
      ty += 8;

      // 3 bar blocks
      const gx = tx;
      for (let b = 1; b <= 3; b++) {
        const bx2 = gx + (b-1) * (barW + 4);
        if (b <= bars) {
          ctx.fillStyle = `rgba(${r2},${g2},${b2},${dark?0.7:0.5})`;
          ctx.fillRect(bx2, ty, barW, barH);
          // highlight border
          ctx.strokeStyle = col; ctx.lineWidth = 1;
          ctx.strokeRect(bx2, ty, barW, barH);
        } else {
          ctx.strokeStyle = dark ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.08)';
          ctx.lineWidth = 1;
          ctx.strokeRect(bx2, ty, barW, barH);
        }
      }
      ty += barH + 18;
    }

    // ── Divider ──
    ctx.strokeStyle = dark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.08)';
    ctx.lineWidth = 0.8;
    ctx.beginPath(); ctx.moveTo(tx, ty); ctx.lineTo(tx+tw, ty); ctx.stroke();
    ty += 22;

    // ── Status section ──
    ctx.fillStyle = this.mutedTxt; ctx.font = 'bold 10px monospace'; ctx.textAlign = 'left';
    ctx.fillText('STATUS', tx, ty);
    ty += 20;

    // Stability
    const stab = (rd.stability_tier || 'STABLE').toUpperCase();
    ctx.fillStyle = this.textCol; ctx.font = '12px monospace';
    ctx.fillText('STABILITY', tx, ty);
    ctx.font = 'bold 12px monospace'; ctx.textAlign = 'right';
    ctx.fillText(stab, tx + tw, ty);
    ty += 24;

    // Hazard status
    let haz = 'ALL CLEAR', hazCol = dark ? '#4ade80' : '#16a34a';
    if (rd.is_quarantined) { haz = '⚠ QUARANTINE'; hazCol = dark ? '#f87171' : '#dc2626'; }
    else if (rd.is_starving) { haz = '⚠ FAMINE'; hazCol = dark ? '#fbbf24' : '#ca8a04'; }

    ctx.fillStyle = this.textCol; ctx.font = '12px monospace'; ctx.textAlign = 'left';
    ctx.fillText('CONDITION', tx, ty);
    ctx.font = 'bold 12px monospace'; ctx.textAlign = 'right';
    ctx.fillStyle = hazCol;
    ctx.fillText(haz, tx + tw, ty);
    ty += 24;

    // Ethos
    if (rd.ethos) {
      ctx.fillStyle = this.textCol; ctx.font = '12px monospace'; ctx.textAlign = 'left';
      ctx.fillText('ETHOS', tx, ty);
      ctx.font = 'bold 11px monospace'; ctx.textAlign = 'right';
      ctx.fillStyle = this.mutedTxt;
      ctx.fillText(rd.ethos.toUpperCase(), tx + tw, ty);
    }

    // ── Leader line from panel to capital ──
    const cp = this.project(...g.capital.pos);
    if (cp && cp.x < px - 10) {
      ctx.strokeStyle = col + '55'; ctx.lineWidth = 1;
      ctx.setLineDash([4,4]);
      ctx.beginPath(); ctx.moveTo(cp.x, cp.y); ctx.lineTo(px, py + PH/2);
      ctx.stroke(); ctx.setLineDash([]);
    }
  }
}

// ── Global exposure ──
if (typeof window !== 'undefined') window.World3DMap = World3DMap;
if (typeof module !== 'undefined' && module.exports) module.exports = { World3DMap };
