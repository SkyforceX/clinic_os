/* ═══════════════════════════════════════════════════════════════
   authentication/js/scripts.js
   Staff login — canvas scene engine + UI interactions

   4 scenes (canvas 2D API, no dependencies):
     morning   05:00 – 10:59  Bình minh
     noon      11:00 – 13:59  Buổi trưa
     afternoon 14:00 – 18:59  Xế chiều
     evening   19:00 – 04:59  Đêm

   Each scene owns: init(), draw(t), onResize()
   ═══════════════════════════════════════════════════════════════ */

(function () {
  "use strict";

  /* ════════════════════════════════════════════════════════════
     UTILITIES
     ════════════════════════════════════════════════════════════ */
  function rand(a, b) { return a + Math.random() * (b - a); }

  function glowCircle(ctx, x, y, r, innerCol, outerCol) {
    var g = ctx.createRadialGradient(x, y, 0, x, y, r);
    g.addColorStop(0, innerCol);
    g.addColorStop(1, outerCol);
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fillStyle = g;
    ctx.fill();
  }

  function fillLinear(ctx, W, H, stops) {
    var g = ctx.createLinearGradient(0, 0, 0, H);
    for (var i = 0; i < stops.length; i++) {
      g.addColorStop(stops[i][0], stops[i][1]);
    }
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);
  }

  /* ════════════════════════════════════════════════════════════
     SCENE: MORNING — Bình minh (05–11h)
     Deep indigo sky → warm amber horizon, soft rising sun,
     radial light rays, drifting golden dust motes
     ════════════════════════════════════════════════════════════ */
  function buildMorning() {
    var particles = [];

    function init(ctx, W, H) {
      particles = [];
      for (var i = 0; i < 38; i++) {
        particles.push({
          x: rand(0, W), y: rand(0, H),
          r: rand(1.0, 3.2),
          vy: rand(0.12, 0.45),
          vx: rand(-0.15, 0.15),
          phase: rand(0, Math.PI * 2),
          opacity: rand(0.25, 0.80)
        });
      }
    }

    function draw(ctx, W, H, t) {
      /* Sky */
      fillLinear(ctx, W, H, [
        [0.00, '#12183a'],
        [0.22, '#2e1640'],
        [0.48, '#7a2e2a'],
        [0.70, '#c85420'],
        [0.86, '#e8880e'],
        [1.00, '#f5c030']
      ]);

      /* Sun position */
      var sx = W * 0.24;
      var sy = H * 0.76;
      var sr = Math.min(W, H) * 0.088;

      /* Horizon atmospheric glow */
      var hg = ctx.createRadialGradient(sx, H, 0, sx, H, H * 0.72);
      hg.addColorStop(0,   'rgba(255,148,30,0.30)');
      hg.addColorStop(0.6, 'rgba(255,90,10,0.08)');
      hg.addColorStop(1,   'transparent');
      ctx.fillStyle = hg;
      ctx.fillRect(0, 0, W, H);

      /* Slow-rotating rays */
      ctx.save();
      ctx.translate(sx, sy);
      for (var i = 0; i < 14; i++) {
        var angle = (i / 14) * Math.PI * 2 + t * 0.030;
        var rayLen = sr * (4.0 + (i % 3) * 1.2);
        var alpha  = 0.042 + (i % 2) * 0.028;
        ctx.beginPath();
        ctx.moveTo(Math.cos(angle) * sr * 0.95, Math.sin(angle) * sr * 0.95);
        ctx.lineTo(Math.cos(angle) * rayLen, Math.sin(angle) * rayLen);
        ctx.strokeStyle = 'rgba(255,195,70,' + alpha + ')';
        ctx.lineWidth   = sr * 0.22;
        ctx.stroke();
      }
      ctx.restore();

      /* Sun glow layers */
      glowCircle(ctx, sx, sy, sr * 5.5, 'rgba(255,165,40,0.07)', 'transparent');
      glowCircle(ctx, sx, sy, sr * 2.8, 'rgba(255,195,60,0.20)', 'transparent');
      glowCircle(ctx, sx, sy, sr * 1.3, 'rgba(255,230,110,0.88)', 'transparent');
      glowCircle(ctx, sx, sy, sr * 0.70,'rgba(255,255,225,0.97)', 'transparent');

      /* Dust motes */
      for (var j = 0; j < particles.length; j++) {
        var p = particles[j];
        p.y -= p.vy;
        p.x += p.vx + Math.sin(t * 0.5 + p.phase) * 0.22;
        if (p.y < -6) { p.y = H + 6; p.x = rand(0, W); }
        var a = p.opacity * (0.45 + 0.55 * Math.sin(t * 1.1 + p.phase));
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(255,205,95,' + a + ')';
        ctx.fill();
      }
    }

    return { init: init, draw: draw };
  }

  /* ════════════════════════════════════════════════════════════
     SCENE: NOON — Buổi trưa (11–14h)
     Deep azure sky, crisp fast-rotating rays, soft cloud puffs,
     bright specular sparkles
     ════════════════════════════════════════════════════════════ */
  function buildNoon() {
    var clouds = [];
    var sparkles = [];

    function makeCloud(forcedX) {
      return {
        x: forcedX !== undefined ? forcedX : rand(-280, W + 280),
        y: rand(H * 0.06, H * 0.40),
        w: rand(110, 270),
        h: rand(36, 80),
        speed: rand(0.14, 0.38),
        opacity: rand(0.10, 0.24)
      };
    }

    var W_snap = 0, H_snap = 0;

    function init(ctx, W, H) {
      W_snap = W; H_snap = H;
      clouds = [];
      for (var i = 0; i < 5; i++) clouds.push(makeCloud());
      sparkles = [];
      for (var j = 0; j < 22; j++) {
        sparkles.push({
          x: rand(0, W), y: rand(0, H),
          r: rand(0.7, 1.9),
          phase: rand(0, Math.PI * 2),
          speed: rand(0.7, 2.2)
        });
      }
    }

    function drawCloud(ctx, c) {
      ctx.save();
      ctx.globalAlpha = c.opacity;
      ctx.fillStyle = '#e8f4ff';
      ctx.beginPath();
      ctx.ellipse(c.x,               c.y,             c.w * 0.50, c.h * 0.42, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.beginPath();
      ctx.ellipse(c.x - c.w * 0.21,  c.y + c.h * 0.12, c.w * 0.29, c.h * 0.34, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.beginPath();
      ctx.ellipse(c.x + c.w * 0.23,  c.y + c.h * 0.10, c.w * 0.31, c.h * 0.32, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }

    function draw(ctx, W, H, t) {
      W_snap = W; H_snap = H;

      fillLinear(ctx, W, H, [
        [0.00, '#092250'],
        [0.28, '#164585'],
        [0.58, '#2870b8'],
        [0.80, '#52a0d4'],
        [1.00, '#9ad0ee']
      ]);

      var sx = W * 0.50;
      var sy = H * 0.06;
      var sr = Math.min(W, H) * 0.060;

      /* Corona */
      glowCircle(ctx, sx, sy, sr * 8,   'rgba(180,225,255,0.05)', 'transparent');
      glowCircle(ctx, sx, sy, sr * 3.2, 'rgba(255,255,220,0.15)', 'transparent');

      /* Short crisp rays — fast rotation */
      ctx.save();
      ctx.translate(sx, sy);
      for (var i = 0; i < 18; i++) {
        var angle = (i / 18) * Math.PI * 2 + t * 0.14;
        ctx.beginPath();
        ctx.moveTo(Math.cos(angle) * sr * 1.15, Math.sin(angle) * sr * 1.15);
        ctx.lineTo(Math.cos(angle) * sr * 3.0,  Math.sin(angle) * sr * 3.0);
        ctx.strokeStyle = 'rgba(255,255,200,0.16)';
        ctx.lineWidth = 1.8;
        ctx.stroke();
      }
      ctx.restore();

      /* Sun */
      glowCircle(ctx, sx, sy, sr * 1.6, 'rgba(255,255,210,0.82)', 'transparent');
      glowCircle(ctx, sx, sy, sr,        'rgba(255,255,250,1.00)', 'transparent');

      /* Clouds */
      for (var c = 0; c < clouds.length; c++) {
        clouds[c].x += clouds[c].speed;
        if (clouds[c].x > W + 300) {
          clouds[c].x = -300;
          clouds[c].y = rand(H * 0.06, H * 0.40);
        }
        drawCloud(ctx, clouds[c]);
      }

      /* Sparkles */
      for (var s = 0; s < sparkles.length; s++) {
        var sp = sparkles[s];
        var a = 0.38 + 0.62 * Math.abs(Math.sin(t * sp.speed + sp.phase));
        ctx.beginPath();
        ctx.arc(sp.x, sp.y, sp.r * a, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(190,230,255,' + (a * 0.45) + ')';
        ctx.fill();
      }
    }

    return { init: init, draw: draw };
  }

  /* ════════════════════════════════════════════════════════════
     SCENE: AFTERNOON — Xế chiều (14–19h)
     Amber-terracotta sky, large low sun, diagonal light bands,
     drifting warm motes
     ════════════════════════════════════════════════════════════ */
  function buildAfternoon() {
    var motes  = [];
    var bands  = [];

    function init(ctx, W, H) {
      motes = [];
      for (var i = 0; i < 30; i++) {
        motes.push({
          x: rand(0, W), y: rand(0, H),
          r: rand(1.2, 4.0),
          vy: rand(0.08, 0.32),
          vx: rand(-0.18, 0.18),
          phase: rand(0, Math.PI * 2),
          opacity: rand(0.18, 0.68)
        });
      }
      bands = [];
      for (var b = 0; b < 6; b++) {
        bands.push({
          offset: rand(-H, W),
          width:  rand(36, 110),
          alpha:  rand(0.028, 0.078),
          speed:  rand(0.07, 0.18)
        });
      }
    }

    function draw(ctx, W, H, t) {
      fillLinear(ctx, W, H, [
        [0.00, '#1a0800'],
        [0.20, '#5a1e00'],
        [0.44, '#9c3c0c'],
        [0.66, '#ce6010'],
        [0.84, '#e48c18'],
        [1.00, '#f0ae30']
      ]);

      var sx = W * 0.80;
      var sy = H * 0.66;
      var sr = Math.min(W, H) * 0.10;

      /* Warm horizon haze */
      var hz = ctx.createLinearGradient(0, H * 0.55, 0, H);
      hz.addColorStop(0, 'transparent');
      hz.addColorStop(1, 'rgba(230,100,14,0.16)');
      ctx.fillStyle = hz;
      ctx.fillRect(0, 0, W, H);

      /* Diagonal light bands */
      ctx.save();
      ctx.translate(W * 0.5, H * 0.5);
      ctx.rotate(-0.30);
      for (var b = 0; b < bands.length; b++) {
        var bd = bands[b];
        bd.offset += bd.speed;
        if (bd.offset > W * 1.6) bd.offset = -H * 0.6;
        ctx.fillStyle = 'rgba(255,195,75,' + bd.alpha + ')';
        ctx.fillRect(bd.offset, -H, bd.width, H * 2.8);
      }
      ctx.restore();

      /* Long slow rays */
      ctx.save();
      ctx.translate(sx, sy);
      for (var i = 0; i < 10; i++) {
        var angle = (i / 10) * Math.PI * 2 + t * 0.022;
        var len   = Math.max(W, H) * 2.2;
        ctx.beginPath();
        ctx.moveTo(Math.cos(angle) * sr * 0.95, Math.sin(angle) * sr * 0.95);
        ctx.lineTo(Math.cos(angle) * len,        Math.sin(angle) * len);
        ctx.strokeStyle = 'rgba(255,170,50,0.048)';
        ctx.lineWidth   = sr * 0.38;
        ctx.stroke();
      }
      ctx.restore();

            /* Sun */
      glowCircle(ctx, sx, sy, sr * 5.8, 'rgba(255,130,20,0.09)', 'transparent');
      glowCircle(ctx, sx, sy, sr * 3.0, 'rgba(255,170,40,0.20)', 'transparent');
      glowCircle(ctx, sx, sy, sr * 1.4, 'rgba(255,215,90,0.86)', 'transparent');
      glowCircle(ctx, sx, sy, sr * 0.78,'rgba(255,252,210,0.96)', 'transparent');
      // rebuild glow without canvas ref confusion:
      glowCircle(ctx, sx, sy, sr * 1.4, 'rgba(255,215,90,0.86)', 'transparent');
      glowCircle(ctx, sx, sy, sr * 0.78,'rgba(255,252,210,0.96)', 'transparent');

      /* Floating motes */
      for (var m = 0; m < motes.length; m++) {
        var p = motes[m];
        p.y -= p.vy;
        p.x += p.vx + Math.sin(t * 0.38 + p.phase) * 0.20;
        if (p.y < -8) { p.y = H + 8; p.x = rand(0, W); }
        var a = p.opacity * (0.44 + 0.56 * Math.sin(t * 0.85 + p.phase));
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(255,188,70,' + a + ')';
        ctx.fill();
      }
    }

    return { init: init, draw: draw };
  }

  /* ════════════════════════════════════════════════════════════
     SCENE: EVENING — Đêm (19–05h)
     Deep navy sky, twinkling stars with cross-sparkle,
     crescent moon + halo, slow aurora bands, rare shooting stars
     ════════════════════════════════════════════════════════════ */
  function buildEvening() {
    var stars        = [];
    var shooters     = [];
    var shootTimer   = 0;

    function spawnShooter(W, H) {
      shooters.push({
        x:     rand(W * 0.08, W * 0.88),
        y:     rand(H * 0.02, H * 0.28),
        len:   rand(55, 145),
        speed: rand(5.5, 11),
        angle: 0.22,
        life:  1.0,
        decay: rand(0.014, 0.030)
      });
    }

    function init(ctx, W, H) {
      stars = [];
      for (var i = 0; i < 92; i++) {
        stars.push({
          x: rand(0, W),
          y: rand(0, H * 0.90),
          r: rand(0.45, 2.0),
          phase: rand(0, Math.PI * 2),
          speed: rand(0.38, 1.85),
          base:  rand(0.32, 0.92)
        });
      }
      shooters = [];
    }

    function drawAurora(ctx, W, H, t) {
      var bands = [
        { color: 'rgba(24,200,140,', yFrac: 0.055, amp: 0.022, freq: 0.0055, speed: 0.28 },
        { color: 'rgba(30,150,220,', yFrac: 0.095, amp: 0.018, freq: 0.0070, speed: 0.40 },
        { color: 'rgba(72,90,240,',  yFrac: 0.130, amp: 0.015, freq: 0.0090, speed: 0.55 }
      ];
      for (var b = 0; b < bands.length; b++) {
        var band = bands[b];
        var yBase = H * band.yFrac;
        var amp   = H * band.amp;
        ctx.beginPath();
        ctx.moveTo(0, yBase);
        for (var x = 0; x <= W; x += 5) {
          var y = yBase + Math.sin(x * band.freq + t * band.speed + b * 2.0) * amp;
          ctx.lineTo(x, y);
        }
        ctx.lineTo(W, 0);
        ctx.lineTo(0, 0);
        ctx.closePath();
        var alpha = 0.048 + 0.036 * Math.sin(t * 0.42 + b * 1.3);
        ctx.fillStyle = band.color + alpha + ')';
        ctx.fill();
      }
    }

    function draw(ctx, W, H, t) {
      fillLinear(ctx, W, H, [
        [0.00, '#030710'],
        [0.30, '#060c1c'],
        [0.60, '#09112a'],
        [0.85, '#0c1632'],
        [1.00, '#0f1a3c']
      ]);

      /* Aurora */
      drawAurora(ctx, W, H, t);

      /* Moon */
      var mx = W * 0.76;
      var my = H * 0.19;
      var mr = Math.min(W, H) * 0.052;

      glowCircle(ctx, mx, my, mr * 4.8, 'rgba(190,215,255,0.048)', 'transparent');
      glowCircle(ctx, mx, my, mr * 2.4, 'rgba(215,232,255,0.11)',  'transparent');

      /* Moon body */
      ctx.beginPath();
      ctx.arc(mx, my, mr, 0, Math.PI * 2);
      ctx.fillStyle = '#dce8ff';
      ctx.fill();

      /* Crescent cut-out */
      ctx.save();
      ctx.beginPath();
      ctx.arc(mx + mr * 0.40, my - mr * 0.05, mr * 0.85, 0, Math.PI * 2);
      ctx.fillStyle = '#09112a';
      ctx.fill();
      ctx.restore();

      /* Stars */
      for (var i = 0; i < stars.length; i++) {
        var s = stars[i];
        var a = s.base * (0.45 + 0.55 * Math.sin(t * s.speed + s.phase));
        /* Cross sparkle for larger stars */
        if (s.r > 1.35) {
          ctx.strokeStyle = 'rgba(200,220,255,' + (a * 0.55) + ')';
          ctx.lineWidth   = 0.55;
          var arm = s.r * 2.8;
          ctx.beginPath();
          ctx.moveTo(s.x - arm, s.y); ctx.lineTo(s.x + arm, s.y);
          ctx.moveTo(s.x, s.y - arm); ctx.lineTo(s.x, s.y + arm);
          ctx.stroke();
        }
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(215,232,255,' + a + ')';
        ctx.fill();
      }

      /* Shooting stars */
      shootTimer++;
      if (shootTimer > 240 && Math.random() < 0.010) {
        spawnShooter(W, H);
        shootTimer = 0;
      }
      for (var k = shooters.length - 1; k >= 0; k--) {
        var ss = shooters[k];
        ss.x   += Math.cos(ss.angle) * ss.speed;
        ss.y   += Math.sin(ss.angle) * ss.speed;
        ss.life -= ss.decay;
        var tx = ss.x - Math.cos(ss.angle) * ss.len;
        var ty = ss.y - Math.sin(ss.angle) * ss.len;
        var sg = ctx.createLinearGradient(tx, ty, ss.x, ss.y);
        sg.addColorStop(0, 'transparent');
        sg.addColorStop(1, 'rgba(255,255,255,' + ss.life + ')');
        ctx.beginPath();
        ctx.moveTo(tx, ty);
        ctx.lineTo(ss.x, ss.y);
        ctx.strokeStyle = sg;
        ctx.lineWidth   = 1.6;
        ctx.stroke();
        if (ss.life <= 0) shooters.splice(k, 1);
      }
    }

    return { init: init, draw: draw };
  }

  /* ════════════════════════════════════════════════════════════
     CANVAS ENGINE
     ════════════════════════════════════════════════════════════ */
  var canvas, ctx, W, H, raf, activeScene, tick;

  var SCENE_BUILDERS = {
    morning:   buildMorning,
    noon:      buildNoon,
    afternoon: buildAfternoon,
    evening:   buildEvening
  };

  function resize() {
    if (!canvas) return;
    var hero = canvas.parentElement;
    W = canvas.width  = hero.offsetWidth;
    H = canvas.height = hero.offsetHeight;
    if (activeScene) activeScene.init(ctx, W, H); // reinit on resize
  }

  function loop() {
    tick += 0.016;
    if (activeScene) activeScene.draw(ctx, W, H, tick);
    raf = requestAnimationFrame(loop);
  }

  function startCanvas(slot) {
    canvas = document.getElementById('heroCanvas');
    if (!canvas || !canvas.getContext) return;
    ctx  = canvas.getContext('2d');
    tick = 0;
    resize();
    window.addEventListener('resize', resize);
    activeScene = SCENE_BUILDERS[slot]();
    activeScene.init(ctx, W, H);
    if (raf) cancelAnimationFrame(raf);
    loop();
  }

  /* ════════════════════════════════════════════════════════════
     TIME HELPERS
     ════════════════════════════════════════════════════════════ */
  function getSlot(h) {
    if (h >= 5  && h < 11) return 'morning';
    if (h >= 11 && h < 14) return 'noon';
    if (h >= 14 && h < 19) return 'afternoon';
    return 'evening';
  }

  function getGreeting(h) {
    if (h >= 5  && h < 11) return { label: 'Buổi sáng',  title: 'Chào buổi sáng!' };
    if (h >= 11 && h < 14) return { label: 'Buổi trưa',  title: 'Chào buổi trưa!' };
    if (h >= 14 && h < 19) return { label: 'Buổi chiều', title: 'Chào buổi chiều!' };
    return { label: 'Buổi tối', title: 'Chào buổi tối!' };
  }

  function pad(n) { return String(n).padStart(2, '0'); }

  function applyGreeting() {
    var h = new Date().getHours();
    var g = getGreeting(h);
    var labelEl = document.getElementById('greetingLabel');
    var titleEl = document.getElementById('greetingTitle');
    if (labelEl) labelEl.textContent = g.label;
    if (titleEl) titleEl.textContent = g.title;
  }

  function tickClock() {
    var el = document.getElementById('heroClock');
    if (!el) return;
    function update() {
      var n = new Date();
      el.textContent = pad(n.getHours()) + ':' + pad(n.getMinutes()) + ':' + pad(n.getSeconds());
    }
    update();
    setInterval(update, 1000);
  }

  /* ════════════════════════════════════════════════════════════
     UI INTERACTIONS
     ════════════════════════════════════════════════════════════ */
  function initPasswordToggle() {
    var btn     = document.getElementById('togglePassword');
    var eyeIcon = document.getElementById('pwEyeIcon');
    var pwInput = btn ? btn.closest('.field-input-wrap').querySelector('input') : null;
    if (!btn || !pwInput || !eyeIcon) return;
    btn.addEventListener('click', function () {
      var hidden = pwInput.type === 'password';
      pwInput.type      = hidden ? 'text' : 'password';
      eyeIcon.className = hidden ? 'fa-regular fa-eye-slash' : 'fa-regular fa-eye';
      btn.classList.toggle('active', hidden);
      btn.setAttribute('aria-label', hidden ? 'Ẩn mật khẩu' : 'Hiện mật khẩu');
      pwInput.focus();
    });
  }

  function initSubmitLoading() {
    var form   = document.querySelector('.login-form');
    var btn    = document.getElementById('btnSubmit');
    var textEl = btn ? btn.querySelector('.btn-submit-text')    : null;
    var iconEl = btn ? btn.querySelector('.btn-submit-icon')    : null;
    var loadEl = btn ? btn.querySelector('.btn-submit-loading') : null;
    if (!form || !btn) return;
    form.addEventListener('submit', function () {
      btn.disabled = true;
      if (textEl) textEl.textContent = 'Đang xử lý...';
      if (iconEl) iconEl.hidden = true;
      if (loadEl) loadEl.hidden = false;
      setTimeout(function () {
        btn.disabled = false;
        if (textEl) textEl.textContent = 'Đăng nhập';
        if (iconEl) iconEl.hidden = false;
        if (loadEl) loadEl.hidden = true;
      }, 8000);
    });
  }

  /* ════════════════════════════════════════════════════════════
     BOOT
     ════════════════════════════════════════════════════════════ */
  document.addEventListener('DOMContentLoaded', function () {
    var slot = getSlot(new Date().getHours());
    startCanvas(slot);
    applyGreeting();
    tickClock();
    initPasswordToggle();
    initSubmitLoading();
  });

}());