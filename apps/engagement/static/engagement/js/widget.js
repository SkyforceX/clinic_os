/**
 * ClinicOS WebChat Widget v1.0
 * Nhúng vào website bằng: <script src="...widget.js" data-key="YOUR_KEY" async></script>
 *
 * Giao tiếp với backend qua:
 *   POST /engagement/webhook/webchat/{key}/init/  → lấy session_id
 *   POST /engagement/webhook/webchat/{key}/send/  → gửi tin nhắn
 *   GET  /engagement/webhook/webchat/{key}/poll/?session_id=...&after_id=... → nhận tin mới
 */
(function() {
  const script  = document.currentScript || document.querySelector('script[data-key]');
  const key     = script ? script.getAttribute('data-key') : null;
  if (!key) return console.warn('[ClinicOS WebChat] data-key missing');

  // ── Detect base URL from script src ──────────────────────────────────────
  const scriptSrc = script.src || '';
  const baseUrl   = scriptSrc.replace(/\/static\/.*$/, '');
  const apiBase   = `${baseUrl}/engagement/webhook/webchat/${key}`;

  // ── State ─────────────────────────────────────────────────────────────────
  let SESSION_ID  = localStorage.getItem(`cw_sid_${key}`) || '';
  let last_msg_id = parseInt(localStorage.getItem(`cw_mid_${key}`) || '0');
  let config      = {};
  let open        = false;
  let pollTimer   = null;

  // ── CSS ───────────────────────────────────────────────────────────────────
  const style = document.createElement('style');
  style.textContent = `
    #cw-wrap { position:fixed; bottom:20px; right:20px; z-index:99999; font-family:'Segoe UI',system-ui,sans-serif; }
    #cw-btn  { width:52px;height:52px;border-radius:50%;border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:22px;box-shadow:0 4px 18px rgba(0,0,0,.22);transition:transform .2s; }
    #cw-btn:hover { transform:scale(1.08); }
    #cw-badge { position:absolute;top:-4px;right:-4px;background:#e74c3c;color:#fff;border-radius:50%;width:18px;height:18px;font-size:11px;font-weight:700;display:flex;align-items:center;justify-content:center;border:2px solid #fff;display:none; }
    #cw-box  { position:absolute;bottom:64px;right:0;width:320px;border-radius:14px;box-shadow:0 8px 32px rgba(0,0,0,.18);overflow:hidden;display:none;flex-direction:column;background:#fff;border:1px solid #dee2e6;max-height:480px; }
    #cw-head { padding:12px 14px;display:flex;align-items:center;gap:8px;color:#fff; }
    #cw-head-name { font-weight:600;font-size:.9rem;flex:1 }
    #cw-close { background:none;border:none;color:#fff;font-size:18px;cursor:pointer;line-height:1; }
    #cw-msgs { flex:1;overflow-y:auto;padding:10px 12px;background:#f8f9fa;display:flex;flex-direction:column;gap:6px;min-height:200px;max-height:320px; }
    .cw-msg  { max-width:80%;padding:8px 11px;border-radius:12px;font-size:.82rem;line-height:1.45;word-break:break-word; }
    .cw-msg.in  { background:#fff;border:1px solid #e9ecef;color:#212529;border-bottom-left-radius:3px;align-self:flex-start; }
    .cw-msg.out { background:var(--cw-color,#1a5276);color:#fff;border-bottom-right-radius:3px;align-self:flex-end; }
    .cw-time { font-size:.62rem;color:#adb5bd;margin-top:1px; }
    #cw-input-wrap { padding:8px 10px;border-top:1px solid #dee2e6;display:flex;gap:6px;background:#fff; }
    #cw-input { flex:1;border:1px solid #dee2e6;border-radius:8px;padding:7px 10px;font-size:.82rem;outline:none;resize:none; }
    #cw-input:focus { border-color:var(--cw-color,#1a5276); }
    #cw-send { border:none;border-radius:8px;padding:6px 12px;cursor:pointer;font-size:.8rem;color:#fff;background:var(--cw-color,#1a5276); }
  `;
  document.head.appendChild(style);

  // ── DOM ───────────────────────────────────────────────────────────────────
  const wrap  = document.createElement('div'); wrap.id  = 'cw-wrap';
  const btn   = document.createElement('button'); btn.id = 'cw-btn';
  const badge = document.createElement('span');   badge.id = 'cw-badge'; badge.textContent = '';
  btn.appendChild(badge); btn.textContent = '💬';

  const box = document.createElement('div'); box.id = 'cw-box';
  box.innerHTML = `
    <div id="cw-head">
      <img id="cw-av" src="" style="width:30px;height:30px;border-radius:50%;background:#fff;display:none">
      <span id="cw-head-name">Chat</span>
      <button id="cw-close">✕</button>
    </div>
    <div id="cw-msgs"></div>
    <div id="cw-input-wrap">
      <textarea id="cw-input" rows="1" placeholder="Nhập tin nhắn..."></textarea>
      <button id="cw-send">Gửi</button>
    </div>`;

  wrap.appendChild(box);
  wrap.appendChild(btn);
  document.body.appendChild(wrap);

  // ── Init ─────────────────────────────────────────────────────────────────
  async function initSession() {
    try {
      const res  = await fetch(`${apiBase}/init/`, { method: 'POST', headers: {'Content-Type':'application/json'} });
      const data = await res.json();
      if (data.error) return;
      config = data;
      if (!SESSION_ID) {
        SESSION_ID = data.session_id;
        localStorage.setItem(`cw_sid_${key}`, SESSION_ID);
      }
      applyConfig();
      addMsg(data.greeting, 'in');
    } catch(e) {}
  }

  function applyConfig() {
    const color = config.theme_color || '#1a5276';
    document.documentElement.style.setProperty('--cw-color', color);
    btn.style.background = color;
    document.getElementById('cw-head').style.background = color;
    document.getElementById('cw-head-name').textContent = config.channel_name || 'Chat';
    const av = document.getElementById('cw-av');
    if (config.channel_avatar) { av.src = config.channel_avatar; av.style.display = 'block'; }
  }

  // ── Messages ──────────────────────────────────────────────────────────────
  function addMsg(text, dir) {
    const msgs = document.getElementById('cw-msgs');
    const now  = new Date().toLocaleTimeString('vi-VN', {hour:'2-digit',minute:'2-digit'});
    const row  = document.createElement('div');
    row.innerHTML = `<div class="cw-msg ${dir}">${text.replace(/\n/g,'<br>')}</div><div class="cw-time" style="text-align:${dir==='out'?'right':'left'}">${now}</div>`;
    msgs.appendChild(row);
    msgs.scrollTop = msgs.scrollHeight;
  }

  async function sendMsg() {
    const input = document.getElementById('cw-input');
    const text  = input.value.trim();
    if (!text || !SESSION_ID) return;
    input.value = '';
    addMsg(text, 'out');
    try {
      await fetch(`${apiBase}/send/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: SESSION_ID, text }),
      });
    } catch(e) {}
  }

  async function poll() {
    if (!SESSION_ID || !open) return;
    try {
      const res  = await fetch(`${apiBase}/poll/?session_id=${SESSION_ID}&after_id=${last_msg_id}`);
      const data = await res.json();
      for (const msg of (data.messages || [])) {
        if (msg.direction === 'OUT' && msg.id > last_msg_id) {
          addMsg(msg.content, 'in');
          last_msg_id = msg.id;
          localStorage.setItem(`cw_mid_${key}`, last_msg_id);
          if (!open) { badge.style.display = 'flex'; badge.textContent = parseInt(badge.textContent || 0) + 1; }
        }
      }
    } catch(e) {}
  }

  // ── Toggle open/close ─────────────────────────────────────────────────────
  function toggleBox() {
    open = !open;
    box.style.display  = open ? 'flex' : 'none';
    btn.textContent    = open ? '✕' : '💬';
    badge.style.display = 'none'; badge.textContent = '';
    if (open && !SESSION_ID) initSession();
    if (open) clearInterval(pollTimer), pollTimer = setInterval(poll, 4000);
    else clearInterval(pollTimer);
  }

  btn.addEventListener('click', toggleBox);
  document.getElementById('cw-close').addEventListener('click', toggleBox);
  document.getElementById('cw-send').addEventListener('click', sendMsg);
  document.getElementById('cw-input').addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMsg(); }
  });

  // Pre-init if session exists
  if (SESSION_ID) initSession();
})();
