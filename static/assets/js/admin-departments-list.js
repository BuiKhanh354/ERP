function applyFilter() {
    const status = document.getElementById('statusFilter').value;
    const params = new URLSearchParams(window.location.search);
    if (status) {
      params.set('status', status);
    } else {
      params.delete('status');
    }
    params.delete('page');
    window.location.search = params.toString();
  }
