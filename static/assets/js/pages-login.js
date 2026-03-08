function updateDateTime() {
              const now = new Date();
              const weekdays = ['Chủ nhật', 'Thứ Hai', 'Thứ Ba', 'Thứ Tư', 'Thứ Năm', 'Thứ Sáu', 'Thứ Bảy'];
              const day = weekdays[now.getDay()];
              const dateStr = now.toLocaleDateString('vi-VN', {year: 'numeric', month: '2-digit', day: '2-digit'});
              const timeStr = now.toLocaleTimeString('vi-VN', {hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false});
              document.getElementById('current-datetime').textContent =
                `${day}, ${dateStr} – ${timeStr}`;
            }
            updateDateTime();
            setInterval(updateDateTime, 1000);

(function () {
        const passwordInput = document.getElementById("id_password");
        const passwordToggle = document.getElementById(
          "toggle-password-visibility"
        );

        if (passwordInput && passwordToggle) {
          passwordToggle.addEventListener("click", function () {
            const icon = this.querySelector("i");
            if (passwordInput.type === "password") {
              passwordInput.type = "text";
              icon.classList.remove("bi-eye");
              icon.classList.add("bi-eye-slash");
            } else {
              passwordInput.type = "password";
              icon.classList.remove("bi-eye-slash");
              icon.classList.add("bi-eye");
            }
          });
        }
      })();
