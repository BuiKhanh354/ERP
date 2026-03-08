document.addEventListener('DOMContentLoaded', function() {
    // Tự động tính overall_score nếu để trống
    const form = document.getElementById('performanceScoreForm');
    const efficiencyInput = document.getElementById('id_efficiency_score');
    const qualityInput = document.getElementById('id_quality_score');
    const productivityInput = document.getElementById('id_productivity_score');
    const overallInput = document.getElementById('id_overall_score');

    function calculateOverall() {
      if (overallInput.value && overallInput.value.trim() !== '') {
        return; // Nếu đã có giá trị, không tự động tính
      }
      const efficiency = parseFloat(efficiencyInput.value) || 0;
      const quality = parseFloat(qualityInput.value) || 0;
      const productivity = parseFloat(productivityInput.value) || 0;
      if (efficiency > 0 || quality > 0 || productivity > 0) {
        const avg = (efficiency + quality + productivity) / 3;
        overallInput.value = avg.toFixed(2);
      }
    }

    if (efficiencyInput) efficiencyInput.addEventListener('blur', calculateOverall);
    if (qualityInput) qualityInput.addEventListener('blur', calculateOverall);
    if (productivityInput) productivityInput.addEventListener('blur', calculateOverall);
  });
