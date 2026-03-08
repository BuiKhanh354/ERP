document.addEventListener("DOMContentLoaded", function () {
    // Avatar preview
    const fileInput = document.getElementById("id_avatar");
    if (fileInput) {
      fileInput.addEventListener("change", function (e) {
        const f = e.target.files && e.target.files[0];
        if (!f) return;
        const url = URL.createObjectURL(f);
        const wrap = document.getElementById("avatarPreviewWrap");
        if (!wrap) return;
        wrap.innerHTML = `<img id="avatarPreview" src="${url}" alt="Avatar preview" />`;
      });
    }

    // Password eye toggles
    document.querySelectorAll(".password-eye").forEach((btn) => {
      btn.addEventListener("click", () => {
        const targetId = btn.getAttribute("data-target");
        const input = document.getElementById(targetId);
        if (!input) return;
        input.type = input.type === "password" ? "text" : "password";
        const icon = btn.querySelector("i");
        if (icon) icon.className = input.type === "password" ? "bi bi-eye" : "bi bi-eye-slash";
      });
    });

    // Show modal message
    function showMessage(title, message, type = 'success') {
      const modal = new bootstrap.Modal(document.getElementById('messageModal'));
      const modalBody = document.getElementById('messageModalBody');
      const modalTitle = document.getElementById('messageModalLabel');
      
      modalTitle.textContent = title;
      const icon = type === 'success' ? '<i class="bi bi-check-circle-fill text-success me-2"></i>' : '<i class="bi bi-exclamation-triangle-fill text-danger me-2"></i>';
      modalBody.innerHTML = `<div class="d-flex align-items-center">${icon}<span>${message}</span></div>`;
      modal.show();
    }

    // Handle form submissions with AJAX
    function handleFormSubmit(formId, submitBtnId, successMsg) {
      const form = document.getElementById(formId);
      const submitBtn = document.getElementById(submitBtnId);
      
      if (!form || !submitBtn) return;

      form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const formData = new FormData(form);
        const originalBtnText = submitBtn.innerHTML;
        
        // Show loading state
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="loading-spinner"></span> Đang xử lý...';

        try {
          const response = await fetch(form.action || window.location.href, {
            method: 'POST',
            body: formData,
            headers: {
              'X-Requested-With': 'XMLHttpRequest',
            },
          });

          const contentType = response.headers.get('content-type');
          
          if (contentType && contentType.includes('application/json')) {
            // JSON response (AJAX)
            const data = await response.json();
            
            if (data.success) {
              showMessage('Thành công', data.message || successMsg, 'success');
              
              // Reset form if needed
              if (formId === 'profileForm') {
                // Reload page to update avatar in topbar
                setTimeout(() => window.location.reload(), 1500);
              } else if (formId === 'emailRequestForm') {
                // Enable verify button and update status
                document.getElementById('verifyOtpBtn').disabled = false;
                document.getElementById('otpStatus').innerHTML = `OTP đang chờ xác nhận cho email: <strong>${formData.get('new_email')}</strong>`;
                form.reset();
              } else if (formId === 'emailVerifyForm') {
                // Reload page to update email
                setTimeout(() => window.location.reload(), 1500);
              } else if (formId === 'passwordForm') {
                form.reset();
              }
            } else {
              showMessage('Lỗi', data.message || 'Có lỗi xảy ra. Vui lòng thử lại.', 'error');
              
              // Show field errors if any
              if (data.errors) {
                Object.keys(data.errors).forEach(field => {
                  const input = form.querySelector(`[name="${field}"]`);
                  if (input) {
                    input.classList.add('is-invalid');
                    const errorDiv = document.createElement('div');
                    errorDiv.className = 'invalid-feedback';
                    errorDiv.textContent = data.errors[field];
                    input.parentNode.appendChild(errorDiv);
                  }
                });
              }
            }
          } else {
            // HTML response (redirect or form errors)
            const html = await response.text();
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            
            // Check for error messages in form
            const errorMessages = doc.querySelectorAll('.text-danger, .alert-danger, .invalid-feedback');
            if (errorMessages.length > 0) {
              let errorText = Array.from(errorMessages).map(el => el.textContent.trim()).join('; ');
              showMessage('Lỗi', errorText || 'Có lỗi xảy ra. Vui lòng kiểm tra lại thông tin.', 'error');
            } else {
              // Success - reload page
              showMessage('Thành công', successMsg, 'success');
              setTimeout(() => window.location.reload(), 1500);
            }
          }
        } catch (error) {
          console.error('Error:', error);
          showMessage('Lỗi', 'Có lỗi xảy ra khi gửi yêu cầu. Vui lòng thử lại.', 'error');
        } finally {
          submitBtn.disabled = false;
          submitBtn.innerHTML = originalBtnText;
        }
      });
    }

    // Initialize form handlers
    handleFormSubmit('profileForm', 'profileSubmitBtn', 'Đã cập nhật hồ sơ thành công.');
    handleFormSubmit('emailRequestForm', 'sendOtpBtn', 'Đã gửi OTP tới email mới.');
    handleFormSubmit('emailVerifyForm', 'verifyOtpBtn', 'Đổi email thành công.');
    handleFormSubmit('passwordForm', 'passwordSubmitBtn', 'Đổi mật khẩu thành công.');
  });
