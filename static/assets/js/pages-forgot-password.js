(function () {
    const form = document.querySelector(".auth-card form");
    const btn = document.getElementById("btn-send-otp");
    const textSpan = document.getElementById("btn-send-otp-text");
    const loadingSpan = document.getElementById("btn-send-otp-loading");

    if (form && btn && textSpan && loadingSpan) {
      form.addEventListener("submit", function () {
        btn.disabled = true;
        loadingSpan.style.display = "inline-block";
        textSpan.textContent = "Đang gửi...";
      });
    }
  })();
