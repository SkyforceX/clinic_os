(function() {
  function $(id) {
    return document.getElementById(id);
  }

  function getCsrfToken() {
    const cookie = document.cookie
      .split(";")
      .map(function(row) { return row.trim(); })
      .find(function(row) { return row.startsWith("csrftoken="); });
    return cookie ? decodeURIComponent(cookie.split("=")[1]) : "";
  }

  // ── Local log table ──────────────────────────────────────────
  function renderLocalLog(rows) {
    const tbody = $("localLogBody");
    if (!tbody) return;

    if (!rows || rows.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" style="padding:14px 10px;color:#9fb0d8;text-align:center;">(Chưa có dữ liệu)</td></tr>';
      return;
    }

    tbody.innerHTML = rows.map(function(r) {
      return [
        '<tr style="border-bottom:1px solid rgba(255,255,255,.06);">',
        '<td style="padding:7px 10px;color:#34d399;white-space:nowrap;">' + (r.id || '') + '</td>',
        '<td style="padding:7px 10px;color:#6ea8fe;white-space:nowrap;">' + (r.appointment_id || '—') + '</td>',
        '<td style="padding:7px 10px;white-space:nowrap;">' + esc(r.ho_ten) + '</td>',
        '<td style="padding:7px 10px;white-space:nowrap;">' + esc(r.ma_benh_nhan) + '</td>',
        '<td style="padding:7px 10px;white-space:nowrap;">' + esc(r.ngay_bat_dau) + '</td>',
        '<td style="padding:7px 10px;max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="' + esc(r.noi_dung) + '">' + esc(r.noi_dung) + '</td>',
        '<td style="padding:7px 10px;color:#9fb0d8;white-space:nowrap;">' + esc(r.pushed_at) + '</td>',
        '</tr>',
      ].join('');
    }).join('');
  }

  function esc(str) {
    if (!str && str !== 0) return '—';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function buildResponsePreview(text) {
    return String(text || "").replace(/\s+/g, " ").trim().slice(0, 300);
  }

  async function parseApiResponse(response) {
    const contentType = response.headers.get("content-type") || "";
    const rawText = await response.text();
    let data = null;

    if (rawText && contentType.includes("application/json")) {
      try {
        data = JSON.parse(rawText);
      } catch (error) {
        throw new Error(
          "JSON khong hop le. HTTP " + response.status +
          ". Preview: " + buildResponsePreview(rawText)
        );
      }
    }

    if (!response.ok) {
      const message = data && data.error
        ? data.error
        : (
          "HTTP " + response.status +
          " | content-type: " + (contentType || "unknown") +
          " | preview: " + buildResponsePreview(rawText)
        );
      throw new Error(message);
    }

    if (data !== null) {
      return data;
    }

    throw new Error(
      "Endpoint tra ve " + (contentType || "unknown") +
      " thay vi JSON. HTTP " + response.status +
      ". Preview: " + buildResponsePreview(rawText)
    );
  }

  async function loadLocalLog() {
    const endpoint = $("logEndpoint");
    const errEl = $("localLogError");
    const tbody = $("localLogBody");
    if (!endpoint || !tbody) return;

    if (tbody) tbody.innerHTML = '<tr><td colspan="7" style="padding:14px 10px;color:#9fb0d8;text-align:center;">Đang tải...</td></tr>';
    if (errEl) errEl.style.display = "none";

    try {
      const res = await fetch(endpoint.textContent.trim(), {
        credentials: "same-origin",
        headers: {
          "Accept": "application/json",
          "X-Requested-With": "XMLHttpRequest",
        },
      });
      const data = await parseApiResponse(res);
      if (!data.ok) {
        if (errEl) { errEl.textContent = "Lỗi: " + (data.error || "Không rõ"); errEl.style.display = "block"; }
        if (tbody) tbody.innerHTML = '<tr><td colspan="7" style="padding:14px 10px;color:#ef4444;text-align:center;">Lỗi tải dữ liệu.</td></tr>';
        return;
      }
      renderLocalLog(data.rows);
    } catch (err) {
      if (errEl) { errEl.textContent = "Lỗi kết nối: " + err.message; errEl.style.display = "block"; }
      if (tbody) tbody.innerHTML = '<tr><td colspan="7" style="padding:14px 10px;color:#ef4444;text-align:center;">Lỗi kết nối.</td></tr>';
    }
  }

  // ── Push button ──────────────────────────────────────────────
  $("btnSendPush")?.addEventListener("click", async function() {
    const appointmentId = $("appointment_id")?.value?.trim();
    const result = $("pushResult");
    if (!appointmentId) {
      if (result) result.textContent = "Thiếu appointment_id.";
      return;
    }

    if (result) result.textContent = "Đang gửi...";
    try {
      const response = await fetch($("pushEndpoint").textContent.trim(), {
        method: "POST",
        headers: {
          "Accept": "application/json",
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
          "X-Requested-With": "XMLHttpRequest",
        },
        credentials: "same-origin",
        body: JSON.stringify({
          appointment_id: appointmentId,
          force: $("force_send")?.checked || false,
        }),
      });
      const data = await parseApiResponse(response);
      if (result) result.textContent = JSON.stringify(data, null, 2);
      // Reload log after push (success or fail)
      loadLocalLog();
    } catch (error) {
      if (result) result.textContent = "Lỗi: " + error.message;
    }
  });

  $("btnClearPush")?.addEventListener("click", function() {
    if ($("appointment_id")) $("appointment_id").value = "";
    if ($("force_send")) $("force_send").checked = false;
    if ($("pushResult")) $("pushResult").textContent = "(chưa có dữ liệu)";
  });

  $("btnRefreshLog")?.addEventListener("click", loadLocalLog);

  // Auto-load log on page ready
  loadLocalLog();
})();
