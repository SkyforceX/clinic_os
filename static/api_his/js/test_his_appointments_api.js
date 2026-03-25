(function() {
  const $ = id => document.getElementById(id);

  function buildQuery() {
    const params = new URLSearchParams();
    const fields = ["date","date_from","date_to","company_id","page","page_size","updated_since"];
    fields.forEach(k => {
      const v = $(k)?.value?.trim();
      if (v) params.append(k, v);
    });
    return params.toString() ? "?" + params.toString() : "";
  }

  function toCurl(url, token) {
    const hdr = token ? ` -H "Authorization: Token ${token}"` : "";
    return `curl${hdr} "${url}"`;
  }

  // Toggle hiển/ẩn token
  document.querySelector(".btn-toggle-token")?.addEventListener("click", () => {
    const inp = $("token");
    inp.type = (inp.type === "password") ? "text" : "password";
  });

  $("btnSend")?.addEventListener("click", async () => {
    const base = $("endpoint").value || "/api/v1/his/appointments/";
    const token = $("token").value.trim();
    const url = base + buildQuery();

    const headers = {};
    if (token) headers["Authorization"] = `Token ${token}`;

    // Tuỳ template của bạn: hiển thị vào <pre id="result"> và <pre id="curl">
    const result = document.getElementById("result");
    const curl = document.getElementById("curl");
    if (curl) curl.textContent = toCurl(url, token);
    if (result) result.textContent = "Đang gửi...";

    try {
      const res = await fetch(url, { headers, credentials: "include" });
      const data = await res.json();
      if (result) result.textContent = JSON.stringify(data, null, 2);
    } catch (e) {
      if (result) result.textContent = "Lỗi: " + e.message;
    }
  });

  $("btnClear")?.addEventListener("click", () => {
    ["date","date_from","date_to","company_id","page","page_size","updated_since"].forEach(id => {
      const el = document.getElementById(id); if (el) el.value = "";
    });
    const result = document.getElementById("result");
    const curl = document.getElementById("curl");
    if (result) result.textContent = "(chưa có dữ liệu)";
    if (curl) curl.textContent = "";
  });
})();
