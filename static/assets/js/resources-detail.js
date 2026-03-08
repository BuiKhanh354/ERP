// Đảm bảo luôn có showNotification/showConfirm (polyfill)
(function ensureGlobalModals() {
  function fallbackNotify(type, message, title) {
    const full = (title ? (title + ': ') : '') + (message || '');
    window.alert(full);
  }
  function fallbackConfirm(message) {
    return Promise.resolve(window.confirm(message || 'Xác nhận?'));
  }
  if (typeof window.showNotification !== 'function') {
    window.showNotification = function(type, message, title = null) {
      try {
        const modal = document.getElementById('globalNotificationModal');
        if (!modal || typeof bootstrap === 'undefined') {
          return fallbackNotify(type, message, title);
        }
        const header = document.getElementById('globalNotificationModalHeader');
        const label = document.getElementById('globalNotificationModalLabel');
        const body = document.getElementById('globalNotificationModalBody');
        const footer = document.getElementById('globalNotificationModalFooter');
        const resolvedTitle = title || (type === 'success' ? 'Thành công' : type === 'warning' ? 'Cảnh báo' : type === 'info' ? 'Thông tin' : 'Lỗi');
        if (label) label.textContent = resolvedTitle;
        if (header) {
          header.className = 'modal-header';
          if (type === 'success') header.classList.add('bg-success', 'text-white');
          else if (type === 'warning') header.classList.add('bg-warning', 'text-dark');
          else if (type === 'info') header.classList.add('bg-info', 'text-white');
          else header.classList.add('bg-danger', 'text-white');
        }
        if (body) {
          body.innerHTML = `<div>${String(message || '').replace(/\n/g, '<br>')}</div>`;
        }
        if (footer) {
          footer.innerHTML = '<button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Đóng</button>';
        }
        new bootstrap.Modal(modal).show();
      } catch (e) {
        fallbackNotify(type, message, title);
      }
    };
  }
  if (typeof window.showConfirm !== 'function') {
    window.showConfirm = function(message, title = 'Xác nhận', confirmText = 'Xác nhận', cancelText = 'Hủy') {
      try {
        const modal = document.getElementById('globalConfirmModal');
        if (!modal || typeof bootstrap === 'undefined') {
          return fallbackConfirm(message);
        }
        const label = document.getElementById('globalConfirmModalLabel');
        const body = document.getElementById('globalConfirmModalBody');
        const okBtn = document.getElementById('globalConfirmOkBtn');
        const cancelBtn = document.getElementById('globalConfirmCancelBtn');
        if (label) label.textContent = title || 'Xác nhận';
        if (body) body.innerHTML = `<div>${String(message || '').replace(/\n/g, '<br>')}</div>`;
        if (okBtn) okBtn.textContent = confirmText || 'Xác nhận';
        if (cancelBtn) cancelBtn.textContent = cancelText || 'Hủy';
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
        return new Promise((resolve) => {
          const cleanup = () => {
            if (okBtn) okBtn.removeEventListener('click', onOk);
            if (cancelBtn) cancelBtn.removeEventListener('click', onCancel);
            modal.removeEventListener('hidden.bs.modal', onHidden);
          };
          const onOk = () => { cleanup(); bsModal.hide(); resolve(true); };
          const onCancel = () => { cleanup(); bsModal.hide(); resolve(false); };
          const onHidden = () => { cleanup(); resolve(false); };
          if (okBtn) okBtn.addEventListener('click', onOk, { once: true });
          if (cancelBtn) cancelBtn.addEventListener('click', onCancel, { once: true });
          modal.addEventListener('hidden.bs.modal', onHidden, { once: true });
        });
      } catch (e) {
        return fallbackConfirm(message);
      }
    };
  }
})();

function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

async function handleDeleteScore(scoreId, event) {
  if (event) {
    event.preventDefault();
    event.stopPropagation();
  }
  
  const confirmed = await window.showConfirm(
    'Bạn có chắc chắn muốn xóa đánh giá hiệu suất này?<br><small class="text-muted">Hành động này không thể hoàn tác.</small>',
    'Xác nhận xóa đánh giá',
    'Xóa',
    'Hủy'
  );
  if (!confirmed) return;

  const form = document.createElement('form');
  form.method = 'POST';
  form.action = `/performance/scores/${scoreId}/delete/`;

  const csrftoken = getCookie('csrftoken');
  if (csrftoken) {
    const csrfInput = document.createElement('input');
    csrfInput.type = 'hidden';
    csrfInput.name = 'csrfmiddlewaretoken';
    csrfInput.value = csrftoken;
    form.appendChild(csrfInput);
  }

  document.body.appendChild(form);
  form.submit();
}
