(function () {
    const otpInput = document.getElementById("id_otp");
    const pwd1 = document.getElementById("id_new_password1");
    const pwd2 = document.getElementById("id_new_password2");
    const toggle1 = document.getElementById("toggle-new-password1");
    const toggle2 = document.getElementById("toggle-new-password2");

    function setPasswordFieldsEnabled(enabled) {
      if (pwd1) pwd1.disabled = !enabled;
      if (pwd2) pwd2.disabled = !enabled;
    }

    // Disable mật khẩu cho tới khi OTP đủ 6 ký tự
    setPasswordFieldsEnabled(otpInput && otpInput.value.length === 6);

    if (otpInput) {
      otpInput.setAttribute("maxlength", "6");
      otpInput.addEventListener("input", function () {
        const value = this.value.replace(/[^0-9]/g, "");
        if (this.value !== value) {
          this.value = value;
        }
        setPasswordFieldsEnabled(this.value.length === 6);
      });
    }

    function attachToggle(toggleEl, inputEl) {
      if (!toggleEl || !inputEl) return;
      toggleEl.addEventListener("click", function () {
        const icon = this.querySelector("i");
        if (inputEl.type === "password") {
          inputEl.type = "text";
          icon.classList.remove("bi-eye");
          icon.classList.add("bi-eye-slash");
        } else {
          inputEl.type = "password";
          icon.classList.remove("bi-eye-slash");
          icon.classList.add("bi-eye");
        }
      });
    }

    attachToggle(toggle1, pwd1);
    attachToggle(toggle2, pwd2);
  })();
