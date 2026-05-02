// Avatar: The Last Airbender - Free Play Bending Game

const W = 1200, H = 600;
const GROUND = H - 80;
const GRAVITY = 0.65;

// ─── ELEMENT DEFINITIONS ───────────────────────────────────────────────────

const ELEM = {
  water: {
    name: 'Water', key: '1',
    color: '#29b6f6', glow: '#0288d1', dark: '#01579b',
    bgGrad: ['#0a1a2e', '#0d2b45'],
    basic:   { name: 'Water Whip',  cd: 280,  dmg: 12, spd: 14, r: 8,  col: '#29b6f6', pierce: false },
    special: { name: 'Ice Freeze',  cd: 1400, dmg: 25, spd: 8,  r: 14, col: '#b3e5fc', freeze: 2200 },
  },
  earth: {
    name: 'Earth', key: '2',
    color: '#8d6e63', glow: '#5d4037', dark: '#3e2723',
    bgGrad: ['#1a1208', '#2a1c10'],
    basic:   { name: 'Rock Throw',   cd: 480,  dmg: 22, spd: 10, r: 13, col: '#8d6e63', gravity: 0.3 },
    special: { name: 'Earth Fissure',cd: 1800, dmg: 45, spd: 0,  r: 0,  col: '#6d4c41', fissure: true },
  },
  fire: {
    name: 'Fire', key: '3',
    color: '#ff7043', glow: '#d84315', dark: '#bf360c',
    bgGrad: ['#1a0800', '#2d0f00'],
    basic:   { name: 'Fire Blast', cd: 180,  dmg: 9,  spd: 17, r: 10, col: '#ff7043', burn: 400 },
    special: { name: 'Fire Wave',  cd: 1600, dmg: 38, spd: 4,  r: 12, col: '#ff5722', expand: 3.5 },
  },
  air: {
    name: 'Air', key: '4',
    color: '#b0bec5', glow: '#78909c', dark: '#455a64',
    bgGrad: ['#0d1117', '#141e26'],
    basic:   { name: 'Air Blast',   cd: 220,  dmg: 6,  spd: 15, r: 11, col: 'rgba(176,190,197,0.85)', kb: 14 },
    special: { name: 'Air Tornado', cd: 2000, dmg: 18, spd: 0,  r: 70, col: 'rgba(200,210,215,0.6)',  tornado: true },
  },
};

const ELEM_ORDER = ['water', 'earth', 'fire', 'air'];

// ─── PLATFORMS ─────────────────────────────────────────────────────────────

const PLATFORMS = [
  { x: 0,    y: GROUND, w: W,   h: 80 },   // ground
  { x: 180,  y: GROUND - 140, w: 160, h: 16 },
  { x: 520,  y: GROUND - 210, w: 170, h: 16 },
  { x: 860,  y: GROUND - 140, w: 160, h: 16 },
];

// ─── ENEMY WAVE DEFINITIONS ────────────────────────────────────────────────

const ENEMY_DEFS = {
  fire_soldier: {
    label: 'Fire Soldier', hp: 55, spd: 1.4, dmg: 8, xp: 10,
    elem: 'fire', atkRange: 320, atkCd: 1600, projSpd: 11,
    bodyCol: '#c62828', armorCol: '#880e4f', w: 32, h: 52,
  },
  earthbender: {
    label: 'Earthbender', hp: 100, spd: 1.0, dmg: 16, xp: 18,
    elem: 'earth', atkRange: 360, atkCd: 2100, projSpd: 8,
    bodyCol: '#2e7d32', armorCol: '#1b5e20', w: 36, h: 56,
  },
  water_warrior: {
    label: 'Water Warrior', hp: 48, spd: 2.1, dmg: 7, xp: 12,
    elem: 'water', atkRange: 290, atkCd: 1200, projSpd: 13,
    bodyCol: '#0277bd', armorCol: '#01579b', w: 28, h: 50,
  },
  elite: {
    label: 'Elite Firebender', hp: 160, spd: 2.3, dmg: 22, xp: 40,
    elem: 'fire', atkRange: 420, atkCd: 900, projSpd: 15,
    bodyCol: '#b71c1c', armorCol: '#7f0000', w: 38, h: 58,
  },
};

const WAVE_TEMPLATES = [
  [{ type: 'fire_soldier', n: 3 }],
  [{ type: 'fire_soldier', n: 2 }, { type: 'earthbender', n: 1 }],
  [{ type: 'earthbender', n: 2 }, { type: 'water_warrior', n: 2 }],
  [{ type: 'fire_soldier', n: 2 }, { type: 'water_warrior', n: 2 }, { type: 'earthbender', n: 1 }],
  [{ type: 'elite', n: 1 }, { type: 'fire_soldier', n: 3 }],
  [{ type: 'elite', n: 2 }, { type: 'earthbender', n: 2 }, { type: 'water_warrior', n: 2 }],
];

// ─── UTILITIES ──────────────────────────────────────────────────────────────

function rng(min, max) { return min + Math.random() * (max - min); }
function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
function dist(a, b) { return Math.hypot(a.x - b.x, a.y - b.y); }

// ─── PARTICLES ──────────────────────────────────────────────────────────────

class Particle {
  constructor(x, y, col, vx, vy, life, r) {
    this.x = x; this.y = y;
    this.vx = vx; this.vy = vy;
    this.col = col;
    this.life = this.maxLife = life;
    this.r = r;
  }
  update(dt) {
    this.x += this.vx * dt;
    this.y += this.vy * dt;
    this.vy += GRAVITY * 0.5 * dt;
    this.life -= dt;
  }
  draw(ctx) {
    const a = clamp(this.life / this.maxLife, 0, 1);
    ctx.save();
    ctx.globalAlpha = a;
    ctx.fillStyle = this.col;
    ctx.shadowBlur = 8; ctx.shadowColor = this.col;
    ctx.beginPath();
    ctx.arc(this.x, this.y, this.r * a, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }
  get dead() { return this.life <= 0; }
}

function spawnBurst(arr, x, y, col, count = 10) {
  for (let i = 0; i < count; i++) {
    const ang = rng(0, Math.PI * 2);
    const spd = rng(1, 4);
    arr.push(new Particle(x, y, col, Math.cos(ang) * spd, Math.sin(ang) * spd - 2, rng(300, 600), rng(2, 6)));
  }
}

function spawnHitSpark(arr, x, y, col) {
  for (let i = 0; i < 6; i++) {
    const ang = rng(0, Math.PI * 2);
    arr.push(new Particle(x, y, col, Math.cos(ang) * rng(2, 6), Math.sin(ang) * rng(2, 6) - 1, rng(200, 400), rng(3, 7)));
  }
}

// ─── PROJECTILE ─────────────────────────────────────────────────────────────

class Projectile {
  constructor(x, y, vx, vy, r, col, dmg, fromPlayer, opts = {}) {
    this.x = x; this.y = y;
    this.vx = vx; this.vy = vy;
    this.r = r; this.col = col;
    this.dmg = dmg;
    this.fromPlayer = fromPlayer;
    this.opts = opts;
    this.dead = false;
    this.age = 0;
    this.trail = [];
  }
  update(dt) {
    this.trail.push({ x: this.x, y: this.y });
    if (this.trail.length > 8) this.trail.shift();

    if (this.opts.gravity) this.vy += this.opts.gravity * dt;
    if (this.opts.expand)  this.r += this.opts.expand * dt * 0.06;

    this.x += this.vx * dt * 0.06;
    this.y += this.vy * dt * 0.06;
    this.age += dt;

    // lifetime
    const maxAge = this.opts.tornado ? 2500 : this.opts.expand ? 1400 : 3500;
    if (this.age > maxAge) this.dead = true;
    if (this.x < -60 || this.x > W + 60 || this.y > H + 60) this.dead = true;
  }
  draw(ctx) {
    ctx.save();
    ctx.shadowBlur = 18; ctx.shadowColor = this.col;

    // trail
    if (!this.opts.expand && !this.opts.tornado && this.trail.length > 1) {
      for (let i = 1; i < this.trail.length; i++) {
        const a = i / this.trail.length * 0.5;
        ctx.globalAlpha = a;
        ctx.strokeStyle = this.col;
        ctx.lineWidth = this.r * a;
        ctx.lineCap = 'round';
        ctx.beginPath();
        ctx.moveTo(this.trail[i - 1].x, this.trail[i - 1].y);
        ctx.lineTo(this.trail[i].x, this.trail[i].y);
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
    }

    if (this.opts.tornado) {
      // spinning rings
      const rings = 4;
      const t = this.age / 300;
      ctx.globalAlpha = 0.6;
      for (let i = 0; i < rings; i++) {
        const ang = t + (i / rings) * Math.PI * 2;
        const rx = this.r * 0.9;
        const ry = this.r * 0.4;
        ctx.strokeStyle = this.col;
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.ellipse(this.x, this.y, rx, ry, ang, 0, Math.PI * 2);
        ctx.stroke();
      }
    } else {
      ctx.globalAlpha = 1;
      ctx.fillStyle = this.col;
      ctx.beginPath();
      ctx.arc(this.x, this.y, this.r, 0, Math.PI * 2);
      ctx.fill();

      if (this.opts.freeze) {
        // ice spike — draw a diamond
        ctx.strokeStyle = '#e1f5fe'; ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(this.x, this.y - this.r * 1.6);
        ctx.lineTo(this.x + this.r, this.y);
        ctx.lineTo(this.x, this.y + this.r * 1.6);
        ctx.lineTo(this.x - this.r, this.y);
        ctx.closePath(); ctx.stroke();
      }
    }
    ctx.restore();
  }
}

// ─── ENEMY ──────────────────────────────────────────────────────────────────

class Enemy {
  constructor(def, x) {
    Object.assign(this, def);
    this.maxHp = this.hp;
    this.x = x;
    this.y = GROUND - this.h;
    this.vx = 0; this.vy = 0;
    this.onGround = true;
    this.atkTimer = rng(500, def.atkCd);
    this.frozen = 0;
    this.burnTimer = 0;
    this.facing = -1;
    this.dead = false;
    this.deathAnim = 0;
    this.hitFlash = 0;
    this.id = Math.random();
  }

  update(dt, player, projectiles, particles) {
    if (this.dead) { this.deathAnim -= dt; return; }

    this.hitFlash = Math.max(0, this.hitFlash - dt);

    if (this.frozen > 0) {
      this.frozen -= dt;
      return;
    }

    if (this.burnTimer > 0) {
      this.burnTimer -= dt;
      if (this.burnTimer % 200 < dt) {
        this.hp -= 2;
        spawnHitSpark(particles, this.x + this.w / 2, this.y, '#ff7043');
        if (this.hp <= 0) this.die(particles);
      }
    }

    const px = player.x + player.w / 2;
    const ex = this.x + this.w / 2;
    this.facing = px < ex ? -1 : 1;

    const d = Math.abs(px - ex);

    // Move toward player if far
    if (d > 80) {
      this.vx = this.facing * this.spd;
    } else {
      this.vx = 0;
    }

    // Attack
    this.atkTimer -= dt;
    if (this.atkTimer <= 0 && d <= this.atkRange) {
      this.atkTimer = this.atkCd;
      this.shoot(player, projectiles, particles);
    }

    // Gravity + movement
    this.vy += GRAVITY;
    this.x += this.vx;
    this.y += this.vy;

    // Platform collision
    this.onGround = false;
    for (const p of PLATFORMS) {
      if (
        this.x + this.w > p.x && this.x < p.x + p.w &&
        this.y + this.h > p.y && this.y + this.h < p.y + p.h + 20 &&
        this.vy >= 0
      ) {
        this.y = p.y - this.h;
        this.vy = 0;
        this.onGround = true;
      }
    }

    // Boundary
    this.x = clamp(this.x, 10, W - this.w - 10);
  }

  shoot(player, projectiles, particles) {
    const ex = this.x + this.w / 2;
    const ey = this.y + this.h * 0.4;
    const px = player.x + player.w / 2;
    const py = player.y + player.h * 0.4;
    const ang = Math.atan2(py - ey, px - ex);
    const col = ELEM[this.elem].color;
    projectiles.push(new Projectile(
      ex, ey,
      Math.cos(ang) * this.projSpd,
      Math.sin(ang) * this.projSpd,
      9, col, this.dmg, false,
      this.elem === 'earth' ? { gravity: 0.2 } : {}
    ));
    spawnHitSpark(particles, ex, ey, col);
  }

  takeDamage(dmg, opts, particles) {
    if (this.dead) return;
    this.hp -= dmg;
    this.hitFlash = 150;
    spawnHitSpark(particles, this.x + this.w / 2, this.y + this.h / 2, '#fff');
    if (opts.freeze)  this.frozen = opts.freeze;
    if (opts.burn)    this.burnTimer = opts.burn;
    if (opts.kb)      this.vx -= this.facing * opts.kb;
    if (this.hp <= 0) this.die(particles);
  }

  die(particles) {
    this.dead = true;
    this.deathAnim = 600;
    spawnBurst(particles, this.x + this.w / 2, this.y + this.h / 2, ELEM[this.elem].color, 16);
  }

  draw(ctx) {
    if (this.dead) return;

    const flash = this.hitFlash > 0;
    const frozen = this.frozen > 0;

    ctx.save();

    // Freeze tint
    if (frozen) {
      ctx.shadowBlur = 20; ctx.shadowColor = '#b3e5fc';
    }

    // Hit flash
    if (flash && Math.floor(Date.now() / 80) % 2 === 0) {
      ctx.globalAlpha = 0.6;
    }

    const bodyCol = frozen ? '#90caf9' : this.bodyCol;
    const armorCol = frozen ? '#64b5f6' : this.armorCol;

    // Body
    ctx.fillStyle = bodyCol;
    ctx.fillRect(this.x + 6, this.y + 14, this.w - 12, this.h - 14);

    // Armor
    ctx.fillStyle = armorCol;
    ctx.fillRect(this.x + 4, this.y + 14, this.w - 8, 20);

    // Head
    ctx.beginPath();
    ctx.arc(this.x + this.w / 2, this.y + 10, 12, 0, Math.PI * 2);
    ctx.fillStyle = '#d7a86e';
    ctx.fill();

    // Element indicator dot
    ctx.beginPath();
    ctx.arc(this.x + this.w / 2, this.y + 10, 4, 0, Math.PI * 2);
    ctx.fillStyle = ELEM[this.elem].color;
    ctx.shadowBlur = 10; ctx.shadowColor = ELEM[this.elem].color;
    ctx.fill();

    // HP bar
    const bw = this.w + 8;
    const bx = this.x - 4;
    const by = this.y - 12;
    ctx.fillStyle = '#333';
    ctx.fillRect(bx, by, bw, 6);
    ctx.fillStyle = this.hp / this.maxHp > 0.5 ? '#4caf50' : this.hp / this.maxHp > 0.25 ? '#ff9800' : '#f44336';
    ctx.fillRect(bx, by, bw * (this.hp / this.maxHp), 6);

    ctx.restore();
  }
}

// ─── PLAYER ─────────────────────────────────────────────────────────────────

class Player {
  constructor() {
    this.w = 36; this.h = 58;
    this.x = 120; this.y = GROUND - this.h;
    this.vx = 0; this.vy = 0;
    this.onGround = true;
    this.jumpCount = 0;
    this.facing = 1;
    this.hp = 100; this.maxHp = 100;
    this.elem = 'fire';
    this.cooldowns = { basic: 0, special: 0, dodge: 0 };
    this.dodging = false;
    this.dodgeTimer = 0;
    this.invincible = false;
    this.invTimer = 0;
    this.dead = false;
    this.score = 0;
    this.auraAng = 0;
    this.animFrame = 0;
    this.animTimer = 0;
    this.attackAnim = 0;
  }

  get maxJumps() { return this.elem === 'air' ? 3 : 2; }
  get moveSpeed() { return this.elem === 'air' ? 5.5 : 4.5; }

  update(dt, keys, enemies, projectiles, particles) {
    if (this.dead) return;

    // Cooldowns
    for (const k in this.cooldowns) {
      this.cooldowns[k] = Math.max(0, this.cooldowns[k] - dt);
    }
    this.invTimer = Math.max(0, this.invTimer - dt);
    this.invincible = this.invTimer > 0;
    this.auraAng += dt * 0.003;
    this.attackAnim = Math.max(0, this.attackAnim - dt);

    // Dodge movement
    if (this.dodging) {
      this.dodgeTimer -= dt;
      this.vx = this.facing * this.moveSpeed * 2.8;
      if (this.dodgeTimer <= 0) this.dodging = false;
    } else {
      // Horizontal movement
      const left  = keys['a'] || keys['arrowleft'];
      const right = keys['d'] || keys['arrowright'];
      if (left)  { this.vx = -this.moveSpeed; this.facing = -1; }
      else if (right) { this.vx = this.moveSpeed; this.facing = 1; }
      else this.vx *= 0.75;
    }

    // Gravity
    this.vy += GRAVITY;

    // Move
    this.x += this.vx;
    this.y += this.vy;

    // Platform collision
    this.onGround = false;
    for (const p of PLATFORMS) {
      if (
        this.x + this.w > p.x && this.x < p.x + p.w &&
        this.y + this.h > p.y && this.y + this.h < p.y + p.h + 16 &&
        this.vy >= 0
      ) {
        this.y = p.y - this.h;
        this.vy = 0;
        this.onGround = true;
        this.jumpCount = 0;
      }
    }

    this.x = clamp(this.x, 0, W - this.w);
    if (this.y > H + 200) { this.hp = 0; this.dead = true; }

    // Animation
    this.animTimer += dt;
    if (this.animTimer > 150) { this.animFrame ^= 1; this.animTimer = 0; }
  }

  jump() {
    if (this.jumpCount < this.maxJumps) {
      this.vy = this.elem === 'air' ? -14 : -16;
      this.jumpCount++;
      this.onGround = false;
    }
  }

  dodge(particles) {
    if (this.cooldowns.dodge > 0 || this.dodging) return;
    this.cooldowns.dodge = 1400;
    this.dodging = true;
    this.dodgeTimer = 180;
    this.invincible = true;
    this.invTimer = 180;
    const col = ELEM[this.elem].color;
    spawnBurst(particles, this.x + this.w / 2, this.y + this.h / 2, col, 8);
  }

  basicAttack(projectiles, particles) {
    if (this.cooldowns.basic > 0) return;
    const cfg = ELEM[this.elem].basic;
    this.cooldowns.basic = cfg.cd;
    this.attackAnim = 200;
    const cx = this.x + (this.facing > 0 ? this.w : 0);
    const cy = this.y + this.h * 0.35;
    const opts = {};
    if (cfg.gravity) opts.gravity = cfg.gravity;
    if (cfg.burn)    opts.burn = cfg.burn;
    if (cfg.freeze)  opts.freeze = cfg.freeze;
    if (cfg.kb)      opts.kb = cfg.kb;
    projectiles.push(new Projectile(cx, cy, this.facing * cfg.spd, cfg.gravity ? -4 : 0, cfg.r, cfg.col, cfg.dmg, true, opts));
    spawnHitSpark(particles, cx, cy, cfg.col);
  }

  specialAttack(projectiles, particles) {
    if (this.cooldowns.special > 0) return;
    const cfg = ELEM[this.elem].special;
    this.cooldowns.special = cfg.cd;
    this.attackAnim = 350;
    const cx = this.x + (this.facing > 0 ? this.w + 10 : -10);
    const cy = this.y + this.h * 0.4;
    const opts = {};
    if (cfg.freeze)  opts.freeze = cfg.freeze;
    if (cfg.fissure) opts.fissure = true;
    if (cfg.expand)  opts.expand = cfg.expand;
    if (cfg.tornado) opts.tornado = true;
    if (cfg.fissure) {
      // Earth fissure — hit all enemies on ground directly (handled in game loop)
      this._fissure = true;
      spawnBurst(particles, this.x + this.w / 2, this.y + this.h, ELEM.earth.color, 20);
      return;
    }
    projectiles.push(new Projectile(cx, cy, this.facing * cfg.spd, 0, cfg.r, cfg.col, cfg.dmg, true, opts));
    spawnBurst(particles, cx, cy, cfg.col, 12);
  }

  takeDamage(dmg, particles) {
    if (this.invincible || this.dead) return;
    this.hp -= dmg;
    this.invincible = true;
    this.invTimer = 700;
    spawnHitSpark(particles, this.x + this.w / 2, this.y + this.h * 0.4, '#fff');
    if (this.hp <= 0) { this.hp = 0; this.dead = true; }
  }

  draw(ctx) {
    const el = ELEM[this.elem];
    const cx = this.x + this.w / 2;
    const cy = this.y + this.h / 2;

    // Invisible flash
    if (this.invincible && Math.floor(Date.now() / 90) % 2 === 0) return;

    ctx.save();

    // Aura orbit
    ctx.shadowBlur = 24; ctx.shadowColor = el.color;
    const orbCount = 3;
    for (let i = 0; i < orbCount; i++) {
      const ang = this.auraAng + (i / orbCount) * Math.PI * 2;
      const ox = cx + Math.cos(ang) * 28;
      const oy = cy + Math.sin(ang) * 12;
      ctx.fillStyle = el.color;
      ctx.globalAlpha = 0.55;
      ctx.beginPath(); ctx.arc(ox, oy, 5, 0, Math.PI * 2); ctx.fill();
    }
    ctx.globalAlpha = 1; ctx.shadowBlur = 0;

    // Legs
    const legAnim = this.onGround ? Math.sin(this.animFrame * Math.PI) * 6 : 0;
    ctx.fillStyle = '#5d4037';
    ctx.fillRect(this.x + 6,  this.y + 38, 10, 20 + legAnim);
    ctx.fillRect(this.x + 20, this.y + 38, 10, 20 - legAnim);

    // Body / robe
    ctx.fillStyle = '#f57f17'; // fire nation orange base → Avatar orange
    ctx.shadowBlur = 8; ctx.shadowColor = el.color;
    // Slightly animate if attacking
    const bodyOff = this.attackAnim > 0 ? (this.facing * 3) : 0;
    ctx.fillRect(this.x + 4 + bodyOff, this.y + 18, this.w - 8, 26);

    // Sash
    ctx.fillStyle = el.color;
    ctx.globalAlpha = 0.7;
    ctx.fillRect(this.x + 4 + bodyOff, this.y + 26, this.w - 8, 6);
    ctx.globalAlpha = 1;

    // Arms
    ctx.fillStyle = '#f5deb3';
    ctx.shadowBlur = 0;
    ctx.fillRect(this.x - 2 + bodyOff * 0.5, this.y + 20, 8, 18);
    ctx.fillRect(this.x + this.w - 6 + bodyOff * 0.5, this.y + 20, 8, 18);

    // Head
    ctx.fillStyle = '#f5deb3';
    ctx.shadowBlur = 0;
    ctx.beginPath();
    ctx.arc(cx, this.y + 12, 14, 0, Math.PI * 2);
    ctx.fill();

    // Avatar arrow tattoo (forehead)
    ctx.fillStyle = '#29b6f6';
    ctx.shadowBlur = 10; ctx.shadowColor = '#29b6f6';
    ctx.globalAlpha = 0.95;
    ctx.beginPath();
    ctx.moveTo(cx, this.y - 2);
    ctx.lineTo(cx - 6, this.y + 6);
    ctx.lineTo(cx + 6, this.y + 6);
    ctx.closePath(); ctx.fill();

    // Eyes
    ctx.fillStyle = '#1a237e';
    ctx.shadowBlur = 0; ctx.globalAlpha = 1;
    ctx.beginPath(); ctx.arc(cx - 5 + this.facing * 2, this.y + 12, 2.5, 0, Math.PI * 2); ctx.fill();

    // Ground shadow
    ctx.globalAlpha = 0.18;
    ctx.fillStyle = '#000';
    ctx.shadowBlur = 0;
    ctx.beginPath();
    ctx.ellipse(cx, GROUND, 22, 6, 0, 0, Math.PI * 2);
    ctx.fill();

    ctx.restore();
  }
}

// ─── FLOATING TEXT ───────────────────────────────────────────────────────────

class FloatText {
  constructor(x, y, text, col) {
    this.x = x; this.y = y; this.text = text; this.col = col;
    this.life = 900; this.vy = -0.7;
  }
  update(dt) { this.y += this.vy * dt * 0.06; this.life -= dt; }
  draw(ctx) {
    ctx.save();
    ctx.globalAlpha = clamp(this.life / 900, 0, 1);
    ctx.fillStyle = this.col;
    ctx.shadowBlur = 8; ctx.shadowColor = this.col;
    ctx.font = 'bold 18px Georgia';
    ctx.textAlign = 'center';
    ctx.fillText(this.text, this.x, this.y);
    ctx.restore();
  }
  get dead() { return this.life <= 0; }
}

// ─── GAME STATE ──────────────────────────────────────────────────────────────

const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');

const keys = {};
const mouse = { x: 0, y: 0 };

let player, enemies, projectiles, particles, floatTexts;
let wave, score, gamePhase, phaseTimer, spawnQueue, spawnTimer;

function initGame() {
  player     = new Player();
  enemies    = [];
  projectiles= [];
  particles  = [];
  floatTexts = [];
  wave       = 0;
  score      = 0;
  gamePhase  = 'wave_start'; // wave_start | playing | wave_clear | gameover
  phaseTimer = 1800;
  spawnQueue = [];
  spawnTimer = 0;
  startWave();
}

function startWave() {
  wave++;
  gamePhase = 'wave_start';
  phaseTimer = 1800;

  const template = WAVE_TEMPLATES[Math.min(wave - 1, WAVE_TEMPLATES.length - 1)];
  spawnQueue = [];
  for (const entry of template) {
    const extra = Math.max(0, wave - WAVE_TEMPLATES.length);
    const count = entry.n + (extra > 0 ? Math.ceil(extra * 0.5) : 0);
    for (let i = 0; i < count; i++) {
      spawnQueue.push(entry.type);
    }
  }
  // shuffle
  for (let i = spawnQueue.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [spawnQueue[i], spawnQueue[j]] = [spawnQueue[j], spawnQueue[i]];
  }
  spawnTimer = 0;
}

function spawnEnemy(type) {
  const def = { ...ENEMY_DEFS[type] };
  const side = Math.random() > 0.5;
  const x = side ? W - def.w - 20 : 20;
  enemies.push(new Enemy(def, x));
}

// ─── INPUT ───────────────────────────────────────────────────────────────────

document.addEventListener('keydown', e => {
  const k = e.key.toLowerCase();
  if (keys[k]) return;
  keys[k] = true;

  // Start screen
  if (!gameStarted) {
    if (k === 'enter' || k === ' ') { gameStarted = true; initGame(); }
    return;
  }

  if (gamePhase === 'gameover') {
    if (k === 'enter' || k === ' ' || k === 'r') initGame();
    return;
  }
  if (gamePhase === 'wave_start' && (k === ' ' || k === 'enter')) {
    phaseTimer = 0; // skip countdown
    return;
  }

  // Element switch
  if (k === '1') player.elem = 'water';
  if (k === '2') player.elem = 'earth';
  if (k === '3') player.elem = 'fire';
  if (k === '4') player.elem = 'air';

  // Jump
  if (k === 'w' || k === 'arrowup' || k === ' ') {
    e.preventDefault();
    player.jump();
  }

  // Attacks
  if (k === 'j' || k === 'z') player.basicAttack(projectiles, particles);
  if (k === 'k' || k === 'x') player.specialAttack(projectiles, particles);

  // Dodge
  if (k === 'shift') { e.preventDefault(); player.dodge(particles); }
});

document.addEventListener('keyup', e => { keys[e.key.toLowerCase()] = false; });

canvas.addEventListener('mousedown', e => {
  if (gamePhase !== 'playing') return;
  e.preventDefault();
  if (e.button === 0) player.basicAttack(projectiles, particles);
  if (e.button === 2) player.specialAttack(projectiles, particles);
});
canvas.addEventListener('contextmenu', e => e.preventDefault());
canvas.addEventListener('mousemove', e => {
  const r = canvas.getBoundingClientRect();
  mouse.x = (e.clientX - r.left) * (W / r.width);
  mouse.y = (e.clientY - r.top)  * (H / r.height);
});

// ─── COLLISION ───────────────────────────────────────────────────────────────

function rectsOverlap(ax, ay, aw, ah, bx, by, bw, bh) {
  return ax < bx + bw && ax + aw > bx && ay < by + bh && ay + ah > by;
}

function circleRect(cx, cy, cr, rx, ry, rw, rh) {
  const nx = clamp(cx, rx, rx + rw);
  const ny = clamp(cy, ry, ry + rh);
  return Math.hypot(cx - nx, cy - ny) < cr;
}

// ─── BACKGROUND RENDER ───────────────────────────────────────────────────────

function drawBackground() {
  const el = ELEM[player.elem];
  const grad = ctx.createLinearGradient(0, 0, 0, H);
  grad.addColorStop(0, el.bgGrad[0]);
  grad.addColorStop(1, el.bgGrad[1]);
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, W, H);

  // Distant mountains silhouette
  ctx.fillStyle = 'rgba(0,0,0,0.25)';
  ctx.beginPath();
  ctx.moveTo(0, H * 0.6);
  const mts = [0, 120, 200, 320, 430, 560, 680, 790, 900, 1020, 1120, 1200];
  const mh  = [0.6, 0.38, 0.5, 0.3, 0.45, 0.35, 0.52, 0.4, 0.48, 0.36, 0.55, 0.6];
  mts.forEach((mx, i) => ctx.lineTo(mx, H * mh[i]));
  ctx.lineTo(W, H);
  ctx.lineTo(0, H);
  ctx.closePath(); ctx.fill();

  // Ground
  const groundGrad = ctx.createLinearGradient(0, GROUND, 0, H);
  groundGrad.addColorStop(0, '#2c1a0e');
  groundGrad.addColorStop(1, '#1a0f08');
  ctx.fillStyle = groundGrad;
  ctx.fillRect(0, GROUND, W, H - GROUND);

  // Ground line glow
  ctx.strokeStyle = el.color;
  ctx.lineWidth = 2;
  ctx.globalAlpha = 0.3;
  ctx.beginPath();
  ctx.moveTo(0, GROUND); ctx.lineTo(W, GROUND);
  ctx.stroke();
  ctx.globalAlpha = 1;

  // Platforms
  for (let i = 1; i < PLATFORMS.length; i++) {
    const p = PLATFORMS[i];
    const pg = ctx.createLinearGradient(p.x, p.y, p.x, p.y + p.h);
    pg.addColorStop(0, '#4a3728');
    pg.addColorStop(1, '#2c1a0e');
    ctx.fillStyle = pg;
    ctx.fillRect(p.x, p.y, p.w, p.h);
    ctx.strokeStyle = el.color;
    ctx.lineWidth = 1.5;
    ctx.globalAlpha = 0.4;
    ctx.strokeRect(p.x, p.y, p.w, p.h);
    ctx.globalAlpha = 1;
  }
}

// ─── HUD ─────────────────────────────────────────────────────────────────────

function drawHUD() {
  const el = ELEM[player.elem];

  // Health bar
  const hbw = 220, hbh = 18;
  const hbx = 20, hby = 20;
  ctx.fillStyle = 'rgba(0,0,0,0.55)';
  ctx.fillRect(hbx - 2, hby - 2, hbw + 4, hbh + 4);
  ctx.fillStyle = '#333';
  ctx.fillRect(hbx, hby, hbw, hbh);
  const hpRatio = player.hp / player.maxHp;
  const hpCol = hpRatio > 0.5 ? '#4caf50' : hpRatio > 0.25 ? '#ff9800' : '#f44336';
  ctx.fillStyle = hpCol;
  ctx.shadowBlur = 8; ctx.shadowColor = hpCol;
  ctx.fillRect(hbx, hby, hbw * hpRatio, hbh);
  ctx.shadowBlur = 0;
  ctx.fillStyle = '#fff';
  ctx.font = 'bold 12px Georgia';
  ctx.textAlign = 'left';
  ctx.fillText(`HP: ${player.hp} / ${player.maxHp}`, hbx + 4, hby + 13);

  // Element panel
  const epx = 20, epy = 50;
  ELEM_ORDER.forEach((e, i) => {
    const el2 = ELEM[e];
    const ex = epx + i * 62;
    const active = player.elem === e;
    ctx.fillStyle = active ? el2.color : 'rgba(30,30,30,0.7)';
    ctx.shadowBlur = active ? 16 : 0; ctx.shadowColor = el2.color;
    ctx.strokeStyle = el2.color;
    ctx.lineWidth = active ? 2 : 1;
    roundRect(ctx, ex, epy, 56, 38, 6);
    ctx.fill(); ctx.stroke();
    ctx.shadowBlur = 0;
    ctx.fillStyle = active ? '#000' : el2.color;
    ctx.font = `bold 11px Georgia`;
    ctx.textAlign = 'center';
    ctx.fillText(`[${i + 1}] ${el2.name}`, ex + 28, epy + 24);
  });

  // Cooldown bars
  const cdx = 20, cdy = 100;
  drawCooldownBar(ctx, cdx,      cdy, 'Basic [J]',   player.cooldowns.basic,   ELEM[player.elem].basic.cd,   el.color);
  drawCooldownBar(ctx, cdx + 120, cdy, 'Special [K]', player.cooldowns.special, ELEM[player.elem].special.cd, el.color);
  drawCooldownBar(ctx, cdx + 240, cdy, 'Dodge [Shift]', player.cooldowns.dodge, 1400, '#aaa');

  // Wave / Score
  ctx.fillStyle = 'rgba(0,0,0,0.5)';
  ctx.fillRect(W - 160, 14, 146, 56);
  ctx.fillStyle = '#fff';
  ctx.font = 'bold 14px Georgia';
  ctx.textAlign = 'right';
  ctx.fillText(`Wave ${wave}`, W - 18, 36);
  ctx.fillStyle = '#ffd54f';
  ctx.fillText(`Score: ${score}`, W - 18, 58);

  // Enemies remaining
  const alive = enemies.filter(e => !e.dead).length;
  ctx.fillStyle = alive > 0 ? '#ef9a9a' : '#a5d6a7';
  ctx.font = '13px Georgia';
  ctx.fillText(`Enemies: ${alive + spawnQueue.length}`, W - 18, 78);

  // Controls hint (desktop only)
  if (!('ontouchstart' in window) && navigator.maxTouchPoints === 0) {
    ctx.fillStyle = 'rgba(255,255,255,0.3)';
    ctx.font = '11px Georgia';
    ctx.textAlign = 'center';
    ctx.fillText('WASD/Arrows: Move | Space/W: Jump | 1-4: Element | J: Basic | K: Special | Shift: Dodge', W / 2, H - 8);
  }
}

function drawCooldownBar(ctx, x, y, label, cd, maxCd, col) {
  const bw = 110, bh = 8;
  ctx.fillStyle = 'rgba(0,0,0,0.5)';
  ctx.fillRect(x, y, bw, bh + 14);
  ctx.fillStyle = '#333';
  ctx.fillRect(x, y + 14, bw, bh);
  const ratio = 1 - cd / maxCd;
  ctx.fillStyle = cd > 0 ? '#777' : col;
  ctx.shadowBlur = cd === 0 ? 6 : 0; ctx.shadowColor = col;
  ctx.fillRect(x, y + 14, bw * ratio, bh);
  ctx.shadowBlur = 0;
  ctx.fillStyle = '#ccc';
  ctx.font = '10px Georgia';
  ctx.textAlign = 'left';
  ctx.fillText(label, x + 2, y + 11);
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

function drawStartScreen() {
  ctx.fillStyle = 'rgba(0,0,0,0.85)';
  ctx.fillRect(0, 0, W, H);

  ctx.textAlign = 'center';
  ctx.fillStyle = '#ffd54f';
  ctx.shadowBlur = 20; ctx.shadowColor = '#ffa000';
  ctx.font = 'bold 52px Georgia';
  ctx.fillText('AVATAR: THE LAST AIRBENDER', W / 2, 130);

  ctx.shadowBlur = 0;
  ctx.fillStyle = '#ccc';
  ctx.font = '22px Georgia';
  ctx.fillText('Free Play Bending Game', W / 2, 175);

  ctx.font = '16px Georgia';
  const lines = [
    '1 / 2 / 3 / 4 — Switch Element (Water / Earth / Fire / Air)',
    'A / D or ← / → — Move       W / Space — Jump',
    'J or Left Click — Basic Attack',
    'K or Right Click — Special Attack',
    'Shift — Dodge (Invincibility frames)',
    '',
    'Air: Double jump + speed bonus',
    'Water: Ice Freeze stuns enemies',
    'Earth: Fissure hits all grounded enemies',
    'Fire: Burn damage over time',
  ];
  lines.forEach((l, i) => {
    ctx.fillStyle = l === '' ? '#fff' : (i < 5 ? '#e0e0e0' : ELEM[ELEM_ORDER[i - 6]]?.color ?? '#aaa');
    ctx.fillText(l, W / 2, 230 + i * 28);
  });

  ctx.font = 'bold 20px Georgia';
  ctx.fillStyle = '#ffd54f';
  ctx.shadowBlur = 10; ctx.shadowColor = '#ffa000';
  ctx.fillText('Press ENTER or SPACE to begin', W / 2, H - 40);
  ctx.shadowBlur = 0;
}

function drawWaveStart() {
  ctx.fillStyle = 'rgba(0,0,0,0.55)';
  ctx.fillRect(0, 0, W, H);
  ctx.textAlign = 'center';
  ctx.fillStyle = '#ffd54f';
  ctx.shadowBlur = 20; ctx.shadowColor = '#ffa000';
  ctx.font = 'bold 48px Georgia';
  ctx.fillText(`Wave ${wave}`, W / 2, H / 2 - 20);
  ctx.shadowBlur = 0;
  ctx.fillStyle = '#ccc';
  ctx.font = '20px Georgia';
  ctx.fillText('Get ready!  Press Space to start early', W / 2, H / 2 + 30);
}

function drawWaveClear() {
  ctx.fillStyle = 'rgba(0,0,0,0.55)';
  ctx.fillRect(0, 0, W, H);
  ctx.textAlign = 'center';
  ctx.fillStyle = '#a5d6a7';
  ctx.shadowBlur = 16; ctx.shadowColor = '#4caf50';
  ctx.font = 'bold 44px Georgia';
  ctx.fillText(`Wave ${wave} Clear!`, W / 2, H / 2 - 20);
  ctx.shadowBlur = 0;
  ctx.fillStyle = '#ffd54f';
  ctx.font = '22px Georgia';
  ctx.fillText(`Score: ${score}`, W / 2, H / 2 + 24);
  ctx.fillStyle = '#ccc';
  ctx.font = '18px Georgia';
  ctx.fillText('Next wave incoming…', W / 2, H / 2 + 60);
}

function drawGameOver() {
  ctx.fillStyle = 'rgba(0,0,0,0.8)';
  ctx.fillRect(0, 0, W, H);
  ctx.textAlign = 'center';
  ctx.fillStyle = '#ef5350';
  ctx.shadowBlur = 20; ctx.shadowColor = '#b71c1c';
  ctx.font = 'bold 56px Georgia';
  ctx.fillText('GAME OVER', W / 2, H / 2 - 40);
  ctx.shadowBlur = 0;
  ctx.fillStyle = '#ffd54f';
  ctx.font = '28px Georgia';
  ctx.fillText(`Final Score: ${score}   Wave: ${wave}`, W / 2, H / 2 + 20);
  ctx.fillStyle = '#ccc';
  ctx.font = '20px Georgia';
  ctx.fillText('Press R / Enter / Space to play again', W / 2, H / 2 + 70);
}

// ─── GAME LOOP ───────────────────────────────────────────────────────────────

let lastTime = 0;
let gameStarted = false;

function loop(timestamp) {
  const dt = Math.min(timestamp - lastTime, 50); // cap delta to avoid spiral
  lastTime = timestamp;

  ctx.clearRect(0, 0, W, H);

  if (!gameStarted) {
    // Start screen before first game
    drawBackground();
    drawStartScreen();
    requestAnimationFrame(loop);
    return;
  }

  drawBackground();

  // ── Phase logic ──
  if (gamePhase === 'wave_start') {
    phaseTimer -= dt;
    player.update(dt, keys, enemies, projectiles, particles);
    player.draw(ctx);
    drawHUD();
    drawTouchControls();
    drawWaveStart();
    if (phaseTimer <= 0) gamePhase = 'playing';
  }
  else if (gamePhase === 'playing') {
    // Spawn enemies
    if (spawnQueue.length > 0) {
      spawnTimer -= dt;
      if (spawnTimer <= 0) {
        spawnEnemy(spawnQueue.pop());
        spawnTimer = rng(600, 1400);
      }
    }

    // Update player
    player.update(dt, keys, enemies, projectiles, particles);

    // Earth fissure special
    if (player._fissure) {
      player._fissure = false;
      const cfg = ELEM.earth.special;
      for (const en of enemies) {
        if (!en.dead && en.onGround) {
          en.takeDamage(cfg.dmg, {}, particles);
          floatTexts.push(new FloatText(en.x + en.w / 2, en.y - 10, `-${cfg.dmg}`, ELEM.earth.color));
          score += 5;
        }
      }
    }

    // Update enemies
    for (const en of enemies) {
      en.update(dt, player, projectiles, particles);
    }

    // Update projectiles
    for (const p of projectiles) {
      p.update(dt);

      if (p.fromPlayer) {
        // Hit enemies
        for (const en of enemies) {
          if (en.dead) continue;
          if (circleRect(p.x, p.y, p.r, en.x, en.y, en.w, en.h)) {
            en.takeDamage(p.dmg, p.opts, particles);
            floatTexts.push(new FloatText(en.x + en.w / 2, en.y - 10, `-${p.dmg}`, '#fff'));
            score += Math.floor(p.dmg * 0.5);
            if (!p.opts.expand && !p.opts.tornado) p.dead = true;
          }
        }
      } else {
        // Hit player
        if (!player.dead && circleRect(p.x, p.y, p.r, player.x, player.y, player.w, player.h)) {
          player.takeDamage(p.dmg, particles);
          floatTexts.push(new FloatText(player.x + player.w / 2, player.y - 10, `-${p.dmg}`, '#f44336'));
          p.dead = true;
        }
      }

      // Platform collision for non-player projectiles
      if (!p.dead) {
        for (const plat of PLATFORMS) {
          if (circleRect(p.x, p.y, p.r, plat.x, plat.y, plat.w, plat.h)) {
            spawnHitSpark(particles, p.x, p.y, p.col);
            p.dead = true;
            break;
          }
        }
      }
    }

    // Tornado suck
    for (const p of projectiles) {
      if (!p.opts.tornado || p.dead) continue;
      for (const en of enemies) {
        if (en.dead) continue;
        const dx = p.x - (en.x + en.w / 2);
        const dy = p.y - (en.y + en.h / 2);
        const d = Math.hypot(dx, dy);
        if (d < p.r * 1.5) {
          en.vx += (dx / d) * 1.5;
          en.vy += (dy / d) * 1.5;
        }
      }
    }

    // Enemy melee damage
    for (const en of enemies) {
      if (en.dead) continue;
      if (rectsOverlap(player.x, player.y, player.w, player.h, en.x, en.y, en.w, en.h)) {
        player.takeDamage(en.dmg * 0.4, particles);
      }
    }

    // Update particles & floatTexts
    for (const p of particles)  p.update(dt);
    for (const f of floatTexts) f.update(dt);

    // Clean up dead objects
    projectiles.splice(0, projectiles.length, ...projectiles.filter(p => !p.dead));
    enemies.splice(0, enemies.length, ...enemies.filter(e => {
      if (e.dead && e.deathAnim <= 0) {
        score += e.xp ?? 10;
        return false;
      }
      return true;
    }));
    particles.splice(0, particles.length,  ...particles.filter(p => !p.dead));
    floatTexts.splice(0, floatTexts.length, ...floatTexts.filter(f => !f.dead));

    // Draw everything
    for (const p of particles)  p.draw(ctx);
    for (const p of projectiles) p.draw(ctx);
    for (const en of enemies)   en.draw(ctx);
    player.draw(ctx);
    for (const f of floatTexts) f.draw(ctx);

    drawHUD();
    drawTouchControls();

    // Check wave clear
    if (spawnQueue.length === 0 && enemies.every(e => e.dead)) {
      gamePhase = 'wave_clear';
      phaseTimer = 2200;
    }

    // Check game over
    if (player.dead) {
      gamePhase = 'gameover';
    }
  }
  else if (gamePhase === 'wave_clear') {
    for (const p of particles)  { p.update(dt); p.draw(ctx); }
    player.draw(ctx);
    drawHUD();
    drawWaveClear();
    phaseTimer -= dt;
    if (phaseTimer <= 0) startWave();
  }
  else if (gamePhase === 'gameover') {
    player.draw(ctx);
    drawHUD();
    drawGameOver();
  }

  requestAnimationFrame(loop);
}

// ─── INIT ────────────────────────────────────────────────────────────────────

canvas.addEventListener('click', () => {
  if (!gameStarted) {
    gameStarted = true;
    initGame();
  }
});

// ─── TOUCH CONTROLS ──────────────────────────────────────────────────────────

// Button layout in canvas-space (1200 x 600). Scaled automatically by CSS.
const TOUCH_BTNS = [
  // Movement – left cluster
  { id: 'left',    x: 15,  y: 475, w: 72, h: 72, key: 'a',     hold: true,  label: '◀' },
  { id: 'right',   x: 100, y: 475, w: 72, h: 72, key: 'd',     hold: true,  label: '▶' },
  { id: 'jump',    x: 57,  y: 395, w: 72, h: 72, key: ' ',     hold: false, label: '▲\nJUMP' },
  // Actions – right cluster
  { id: 'basic',   x: 1115, y: 475, w: 72, h: 72, key: 'j',     hold: false, label: 'J\nATK' },
  { id: 'special', x: 1030, y: 475, w: 72, h: 72, key: 'k',     hold: false, label: 'K\nSPEC' },
  { id: 'dodge',   x: 1115, y: 395, w: 72, h: 72, key: 'shift', hold: false, label: 'DODGE' },
  // Element strip – bottom center
  { id: 'e1', x: 418, y: 550, w: 82, h: 40, key: '1', hold: false, label: '1 Water',  elemCol: ELEM.water.color },
  { id: 'e2', x: 508, y: 550, w: 82, h: 40, key: '2', hold: false, label: '2 Earth',  elemCol: ELEM.earth.color },
  { id: 'e3', x: 598, y: 550, w: 82, h: 40, key: '3', hold: false, label: '3 Fire',   elemCol: ELEM.fire.color  },
  { id: 'e4', x: 688, y: 550, w: 82, h: 40, key: '4', hold: false, label: '4 Air',    elemCol: ELEM.air.color   },
];

const heldTouches = new Map(); // touchId → key

function toCanvasCoords(clientX, clientY) {
  const r = canvas.getBoundingClientRect();
  return {
    x: (clientX - r.left) * (W / r.width),
    y: (clientY - r.top)  * (H / r.height),
  };
}

function hitTestBtn(cx, cy) {
  for (const b of TOUCH_BTNS) {
    if (cx >= b.x && cx <= b.x + b.w && cy >= b.y && cy <= b.y + b.h) return b;
  }
  return null;
}

function fireTouchKey(key) {
  if (!player || player.dead) return;
  if (key === ' ')     player.jump();
  else if (key === 'j') player.basicAttack(projectiles, particles);
  else if (key === 'k') player.specialAttack(projectiles, particles);
  else if (key === 'shift') player.dodge(particles);
  else if (key === '1') player.elem = 'water';
  else if (key === '2') player.elem = 'earth';
  else if (key === '3') player.elem = 'fire';
  else if (key === '4') player.elem = 'air';
}

canvas.addEventListener('touchstart', e => {
  e.preventDefault();
  if (!gameStarted) { gameStarted = true; initGame(); return; }
  if (gamePhase === 'gameover') { initGame(); return; }
  if (gamePhase === 'wave_start') { phaseTimer = 0; return; }
  if (gamePhase !== 'playing') return;

  for (const t of e.changedTouches) {
    const { x, y } = toCanvasCoords(t.clientX, t.clientY);
    const btn = hitTestBtn(x, y);
    if (!btn) continue;
    if (btn.hold) {
      keys[btn.key] = true;
      heldTouches.set(t.identifier, btn.key);
    } else {
      fireTouchKey(btn.key);
    }
  }
}, { passive: false });

canvas.addEventListener('touchend', e => {
  e.preventDefault();
  for (const t of e.changedTouches) {
    const key = heldTouches.get(t.identifier);
    if (key) { keys[key] = false; heldTouches.delete(t.identifier); }
  }
}, { passive: false });

canvas.addEventListener('touchcancel', e => {
  for (const t of e.changedTouches) {
    const key = heldTouches.get(t.identifier);
    if (key) { keys[key] = false; heldTouches.delete(t.identifier); }
  }
});

function drawTouchControls() {
  if (gamePhase !== 'playing' && gamePhase !== 'wave_start') return;

  ctx.save();
  for (const b of TOUCH_BTNS) {
    const isElem = b.id.startsWith('e');
    const active = isElem
      ? player && player.elem === ELEM_ORDER[parseInt(b.key) - 1]
      : (b.hold && keys[b.key]);

    const baseAlpha = 0.45;
    ctx.globalAlpha = active ? 0.75 : baseAlpha;

    const col = b.elemCol ?? ELEM[player?.elem ?? 'fire'].color;

    // Background
    ctx.fillStyle = active ? col : 'rgba(0,0,0,0.5)';
    ctx.strokeStyle = col;
    ctx.lineWidth = active ? 2.5 : 1.5;
    ctx.shadowBlur = active ? 12 : 0;
    ctx.shadowColor = col;
    roundRect(ctx, b.x, b.y, b.w, b.h, 10);
    ctx.fill();
    ctx.stroke();

    // Label
    ctx.shadowBlur = 0;
    ctx.fillStyle = active ? '#000' : '#fff';
    ctx.globalAlpha = active ? 0.9 : 0.8;
    ctx.font = `bold ${isElem ? 11 : 13}px Georgia`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    const lines = b.label.split('\n');
    if (lines.length === 2) {
      ctx.fillText(lines[0], b.x + b.w / 2, b.y + b.h / 2 - 7);
      ctx.font = `${isElem ? 10 : 10}px Georgia`;
      ctx.fillText(lines[1], b.x + b.w / 2, b.y + b.h / 2 + 7);
    } else {
      ctx.fillText(b.label, b.x + b.w / 2, b.y + b.h / 2);
    }
  }
  ctx.globalAlpha = 1;
  ctx.textBaseline = 'alphabetic';
  ctx.restore();
}

requestAnimationFrame(ts => { lastTime = ts; requestAnimationFrame(loop); });
