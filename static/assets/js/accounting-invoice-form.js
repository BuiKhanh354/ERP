document.addEventListener('DOMContentLoaded', function() {
  const container = document.getElementById('formset-container');
  const totalForms = document.getElementById('id_items-TOTAL_FORMS');
  const addBtn = document.getElementById('add-item-btn');

  addBtn.addEventListener('click', function() {
    const idx = parseInt(totalForms.value);
    const newRow = document.createElement('div');
    newRow.className = 'formset-row';
    newRow.dataset.index = idx;
    newRow.innerHTML = `
      <div class="form-group desc">
        <label class="form-label small">Mô tả</label>
        <input type="text" name="items-${idx}-description" class="form-control" placeholder="Mô tả">
      </div>
      <div class="form-group">
        <label class="form-label small">Số lượng</label>
        <input type="number" name="items-${idx}-quantity" class="form-control" step="0.01" min="0.01" value="1">
      </div>
      <div class="form-group">
        <label class="form-label small">Đơn giá</label>
        <input type="number" name="items-${idx}-unit_price" class="form-control" step="0.01" min="0" value="0">
      </div>
      <div class="remove-btn">
        <button type="button" class="btn btn-outline-danger btn-sm remove-row-btn" title="Xoá"><i class="bi bi-x-lg"></i></button>
      </div>
    `;
    container.appendChild(newRow);
    totalForms.value = idx + 1;
  });

  container.addEventListener('click', function(e) {
    const removeBtn = e.target.closest('.remove-row-btn');
    if (removeBtn) {
      removeBtn.closest('.formset-row').remove();
    }
    const deleteBtn = e.target.closest('.delete-item-btn');
    if (deleteBtn) {
      const row = deleteBtn.closest('.formset-row');
      const checkbox = row.querySelector('input[name$="-DELETE"]');
      if (checkbox) { checkbox.checked = true; }
      row.style.display = 'none';
    }
  });
});
