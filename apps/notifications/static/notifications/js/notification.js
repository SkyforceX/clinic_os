/**
 * clinic_os — Notification Client
 * ─────────────────────────────────
 * - Kết nối WebSocket tới /ws/notifications/
 * - Nhận JSON từ server → hiển thị Browser Notification popup + in-app toast
 * - Cập nhật bell badge (số thông báo chưa đọc) realtime
 * - Tự reconnect khi mất kết nối (exponential backoff)
 *
 * Yêu cầu: base_admin.html phải có
 *   <span id="notif-badge" class="notif-badge" style="display:none">0</span>
 *   <div id="notif-toast-container"></div>
 */

(function () {
  "use strict";

  // ── Config ────────────────────────────────────────────────────────────────
  const WS_PATH    = "/ws/notifications/";
  const TOAST_DURATION = 6000;   // ms tự ẩn toast
  const RECONNECT_BASE = 2000;   // ms delay reconnect đầu tiên
  const RECONNECT_MAX  = 30000;  // ms delay reconnect tối đa

  // ── State ─────────────────────────────────────────────────────────────────
  let ws            = null;
  let reconnectDelay = RECONNECT_BASE;
  let unreadCount    = 0;

  // ── Bell badge ────────────────────────────────────────────────────────────
  const badge = document.getElementById("notif-badge");

  function updateBadge(delta) {
    unreadCount = Math.max(0, unreadCount + delta);
    if (!badge) return;
    if (unreadCount > 0) {
      badge.textContent = unreadCount > 99 ? "99+" : unreadCount;
      badge.style.display = "inline-flex";
    } else {
      badge.style.display = "none";
    }
  }

  // Khởi tạo badge từ giá trị server inject qua window.__NOTIF_UNREAD_COUNT__
  function initBadge() {
    if (!badge) return;
    const initial = parseInt(window.__NOTIF_UNREAD_COUNT__ || "0", 10);
    unreadCount = initial;
    updateBadge(0);
  }

  // ── Browser Notification API ──────────────────────────────────────────────
  function requestPermission() {
    if (!("Notification" in window)) return;
    if (Notification.permission === "default") {
      // Xin quyền khi user tương tác lần đầu (không popup ngay khi load)
      document.addEventListener(
        "click",
        function askOnce() {
          Notification.requestPermission();
          document.removeEventListener("click", askOnce);
        },
        { once: true }
      );
    }
  }

  function showBrowserNotification(notif) {
    if (!("Notification" in window)) return;
    if (Notification.permission !== "granted") return;

    const n = new Notification(notif.title, {
      body: notif.body || "",
      icon: "/static/notifications/img/icon-192.png",
      tag:  "clinicos-" + notif.id,   // tag giống nhau → ghi đè thay vì chồng
      requireInteraction: notif.level === "danger",
    });

    n.onclick = function () {
      window.focus();
      if (notif.url) window.location.href = notif.url;
      n.close();
      markRead([notif.id]);
    };
  }

  // ── In-app Toast ──────────────────────────────────────────────────────────
  const toastContainer = document.getElementById("notif-toast-container");

  const LEVEL_STYLES = {
    success: { border: "#1d9e75", icon: "✅" },
    danger:  { border: "#e24b4a", icon: "❌" },
    warning: { border: "#ba7517", icon: "⚠️" },
    info:    { border: "#378add", icon: "ℹ️" },
  };

  function showToast(notif) {
    if (!toastContainer) return;

    const style = LEVEL_STYLES[notif.level] || LEVEL_STYLES.info;
    const el    = document.createElement("div");
    el.className  = "clinicos-toast";
    el.dataset.id = notif.id;
    el.style.cssText = `
      border-left: 4px solid ${style.border};
      background: var(--color-background-primary, #fff);
      color: var(--color-text-primary, #222);
      border-radius: 8px;
      box-shadow: 0 4px 16px rgba(0,0,0,.12);
      padding: 12px 16px;
      margin-bottom: 10px;
      min-width: 280px;
      max-width: 380px;
      cursor: pointer;
      animation: slideInRight .25s ease;
      position: relative;
    `;
    el.innerHTML = `
      <div style="display:flex;align-items:flex-start;gap:8px">
        <span style="font-size:16px;line-height:1.4">${style.icon}</span>
        <div style="flex:1;min-width:0">
          <div style="font-weight:500;font-size:.88rem;margin-bottom:2px">${escHtml(notif.title)}</div>
          ${notif.body ? `<div style="font-size:.8rem;opacity:.75;white-space:pre-line">${escHtml(notif.body)}</div>` : ""}
          <div style="font-size:.72rem;opacity:.5;margin-top:4px">${notif.created_at}</div>
        </div>
        <button onclick="this.closest('.clinicos-toast').remove()" style="
          background:none;border:none;cursor:pointer;opacity:.4;font-size:16px;
          padding:0;line-height:1;color:inherit">×</button>
      </div>
    `;

    // Click vào toast → navigate + mark read
    el.addEventListener("click", function (e) {
      if (e.target.tagName === "BUTTON") return;
      markRead([notif.id]);
      if (notif.url) window.location.href = notif.url;
    });

    toastContainer.prepend(el);

    // Tự ẩn sau TOAST_DURATION
    setTimeout(() => {
      el.style.animation = "fadeOut .3s ease forwards";
      el.addEventListener("animationend", () => el.remove(), { once: true });
    }, TOAST_DURATION);
  }

  function escHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  // ── Mark read (gửi qua WebSocket, không cần HTTP) ─────────────────────────
  function markRead(ids) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({ type: "mark_read", ids }));
    updateBadge(-ids.length);
  }

  // ── WebSocket ─────────────────────────────────────────────────────────────
  function buildWsUrl() {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${location.host}${WS_PATH}`;
  }

  function onMessage(event) {
    let data;
    try { data = JSON.parse(event.data); }
    catch { return; }

    if (data.type !== "notification") return;

    const notif = data.notification;
    updateBadge(+1);
    showToast(notif);
    showBrowserNotification(notif);
  }

  function connect() {
    ws = new WebSocket(buildWsUrl());

    ws.onopen = function () {
      reconnectDelay = RECONNECT_BASE; // reset backoff khi kết nối thành công
    };

    ws.onmessage = onMessage;

    ws.onclose = function (e) {
      // 4003 = unauthorized (consumer đóng chủ động), không reconnect
      if (e.code === 4003) return;
      scheduleReconnect();
    };

    ws.onerror = function () {
      ws.close();
    };
  }

  function scheduleReconnect() {
    setTimeout(function () {
      connect();
      reconnectDelay = Math.min(reconnectDelay * 2, RECONNECT_MAX);
    }, reconnectDelay);
  }

  // ── Init ──────────────────────────────────────────────────────────────────
  function init() {
    initBadge();
    requestPermission();
    connect();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
