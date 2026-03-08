function applyFilter(val) {
    const params = new URLSearchParams(window.location.search);
    if (val) { params.set('action', val); } else { params.delete('action'); }
    params.delete('page');
    window.location.search = params.toString();
  }
