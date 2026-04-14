/**
 * edit_corporate_contract.js
 * Đặt tại: contract/static/contract/js/edit_corporate_contract.js
 *
 * Django context được truyền vào qua <div id="cc-contract-data" data-*>
 * trong template HTML — không dùng {{ }} trực tiếp trong JS.
 */

'use strict';

// ── Đọc Django context từ data-* attribute ──────────────────────────────────
// Lấy từ <div id="cc-contract-data" data-grand-total="..." ...> trong template
const _cfgEl = document.getElementById('cc-contract-data');
const _cfg = _cfgEl ? _cfgEl.dataset : {};

const ccData = {
  grandTotal:           parseFloat(_cfg.grandTotal)          || 0,
  maleCount:            parseFloat(_cfg.maleCount)           || 0,
  femaleSingleCount:    parseFloat(_cfg.femaleSingleCount)   || 0,
  femaleFamilyCount:    parseFloat(_cfg.femaleFamilyCount)   || 0,
  subtotalMale:         parseFloat(_cfg.subtotalMale)        || 0,
  subtotalFemaleSingle: parseFloat(_cfg.subtotalFemaleSingle)|| 0,
  subtotalFemaleFamily: parseFloat(_cfg.subtotalFemaleFamily)|| 0,
};

// ── State ───────────────────────────────────────────────────────────────────
let selectedGrand = ccData.grandTotal;
let isSubmittingEditContract = false;

// ── Helpers ─────────────────────────────────────────────────────────────────
let depositAmountManual = false;
let depositWordsManual = false;

function onlyDigits(value) {
  return String(value || '').replace(/[^\d]/g, '');
}

function parseMoneyInput(value) {
  const digits = onlyDigits(value);
  return digits ? parseInt(digits, 10) : 0;
}

function formatMoneyInput(value) {
  const n = parseMoneyInput(value);
  return n ? n.toLocaleString('vi-VN') : '';
}

function numberToVietnameseWords(num) {
  num = parseInt(num || 0, 10);
  if (!num) return '';

  const digits = ['không', 'một', 'hai', 'ba', 'bốn', 'năm', 'sáu', 'bảy', 'tám', 'chín'];

  function readTriple(n, full) {
    const hundred = Math.floor(n / 100);
    const ten = Math.floor((n % 100) / 10);
    const unit = n % 10;
    const parts = [];

    if (full || hundred > 0) parts.push(digits[hundred] + ' trăm');

    if (ten > 1) {
      parts.push(digits[ten] + ' mươi');
      if (unit === 1) parts.push('mốt');
      else if (unit === 4) parts.push('tư');
      else if (unit === 5) parts.push('lăm');
      else if (unit > 0) parts.push(digits[unit]);
    } else if (ten === 1) {
      parts.push('mười');
      if (unit === 5) parts.push('lăm');
      else if (unit > 0) parts.push(digits[unit]);
    } else if (unit > 0) {
      if (hundred > 0 || full) parts.push('lẻ');
      parts.push(digits[unit]);
    }

    return parts.join(' ').trim();
  }

  const units = ['', 'nghìn', 'triệu', 'tỷ', 'nghìn tỷ', 'triệu tỷ'];
  const groups = [];
  while (num > 0) {
    groups.push(num % 1000);
    num = Math.floor(num / 1000);
  }

  const parts = [];
  for (let i = groups.length - 1; i >= 0; i--) {
    const group = groups[i];
    if (!group) continue;
    const full = i < groups.length - 1 && group < 100;
    const chunk = readTriple(group, full);
    if (chunk) parts.push((chunk + ' ' + (units[i] || '')).trim());
  }

  let text = parts.join(' ').replace(/\s+/g, ' ').trim();
  if (!text) return '';
  text = text.charAt(0).toUpperCase() + text.slice(1);
  return text + ' đồng';
}

function syncDepositWordsFromAmount() {
  const wordsInput = document.getElementById('deposit_amount_words_input');
  const amountInput = document.getElementById('deposit_amount_input');
  if (!wordsInput || !amountInput) return;
  if (depositWordsManual) return;

  const amount = parseMoneyInput(amountInput.value);
  wordsInput.value = amount > 0 ? numberToVietnameseWords(amount) : '';
}

function handleDepositAmountInput() {
  const amountInput = document.getElementById('deposit_amount_input');
  if (!amountInput) return;

  depositAmountManual = true;
  amountInput.value = formatMoneyInput(amountInput.value);
  try {
    amountInput.setSelectionRange(amountInput.value.length, amountInput.value.length);
  } catch (e) {}

  syncDepositWordsFromAmount();
}
function fmtVnd(n) {
  return Math.round(n || 0).toLocaleString('vi-VN');
}

function clearFieldErrors() {
  document.querySelectorAll('.cc-field-error').forEach(el => {
    el.textContent = '';
  });
  document.querySelectorAll('.cc-input, .cc-select, .cc-textarea').forEach(el => {
    el.classList.remove('is-invalid');
  });
}

function markFieldError(fieldName, messages) {
  const message = Array.isArray(messages) ? messages[0] : messages;
  if (!message) return;

  const errorBox = document.querySelector(`.cc-field-error[data-error-for="${CSS.escape(fieldName)}"]`);
  if (errorBox) {
    errorBox.textContent = message;
  }

  let input = document.querySelector(`[name="${fieldName}"]`);
  if (!input) {
    const escaped = fieldName.replace(/"/g, '\\"');
    input = document.querySelector(`[name="${escaped}"]`);
  }
  if (!input && fieldName === 'company_id') {
    input = document.getElementById('company_name_input');
  }
  if (input) {
    input.classList.add('is-invalid');
  }
}

function applyFieldErrors(fieldErrors) {
  if (!fieldErrors) return;

  Object.entries(fieldErrors).forEach(([fieldName, messages]) => {
    markFieldError(fieldName, messages);
  });

  const firstInvalid = document.querySelector('.is-invalid');
  if (firstInvalid) {
    firstInvalid.scrollIntoView({ behavior: 'smooth', block: 'center' });
    try { firstInvalid.focus(); } catch (e) { /* ignore */ }
  }
}

function setSubmittingState(isBusy) {
  const submitBtn = document.getElementById('submitContractBtn');
  const backBtn   = document.getElementById('backToPreviewBtn');
  const overlay   = document.getElementById('ccSubmitOverlay');

  if (submitBtn) {
    const defaultHtml = submitBtn.dataset.defaultHtml || 'Lưu cập nhật';
    const loadingHtml = submitBtn.dataset.loadingHtml || 'Đang lưu...';

    submitBtn.disabled = isBusy;
    submitBtn.innerHTML = isBusy ? loadingHtml : defaultHtml;
    submitBtn.setAttribute('aria-busy', isBusy ? 'true' : 'false');
  }

  if (backBtn) {
    if (isBusy) {
      backBtn.classList.add('disabled');
      backBtn.setAttribute('aria-disabled', 'true');
      backBtn.dataset.originalHref = backBtn.getAttribute('href') || '';
      backBtn.removeAttribute('href');
    } else {
      backBtn.classList.remove('disabled');
      backBtn.setAttribute('aria-disabled', 'false');
      if (backBtn.dataset.originalHref) {
        backBtn.setAttribute('href', backBtn.dataset.originalHref);
      }
    }
  }

  if (overlay) {
    overlay.style.display = isBusy ? 'flex' : 'none';
    overlay.setAttribute('aria-hidden', isBusy ? 'false' : 'true');
  }

  document.body.classList.toggle('cc-busy', isBusy);
}

// ── Tính toán đặt cọc ────────────────────────────────────────────────────────
function updateDepositCalc() {
  const grand = ccData.grandTotal;
  const pct = parseFloat(document.getElementById('deposit_pct_input').value) || 0;
  const autoDeposit = Math.round(grand * pct / 100);

  document.getElementById('js-grand-total').textContent = fmtVnd(grand) + ' ₫';

  const amountInput = document.getElementById('deposit_amount_input');

  if (grand > 0) {
    document.getElementById('deposit_note').style.display = 'block';
    document.getElementById('grand_display').textContent = fmtVnd(grand);
    document.getElementById('pct_display').textContent = pct;
    document.getElementById('deposit_auto_display').textContent = fmtVnd(autoDeposit);

    if (amountInput && !depositAmountManual && !parseMoneyInput(amountInput.value)) {
      amountInput.value = autoDeposit ? autoDeposit.toLocaleString('vi-VN') : '';
      syncDepositWordsFromAmount();
    }
  } else {
    document.getElementById('deposit_note').style.display = 'none';
  }
}

// ── Thêm dòng lịch lấy máu ──────────────────────────────────────────────────
function addBloodRow() {
  const container = document.getElementById('blood-rows');
  const firstRow  = container.querySelector('.blood-row');
  if (!firstRow) return;

  const row = firstRow.cloneNode(true);

  row.querySelectorAll('input').forEach(inp => {
    inp.value = inp.type === 'number' ? 0 : '';
    inp.classList.remove('is-invalid');
  });
  row.querySelectorAll('.cc-field-error').forEach(el => {
    el.textContent = '';
  });

  container.appendChild(row);
}

// ── Khởi tạo sau khi DOM sẵn sàng ──────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
  const form      = document.getElementById('ccEditForm');
  const errorBox  = document.getElementById('contract_form_error');

  if (!form) return;

  // Ngăn submit bằng Enter khi đang gửi
  form.addEventListener('keydown', function (e) {
    if (isSubmittingEditContract && e.key === 'Enter') {
      e.preventDefault();
    }
  });

  // Xoá lỗi field khi người dùng nhập / thay đổi
  function clearFieldOnInteract(e) {
    const target = e.target;
    if (!target) return;

    target.classList.remove('is-invalid');

    const fieldName = target.name;
    if (!fieldName) return;

    const errorEl = document.querySelector(
      `.cc-field-error[data-error-for="${CSS.escape(fieldName)}"]`
    );
    if (errorEl) errorEl.textContent = '';
  }

  form.addEventListener('input',  clearFieldOnInteract);
  form.addEventListener('change', clearFieldOnInteract);

  // Submit bằng fetch (AJAX)
  form.addEventListener('submit', async function (e) {
    e.preventDefault();

    if (isSubmittingEditContract) return;

    isSubmittingEditContract = true;
    setSubmittingState(true);

    if (errorBox) {
      errorBox.style.display = 'none';
      errorBox.textContent   = '';
    }
    clearFieldErrors();

    try {
      const response = await fetch(form.action, {
        method: 'POST',
        body: new FormData(form),
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'same-origin',
      });

      let data = {};
      try {
        data = await response.json();
      } catch {
        data = {
          ok: false,
          message: 'Phản hồi từ máy chủ không hợp lệ.',
          field_errors: {},
        };
      }

      if (data.ok) {
        window.location.href = data.redirect_url;
        return;
      }

      if (data.field_errors && Object.keys(data.field_errors).length > 0) {
        applyFieldErrors(data.field_errors);
      }

      if (
        errorBox &&
        (
          !data.field_errors ||
          Object.keys(data.field_errors).length === 0 ||
          data.field_errors.__all__
        )
      ) {
        errorBox.textContent = data.message || 'Có lỗi xảy ra.';
        errorBox.style.display = 'block';
        errorBox.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    } catch {
      if (errorBox) {
        errorBox.textContent = 'Không thể gửi yêu cầu. Vui lòng thử lại.';
        errorBox.style.display = 'block';
        errorBox.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    } finally {
      isSubmittingEditContract = false;
      setSubmittingState(false);
    }
  });

  const depositWordsInput = document.getElementById('deposit_amount_words_input');
  if (depositWordsInput) {
    depositWordsInput.addEventListener('input', function () {
      depositWordsManual = !!this.value.trim();
    });
  }

  const depositAmountInput = document.getElementById('deposit_amount_input');
  if (depositAmountInput) {
    depositAmountInput.value = formatMoneyInput(depositAmountInput.value);
    if (parseMoneyInput(depositAmountInput.value) > 0) {
      depositAmountManual = true;
    }
  }

  // Chặn navigation link khi đang submit
  document.addEventListener('click', function (e) {
    if (!isSubmittingEditContract) return;
    const link = e.target.closest('a');
    if (link) e.preventDefault();
  }, true);



  // Chạy lần đầu để hiển thị tổng tiền
  updateDepositCalc();
  //
  syncDepositWordsFromAmount();
});