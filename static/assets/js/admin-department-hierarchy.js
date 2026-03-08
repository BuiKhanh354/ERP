document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.tree-toggle').forEach(btn => {
    btn.addEventListener('click', function() {
      const target = document.getElementById(this.dataset.target);
      if (target) {
        target.classList.toggle('d-none');
        this.classList.toggle('collapsed');
      }
    });
  });
});
