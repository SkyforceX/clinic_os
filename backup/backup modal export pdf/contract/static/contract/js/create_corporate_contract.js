let selectedGrand = 0;
let isSubmittingCreateContract = false;
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
  const caretToEnd = amountInput.selectionStart;
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
    try { firstInvalid.focus(); } catch (e) {}
  }
}

function setSubmittingState(isBusy) {
  const submitBtn = document.getElementById('submitContractBtn');
  const backBtn = document.getElementById('backToListBtn');
  const overlay = document.getElementById('ccSubmitOverlay');

  if (submitBtn) {
    const defaultHtml = submitBtn.dataset.defaultHtml || 'Tạo Hợp đồng';
    const loadingHtml = submitBtn.dataset.loadingHtml || 'Đang tạo...';

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

function loadQuotationData(qid) {
  const sel = document.getElementById('quotation_select');
  const opt = sel.options[sel.selectedIndex];
  const preview = document.getElementById('quotation_preview');
  const warning = document.getElementById('quotation_warning');
  const warningText = document.getElementById('quotation_warning_text');

  const companyIdInput = document.getElementById('company_id_input');
  const companyNameInput = document.getElementById('company_name_input');

  if (!qid) {
    preview.style.display = 'none';
    warning.style.display = 'none';
    selectedGrand = 0;

    companyIdInput.value = '';
    companyNameInput.value = '';
    document.getElementById('company_address_input').value = '';
    document.getElementById('contact_input').value = '';
    document.getElementById('male_count_input').value = 0;
    document.getElementById('fs_count_input').value = 0;
    document.getElementById('ff_count_input').value = 0;

    updateDepositCalc();
    return;
  }

  companyIdInput.value = opt.dataset.companyId || '';
  companyNameInput.value = opt.dataset.company || '';

  document.getElementById('company_address_input').value = opt.dataset.address || '';
  document.getElementById('contact_input').value = opt.dataset.contact || '';
  document.getElementById('male_count_input').value = opt.dataset.male || 0;
  document.getElementById('fs_count_input').value = opt.dataset.fs || 0;
  document.getElementById('ff_count_input').value = opt.dataset.ff || 0;

  selectedGrand = parseInt(opt.dataset.grand || 0);
  document.getElementById('qp_company').textContent = opt.dataset.company || '';
  document.getElementById('qp_total').textContent = fmtVnd(selectedGrand) + ' ₫';
  preview.style.display = 'block';

  if (opt.dataset.disabledReason) {
    warningText.textContent = opt.dataset.disabledReason;
    warning.style.display = 'block';
  } else {
    warning.style.display = 'none';
  }

  updateDepositCalc();
}

function updateDepositCalc() {
  const maleCount = parseInt(document.getElementById('male_count_input').value || 0, 10);
  const fsCount = parseInt(document.getElementById('fs_count_input').value || 0, 10);
  const ffCount = parseInt(document.getElementById('ff_count_input').value || 0, 10);

  const qSelect = document.getElementById('quotation_select');
  const selectedOption = qSelect && qSelect.selectedOptions ? qSelect.selectedOptions[0] : null;
  const grand = selectedOption ? parseFloat(selectedOption.dataset.grand || 0) : 0;

  const totalPeople = maleCount + fsCount + ffCount;
  const pct = parseFloat(document.getElementById('deposit_pct_input').value) || 0;
  const autoDeposit = Math.round(grand * pct / 100);

  document.getElementById('js-grand-total').textContent = fmtVnd(grand) + ' ₫';

  const amountInput = document.getElementById('deposit_amount_input');

  if (grand > 0 || totalPeople > 0) {
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

function addBloodRow() {
  const container = document.getElementById('blood-rows');
  const row = container.querySelector('.blood-row').cloneNode(true);

  row.querySelectorAll('input').forEach(inp => {
    inp.value = inp.type === 'number' ? 0 : '';
    inp.classList.remove('is-invalid');
  });

  row.querySelectorAll('.cc-field-error').forEach(el => {
    el.textContent = '';
  });

  container.appendChild(row);
}

document.addEventListener('DOMContentLoaded', function () {
  const form = document.getElementById('ccForm');
  const errorBox = document.getElementById('contract_form_error');
  const quotationSelect = document.getElementById('quotation_select');

  if (quotationSelect) {
    quotationSelect.value = '';
  }

  loadQuotationData('');

  if (!form) return;

  form.addEventListener('keydown', function (e) {
    if (isSubmittingCreateContract && e.key === 'Enter') {
      e.preventDefault();
    }
  });

  document.addEventListener('click', function (e) {
    if (!isSubmittingCreateContract) return;

    const link = e.target.closest('a');
    if (link) {
      e.preventDefault();
    }
  }, true);

  form.addEventListener('input', function (e) {
    const target = e.target;
    if (!target) return;

    target.classList.remove('is-invalid');

    const fieldName = target.name;
    if (!fieldName) return;

    const errorEl = document.querySelector(`.cc-field-error[data-error-for="${CSS.escape(fieldName)}"]`);
    if (errorEl) {
      errorEl.textContent = '';
    }
  });

  form.addEventListener('change', function (e) {
    const target = e.target;
    if (!target) return;

    target.classList.remove('is-invalid');

    const fieldName = target.name;
    if (!fieldName) return;

    const errorEl = document.querySelector(`.cc-field-error[data-error-for="${CSS.escape(fieldName)}"]`);
    if (errorEl) {
      errorEl.textContent = '';
    }
  });

  form.addEventListener('submit', async function (e) {
    e.preventDefault();

    if (isSubmittingCreateContract) {
      return;
    }

    isSubmittingCreateContract = true;
    setSubmittingState(true);

    if (errorBox) {
      errorBox.style.display = 'none';
      errorBox.textContent = '';
    }

    clearFieldErrors();

    try {
      const response = await fetch(form.action, {
        method: 'POST',
        body: new FormData(form),
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
        },
        credentials: 'same-origin',
      });

      let data = {};
      try {
        data = await response.json();
      } catch (jsonErr) {
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
    } catch (err) {
      if (errorBox) {
        errorBox.textContent = 'Không thể gửi yêu cầu. Vui lòng thử lại.';
        errorBox.style.display = 'block';
        errorBox.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    } finally {
      isSubmittingCreateContract = false;
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

  updateDepositCalc();
  syncDepositWordsFromAmount();
});