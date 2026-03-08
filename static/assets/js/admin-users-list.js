function applyFilter(key, val) {
    const params = new URLSearchParams(window.location.search);
    if (val) { params.set(key, val); } else { params.delete(key); }
    params.delete('page');
    window.location.search = params.toString();
  }
