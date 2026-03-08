// Live clock
  function updateClock() {
    const now = new Date();
    const opts = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' };
    const el = document.getElementById('live-clock');
    if (el) el.textContent = now.toLocaleDateString('vi-VN', opts);
  }
  updateClock();
  setInterval(updateClock, 1000);
