/**
 * quill_image_upload.js
 * ─────────────────────
 * Intercept hành động paste ảnh và click nút ảnh trong Quill editor.
 * Thay vì chèn base64 (data URI lớn) vào Delta, upload file lên server
 * và chèn URL server-side vào Delta — giúp ảnh hiển thị đúng trong
 * docx/PDF được xuất từ server.
 *
 * Cách dùng:
 *   <script src="{% static 'media_library/js/quill_image_upload.js' %}"></script>
 *   <script>
 *     var quillEditor = new Quill('#editor', { theme: 'snow', ... });
 *     enableQuillImageUpload(quillEditor, {
 *       uploadUrl:  "{% url 'media_library:upload_quill_image' %}",
 *       csrfToken:  "{{ csrf_token }}"
 *     });
 *   </script>
 *
 * Yêu cầu:
 *   - apps.media_library được cài và URL được include
 *   - Quill đã được khởi tạo TRƯỚC khi gọi enableQuillImageUpload()
 */

(function (global) {
  'use strict';

  /**
   * @param {Quill} quill   - instance Quill đã khởi tạo
   * @param {object} options
   * @param {string} options.uploadUrl  - URL endpoint upload ảnh
   * @param {string} options.csrfToken  - CSRF token Django
   * @param {number} [options.maxMB=20] - Giới hạn kích thước MB
   */
  function enableQuillImageUpload(quill, options) {
    var uploadUrl = options.uploadUrl;
    var csrfToken = options.csrfToken;
    var maxBytes  = (options.maxMB || 20) * 1024 * 1024;

    if (!uploadUrl || !csrfToken) {
      console.error('enableQuillImageUpload: thiếu uploadUrl hoặc csrfToken');
      return;
    }

    // ── 1. Override handler cho nút image trong toolbar ──────────────────
    var toolbar = quill.getModule('toolbar');
    if (toolbar) {
      toolbar.addHandler('image', function () {
        var input = document.createElement('input');
        input.type   = 'file';
        input.accept = 'image/jpeg,image/png,image/gif,image/webp,image/bmp';
        input.style.display = 'none';
        document.body.appendChild(input);

        input.addEventListener('change', function () {
          var file = input.files[0];
          document.body.removeChild(input);
          if (!file) return;
          uploadAndInsert(file);
        });

        input.click();
      });
    }

    // ── 2. Intercept paste ────────────────────────────────────────────────
    quill.root.addEventListener('paste', function (e) {
      var clipboardData = e.clipboardData || window.clipboardData;
      if (!clipboardData) return;

      var items = clipboardData.items || [];
      for (var i = 0; i < items.length; i++) {
        var item = items[i];
        if (item.type && item.type.startsWith('image/')) {
          // Có ảnh trong clipboard → intercept và upload thay vì để Quill xử lý base64
          e.preventDefault();
          e.stopPropagation();
          var file = item.getAsFile();
          if (file) uploadAndInsert(file);
          return;
        }
      }
    }, true);  // capture phase — chạy trước Quill's own paste handler

    // ── 3. Upload helper ─────────────────────────────────────────────────
    function uploadAndInsert(file) {
      if (file.size > maxBytes) {
        alert('Ảnh quá lớn. Tối đa ' + (maxBytes / 1024 / 1024) + 'MB.');
        return;
      }

      var formData = new FormData();
      formData.append('image', file);

      // Hiện loading indicator nhỏ tại vị trí con trỏ
      var range    = quill.getSelection(true);
      var loadingIdx = range ? range.index : quill.getLength();
      quill.insertText(loadingIdx, '⏳ Đang tải ảnh...', { color: '#aaa' }, 'user');
      var placeholderLen = '⏳ Đang tải ảnh...'.length;

      var xhr = new XMLHttpRequest();
      xhr.open('POST', uploadUrl);
      xhr.setRequestHeader('X-CSRFToken', csrfToken);

      xhr.addEventListener('load', function () {
        // Xóa placeholder
        quill.deleteText(loadingIdx, placeholderLen, 'api');

        try {
          var data = JSON.parse(xhr.responseText);
          if (data.url) {
            quill.insertEmbed(loadingIdx, 'image', data.url, 'user');
            quill.setSelection(loadingIdx + 1, 0, 'api');
          } else {
            alert('Lỗi upload ảnh: ' + (data.error || 'không xác định'));
          }
        } catch (err) {
          alert('Lỗi phản hồi từ server khi upload ảnh.');
        }
      });

      xhr.addEventListener('error', function () {
        quill.deleteText(loadingIdx, placeholderLen, 'api');
        alert('Lỗi kết nối khi upload ảnh.');
      });

      xhr.send(formData);
    }
  }

  // Export global
  global.enableQuillImageUpload = enableQuillImageUpload;

}(window));
