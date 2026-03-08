// Scroll đến đề xuất mới sau khi tạo thành công
  document.addEventListener('DOMContentLoaded', function() {
    const newRecElement = document.querySelector('.list-group-item.border-primary');
    if (newRecElement) {
      setTimeout(function() {
        newRecElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, 300);
    }
  });
