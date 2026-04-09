/**
 * quill_media_picker.js
 * ─────────────────────
 * Cung cấp 2 tính năng cho Quill editor:
 *
 * 1. Media Library Picker — nút "📚 Thư viện" trên toolbar:
 *    - Chọn ảnh hoặc file từ server media library
 *    - Upload file mới trực tiếp từ modal
 *    - Ảnh → chèn <img src="..."> vào Quill
 *    - File khác → chèn link có tên file
 *
 * 2. Image Editor — bấm vào ảnh trong Quill để sửa:
 *    - Alt text
 *    - Chiều rộng (px hoặc auto)
 *    - Căn lề (left / center / right)
 *    - Link khi bấm vào ảnh
 *    - Xóa ảnh
 *
 * Cách dùng trong template:
 * ─────────────────────────
 *   {% load static %}
 *   {% include "media_library/_modal_media_picker.html" %}
 *   <script src="{% static 'media_library/js/quill_image_upload.js' %}"></script>
 *   <script src="{% static 'media_library/js/quill_media_picker.js' %}"></script>
 *   <script>
 *     var quillEditor;
 *     document.addEventListener('DOMContentLoaded', function () {
 *       quillEditor = new Quill('#quill-editor', { ... });
 *
 *       enableQuillImageUpload(quillEditor, {
 *         uploadUrl: "{% url 'media_library:upload_quill_image' %}",
 *         csrfToken: "{{ csrf_token }}"
 *       });
 *
 *       enableQuillMediaPicker(quillEditor, {
 *         listUrl:   "{% url 'media_library:list_json' %}",
 *         uploadUrl: "{% url 'media_library:upload' %}",
 *         csrfToken: "{{ csrf_token }}"
 *       });
 *     });
 *   </script>
 *
 * Yêu cầu:
 *   - Bootstrap 5 (modal, toast)
 *   - FontAwesome (icon)
 *   - apps.media_library cài và URL included
 *   - _modal_media_picker.html được include TRONG {% block content %}
 */

(function (global) {
  'use strict';

  // ═══════════════════════════════════════════════════════════════════════
  // enableQuillMediaPicker
  // ═══════════════════════════════════════════════════════════════════════
  function enableQuillMediaPicker(quill, options) {
    var LIST_URL   = options.listUrl;
    var UPLOAD_URL = options.uploadUrl;
    var CSRF       = options.csrfToken;

    if (!LIST_URL || !UPLOAD_URL || !CSRF) {
      console.error('enableQuillMediaPicker: thiếu listUrl, uploadUrl hoặc csrfToken');
      return;
    }

    // ── 1. Thêm nút "Thư viện" vào toolbar ─────────────────────────────
    var toolbar = quill.getModule('toolbar');
    if (toolbar) {
      // Thêm custom button vào cuối toolbar container
      var toolbarEl = toolbar.container;
      var libGroup  = document.createElement('span');
      libGroup.className = 'ql-formats';
      libGroup.innerHTML = '<button class="ql-library" title="Chèn từ Thư viện Media" type="button">'
        + '<svg viewBox="0 0 18 18" width="18" height="18">'
        + '<rect x="1" y="1" width="7" height="7" rx="1" fill="none" stroke="currentColor" stroke-width="1.5"/>'
        + '<rect x="10" y="1" width="7" height="7" rx="1" fill="none" stroke="currentColor" stroke-width="1.5"/>'
        + '<rect x="1" y="10" width="7" height="7" rx="1" fill="none" stroke="currentColor" stroke-width="1.5"/>'
        + '<rect x="10" y="10" width="7" height="7" rx="1" fill="none" stroke="currentColor" stroke-width="1.5"/>'
        + '</svg>'
        + '</button>';
      toolbarEl.appendChild(libGroup);

      libGroup.querySelector('.ql-library').addEventListener('click', function () {
        openPicker();
      });
    }

    // ── 2. Phơi hàm mở picker ra global (dùng được từ ngoài) ───────────
    global.mlPickerOpen = openPicker;

    // ═══════════════════════════════════════════════════════════════════
    // MEDIA PICKER STATE
    // ═══════════════════════════════════════════════════════════════════
    var state = {
      page:      1,
      typeFilter: '',
      search:    '',
      selected:  null,   // { id, url, name, file_type, is_image }
      loading:   false,
    };

    var savedRange = null;  // vị trí con trỏ Quill khi mở picker

    // DOM refs
    var modalEl    = document.getElementById('modalMediaPicker');
    var gridEl     = document.getElementById('mlpGrid');
    var pagerEl    = document.getElementById('mlpPager');
    var searchEl   = document.getElementById('mlpSearch');
    var selInfoEl  = document.getElementById('mlpSelInfo');
    var btnInsert  = document.getElementById('mlpBtnInsert');
    var uploadZone = document.getElementById('mlpUploadZone');
    var fileInput  = document.getElementById('mlpFileInput');

    if (!modalEl) {
      console.warn('quill_media_picker: #modalMediaPicker không tìm thấy trong DOM. '
        + 'Hãy thêm {% include "media_library/_modal_media_picker.html" %} trong template.');
      return;
    }

    var bsModal = new bootstrap.Modal(modalEl);

    // ── Tabs ─────────────────────────────────────────────────────────────
    modalEl.querySelectorAll('[data-mlp-tab]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        modalEl.querySelectorAll('[data-mlp-tab]').forEach(function (b) { b.classList.remove('active'); });
        btn.classList.add('active');
        var tab = btn.dataset.mlpTab;
        document.getElementById('mlpTabLibrary').style.display = tab === 'library' ? '' : 'none';
        document.getElementById('mlpTabUpload').style.display  = tab === 'upload'  ? '' : 'none';
        document.getElementById('mlpFooter').style.display     = tab === 'library' ? '' : 'none';
      });
    });

    // ── Type filter buttons ───────────────────────────────────────────────
    modalEl.querySelectorAll('.mlp-type-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        modalEl.querySelectorAll('.mlp-type-btn').forEach(function (b) {
          b.className = 'btn btn-outline-secondary btn-sm mlp-type-btn';
        });
        btn.className = 'btn btn-primary btn-sm mlp-type-btn active';
        state.typeFilter = btn.dataset.type;
        state.page       = 1;
        state.selected   = null;
        loadGrid();
      });
    });

    // ── Search ────────────────────────────────────────────────────────────
    var searchTimeout;
    searchEl.addEventListener('input', function () {
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(function () {
        state.search = searchEl.value.trim();
        state.page   = 1;
        state.selected = null;
        loadGrid();
      }, 350);
    });

    // ── Load grid từ API ─────────────────────────────────────────────────
    function loadGrid() {
      if (state.loading) return;
      state.loading = true;
      gridEl.innerHTML = '<div class="mlp-spinner"><i class="fa fa-circle-notch fa-spin me-2"></i> Đang tải...</div>';
      pagerEl.innerHTML = '';

      var url = LIST_URL + '?page=' + state.page + '&per_page=24';
      if (state.typeFilter) url += '&type=' + encodeURIComponent(state.typeFilter);
      if (state.search)     url += '&q='    + encodeURIComponent(state.search);

      fetch(url, { credentials: 'same-origin' })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          state.loading = false;
          renderGrid(data);
          renderPager(data);
        })
        .catch(function () {
          state.loading = false;
          gridEl.innerHTML = '<div class="mlp-empty"><i class="fa fa-exclamation-circle me-1 text-danger"></i> Lỗi tải dữ liệu.</div>';
        });
    }

    function renderGrid(data) {
      if (!data.items || !data.items.length) {
        gridEl.innerHTML = '<div class="mlp-empty"><i class="fa fa-folder-open fa-2x d-block mb-2 opacity-25"></i>Không có file nào.</div>';
        return;
      }

      gridEl.innerHTML = '';
      data.items.forEach(function (item) {
        var card = document.createElement('div');
        card.className = 'mlp-item';
        card.dataset.id = item.id;

        var thumbHtml;
        if (item.is_image) {
          thumbHtml = '<img src="' + escHtml(item.url) + '" alt="' + escHtml(item.alt_text || item.name) + '" loading="lazy">';
        } else {
          var icons = { pdf: '📄', docx: '📝', excel: '📊' };
          thumbHtml = '<span class="mlp-icon">' + (icons[item.file_type] || '📎') + '</span>';
        }

        card.innerHTML = '<div class="mlp-thumb">'
          + thumbHtml
          + '<div class="mlp-check">✓</div>'
          + '</div>'
          + '<div class="mlp-name" title="' + escHtml(item.name) + '">' + escHtml(item.name) + '</div>'
          + '<div class="mlp-meta">' + escHtml(item.file_size_display) + '</div>';

        card.addEventListener('click', function () {
          // Toggle select
          var already = state.selected && state.selected.id === item.id;
          modalEl.querySelectorAll('.mlp-item').forEach(function (c) { c.classList.remove('mlp-selected'); });
          if (!already) {
            card.classList.add('mlp-selected');
            state.selected = item;
            selInfoEl.textContent = 'Đã chọn: ' + item.name;
            btnInsert.disabled = false;
          } else {
            state.selected = null;
            selInfoEl.textContent = 'Chưa chọn file nào';
            btnInsert.disabled = true;
          }
        });

        gridEl.appendChild(card);
      });
    }

    function renderPager(data) {
      pagerEl.innerHTML = '';
      if (data.num_pages <= 1) return;
      if (data.has_prev) {
        var prev = mkBtn('‹ Trước', function () { state.page--; loadGrid(); });
        pagerEl.appendChild(prev);
      }
      var info = document.createElement('span');
      info.className = 'btn btn-sm btn-light disabled';
      info.textContent = data.page + ' / ' + data.num_pages;
      pagerEl.appendChild(info);
      if (data.has_next) {
        var next = mkBtn('Sau ›', function () { state.page++; loadGrid(); });
        pagerEl.appendChild(next);
      }
    }

    function mkBtn(label, cb) {
      var b = document.createElement('button');
      b.className = 'btn btn-sm btn-outline-secondary';
      b.textContent = label;
      b.addEventListener('click', cb);
      return b;
    }

    // ── Insert vào Quill ─────────────────────────────────────────────────
    btnInsert.addEventListener('click', function () {
      if (!state.selected) return;
      var item = state.selected;

      // Khôi phục focus và vị trí con trỏ
      quill.focus();
      var range = savedRange || quill.getSelection() || { index: quill.getLength(), length: 0 };

      if (item.is_image) {
        quill.insertEmbed(range.index, 'image', item.url, 'user');
        quill.setSelection(range.index + 1, 0, 'api');
      } else {
        // File không phải ảnh → chèn link
        quill.insertText(range.index, item.name, { link: item.url }, 'user');
        quill.setSelection(range.index + item.name.length, 0, 'api');
      }

      bsModal.hide();
      // Reset
      state.selected = null;
      btnInsert.disabled = true;
      selInfoEl.textContent = 'Chưa chọn file nào';
    });

    // ── Upload tab ───────────────────────────────────────────────────────
    ['dragenter', 'dragover'].forEach(function (evt) {
      uploadZone.addEventListener(evt, function (e) { e.preventDefault(); uploadZone.classList.add('mlp-dz-over'); });
    });
    ['dragleave', 'drop'].forEach(function (evt) {
      uploadZone.addEventListener(evt, function (e) { e.preventDefault(); uploadZone.classList.remove('mlp-dz-over'); });
    });
    uploadZone.addEventListener('drop', function (e) { doUpload(e.dataTransfer.files); });
    fileInput.addEventListener('change', function () { doUpload(this.files); this.value = ''; });

    function doUpload(files) {
      if (!files || !files.length) return;
      var resultEl  = document.getElementById('mlpUploadResult');
      var barEl     = document.getElementById('mlpUploadBar');
      var statusEl  = document.getElementById('mlpUploadStatus');
      resultEl.style.display = 'block';
      barEl.style.width = '10%';
      statusEl.textContent = 'Đang upload ' + files.length + ' file...';

      var fd = new FormData();
      for (var i = 0; i < files.length; i++) fd.append('files', files[i]);

      var xhr = new XMLHttpRequest();
      xhr.open('POST', UPLOAD_URL);
      xhr.setRequestHeader('X-CSRFToken', CSRF);
      xhr.upload.addEventListener('progress', function (e) {
        if (e.lengthComputable) barEl.style.width = Math.round(e.loaded / e.total * 90) + '%';
      });
      xhr.addEventListener('load', function () {
        barEl.style.width = '100%';
        try {
          var data = JSON.parse(xhr.responseText);
          if (data.files && data.files.length) {
            statusEl.textContent = 'Upload thành công ' + data.files.length + ' file!';
            statusEl.className = 'text-success';
            // Chuyển sang tab library và reload
            setTimeout(function () {
              modalEl.querySelector('[data-mlp-tab="library"]').click();
              state.page = 1;
              loadGrid();
              resultEl.style.display = 'none';
              barEl.style.width = '0%';
              statusEl.className = 'text-muted';
            }, 900);
          }
          if (data.errors && data.errors.length) {
            statusEl.textContent = data.errors.join(' | ');
            statusEl.className = 'text-danger';
          }
        } catch (e) {
          statusEl.textContent = 'Lỗi phản hồi server.';
          statusEl.className = 'text-danger';
        }
      });
      xhr.addEventListener('error', function () {
        statusEl.textContent = 'Lỗi kết nối.';
        statusEl.className = 'text-danger';
      });
      xhr.send(fd);
    }

    // ── Mở modal ─────────────────────────────────────────────────────────
    function openPicker() {
      savedRange = quill.getSelection();
      // Reset về tab library
      modalEl.querySelector('[data-mlp-tab="library"]').click();
      state.page       = 1;
      state.typeFilter = '';
      state.search     = '';
      state.selected   = null;
      searchEl.value   = '';
      btnInsert.disabled = true;
      selInfoEl.textContent = 'Chưa chọn file nào';
      // Reset type buttons
      modalEl.querySelectorAll('.mlp-type-btn').forEach(function (b) {
        b.className = 'btn btn-outline-secondary btn-sm mlp-type-btn';
      });
      modalEl.querySelector('.mlp-type-btn[data-type=""]').className = 'btn btn-primary btn-sm mlp-type-btn active';
      bsModal.show();
      loadGrid();
    }

    // ── Reset khi đóng modal ──────────────────────────────────────────────
    modalEl.addEventListener('hidden.bs.modal', function () {
      state.selected = null;
      btnInsert.disabled = true;
      selInfoEl.textContent = 'Chưa chọn file nào';
    });
  }


  // ═══════════════════════════════════════════════════════════════════════
  // enableQuillImageEditor
  // Bấm vào ảnh trong Quill → mở modal sửa
  // ═══════════════════════════════════════════════════════════════════════
  function enableQuillImageEditor(quill) {
    var modalEl = document.getElementById('modalImageEdit');
    if (!modalEl) {
      console.warn('enableQuillImageEditor: #modalImageEdit không tìm thấy. Hãy include _modal_media_picker.html');
      return;
    }

    var bsModal    = new bootstrap.Modal(modalEl);
    var targetImg  = null;  // <img> element đang sửa
    var targetIdx  = null;  // vị trí trong Quill delta

    var previewEl  = document.getElementById('imgEditPreview');
    var altInput   = document.getElementById('imgEditAlt');
    var widthInput = document.getElementById('imgEditWidth');
    var linkInput  = document.getElementById('imgEditLink');
    var btnSave    = document.getElementById('imgEditBtnSave');
    var btnDelete  = document.getElementById('imgEditBtnDelete');
    var btnClear   = document.getElementById('imgEditWidthClear');

    // ── Bấm vào ảnh trong editor ─────────────────────────────────────────
    quill.root.addEventListener('click', function (e) {
      var img = e.target.closest('img');
      if (!img || !quill.root.contains(img)) return;

      targetImg = img;

      // Tìm vị trí của ảnh trong Quill delta
      var blot = Quill.find(img);
      targetIdx = blot ? quill.getIndex(blot) : null;

      // Điền dữ liệu vào modal
      previewEl.src    = img.src;
      altInput.value   = img.alt    || '';
      linkInput.value  = img.dataset.link || '';
      widthInput.value = img.style.width
        ? parseInt(img.style.width)
        : (img.getAttribute('width') ? parseInt(img.getAttribute('width')) : '');

      // Xác định căn lề hiện tại
      modalEl.querySelectorAll('.img-align-btn').forEach(function (b) { b.classList.remove('active'); });
      var para = img.closest('p') || img.parentElement;
      var align = '';
      if (para) {
        var cls  = para.className || '';
        var style = para.getAttribute('style') || '';
        if (cls.includes('ql-align-center') || style.includes('text-align: center')) align = 'center';
        else if (cls.includes('ql-align-right') || style.includes('text-align: right'))  align = 'right';
      }
      var activeAlignBtn = modalEl.querySelector('.img-align-btn[data-align="' + align + '"]');
      if (activeAlignBtn) activeAlignBtn.classList.add('active');

      bsModal.show();
    });

    // ── Căn lề buttons ───────────────────────────────────────────────────
    modalEl.querySelectorAll('.img-align-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        modalEl.querySelectorAll('.img-align-btn').forEach(function (b) { b.classList.remove('active'); });
        btn.classList.add('active');
      });
    });

    // ── Clear width ───────────────────────────────────────────────────────
    btnClear.addEventListener('click', function () { widthInput.value = ''; });

    // ── Áp dụng thay đổi ─────────────────────────────────────────────────
    btnSave.addEventListener('click', function () {
      if (!targetImg) return;

      // 1. Alt text
      targetImg.alt = altInput.value.trim();

      // 2. Chiều rộng
      var w = parseInt(widthInput.value);
      if (w && w > 0) {
        targetImg.style.width    = w + 'px';
        targetImg.style.maxWidth = '100%';
        targetImg.removeAttribute('width');
      } else {
        targetImg.style.width = '';
        targetImg.removeAttribute('width');
      }

      // 3. Link bọc ảnh
      var link = linkInput.value.trim();
      var parent = targetImg.parentElement;
      if (link) {
        if (parent && parent.tagName === 'A') {
          parent.href = link;
        } else {
          var a = document.createElement('a');
          a.href   = link;
          a.target = '_blank';
          a.rel    = 'noopener';
          targetImg.parentNode.insertBefore(a, targetImg);
          a.appendChild(targetImg);
        }
        targetImg.dataset.link = link;
      } else {
        // Xóa link nếu có
        if (parent && parent.tagName === 'A') {
          parent.parentNode.insertBefore(targetImg, parent);
          parent.parentNode.removeChild(parent);
        }
        delete targetImg.dataset.link;
      }

      // 4. Căn lề — áp dụng lên paragraph chứa ảnh
      var activeAlignBtn = modalEl.querySelector('.img-align-btn.active');
      var align = activeAlignBtn ? activeAlignBtn.dataset.align : '';
      if (targetIdx !== null) {
        // Lấy vị trí dòng của ảnh
        var lineInfo = quill.getLine(targetIdx);
        var linePara = lineInfo && lineInfo[0] ? lineInfo[0].domNode : null;
        if (linePara) {
          // Xóa align cũ
          linePara.classList.remove('ql-align-center', 'ql-align-right', 'ql-align-justify');
          linePara.style.textAlign = '';
          if (align === 'center') {
            linePara.classList.add('ql-align-center');
          } else if (align === 'right') {
            linePara.classList.add('ql-align-right');
          }
        }
      }

      bsModal.hide();
      targetImg = null;
      targetIdx = null;
    });

    // ── Xóa ảnh ──────────────────────────────────────────────────────────
    btnDelete.addEventListener('click', function () {
      if (!targetImg) return;
      var confirmDel = confirm('Xóa ảnh này khỏi nội dung?');
      if (!confirmDel) return;

      if (targetIdx !== null) {
        quill.deleteText(targetIdx, 1, 'user');
      } else {
        // Fallback: xóa trực tiếp khỏi DOM
        var el = targetImg.parentElement && targetImg.parentElement.tagName === 'A'
          ? targetImg.parentElement
          : targetImg;
        el.parentNode && el.parentNode.removeChild(el);
      }

      bsModal.hide();
      targetImg = null;
      targetIdx = null;
    });

    // ── Thêm tooltip nhỏ khi hover ảnh trong editor ──────────────────────
    var tooltip = document.createElement('div');
    tooltip.style.cssText = [
      'position:absolute', 'background:rgba(0,0,0,.65)', 'color:#fff',
      'font-size:.68rem', 'padding:2px 7px', 'border-radius:4px',
      'pointer-events:none', 'display:none', 'z-index:9999',
      'white-space:nowrap',
    ].join(';');
    tooltip.textContent = '✎ Bấm để sửa ảnh';
    document.body.appendChild(tooltip);

    quill.root.addEventListener('mouseover', function (e) {
      var img = e.target.closest('img');
      if (img && quill.root.contains(img)) {
        img.style.cursor = 'pointer';
        img.style.outline = '2px dashed #3b82f6';
        var rect = img.getBoundingClientRect();
        tooltip.style.left = (rect.left + window.scrollX) + 'px';
        tooltip.style.top  = (rect.top  + window.scrollY - 24) + 'px';
        tooltip.style.display = 'block';
      }
    });
    quill.root.addEventListener('mouseout', function (e) {
      var img = e.target.closest('img');
      if (img) {
        img.style.outline = '';
        tooltip.style.display = 'none';
      }
    });
  }


  // ═══════════════════════════════════════════════════════════════════════
  // Utility
  // ═══════════════════════════════════════════════════════════════════════
  function escHtml(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }


  // Export globals
  global.enableQuillMediaPicker  = enableQuillMediaPicker;
  global.enableQuillImageEditor  = enableQuillImageEditor;

}(window));
