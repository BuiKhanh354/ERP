if (typeof Chart !== 'undefined' && typeof ChartDataLabels !== 'undefined') {
    Chart.register(ChartDataLabels);
  }

  function safeJsonParse(id, fallback = []) {
    const el = document.getElementById(id);
    if (!el) return fallback;
    try {
      const raw = (el.textContent || '').trim();
      if (!raw) return fallback;
      if (!(raw.startsWith('[') || raw.startsWith('{'))) return fallback;
      const parsed = JSON.parse(raw);
      return normalizeArray(parsed);
    } catch (err) {
      console.error('JSON parse error', id, err);
      return fallback;
    }
  }

  function normalizeArray(val) {
    if (Array.isArray(val)) return val;
    if (val && typeof val === 'object') return Object.values(val);
    return [];
  }

  function toNumberArray(arr) {
    return normalizeArray(arr).map(v => {
      const n = Number(v);
      return Number.isFinite(n) ? n : 0;
    });
  }

  function buildChart(buildFn) {
    try {
      buildFn();
    } catch (err) {
      console.error('Chart build error', err);
    }
  }

  // Project Status Chart
  buildChart(function () {
    const ctx = document.getElementById('projectStatusChart');
    if (!ctx) return;
    const labels = safeJsonParse('project_status_labels');
    const data = toNumberArray(safeJsonParse('project_status_data'));
    if (!labels.length || !data.length) return;
    new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels,
        datasets: [{
          data,
          backgroundColor: ['#0000cd', '#3b82f6', '#22c55e', '#f59e0b', '#ef4444']
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom' },
          datalabels: {
            color: '#ffffff',
            font: { weight: 'bold', size: 12 },
            formatter: function(value, context) {
              const total = (context.dataset.data || []).reduce((a, b) => a + (Number(b) || 0), 0);
              const pct = total > 0 ? Math.round((Number(value) / total) * 100) : 0;
              return pct >= 5 ? pct + '%' : '';
            }
          }
        }
      }
    });
  });

  // Expense Type Chart
  buildChart(function () {
    const ctx = document.getElementById('expenseTypeChart');
    if (!ctx) return;
    const labels = safeJsonParse('expense_by_type_labels');
    const data = toNumberArray(safeJsonParse('expense_by_type_data'));
    if (!labels.length || !data.length) return;
    new Chart(ctx, {
      type: 'bar',
      data: {
        labels,
        datasets: [{ label: 'Chi phí (VNĐ)', data, backgroundColor: '#0000cd' }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          datalabels: {
            anchor: 'end',
            align: 'top',
            color: '#0f172a',
            font: { weight: 'bold', size: 10 },
            formatter: function(value) {
              const v = Number(value) || 0;
              if (v >= 1000000) return (v / 1000000).toFixed(1) + 'M';
              if (v >= 1000) return (v / 1000).toFixed(0) + 'K';
              return v.toLocaleString('vi-VN');
            }
          },
          tooltip: { callbacks: { label: c => (c.parsed.y || 0).toLocaleString('vi-VN') + ' VNĐ' } }
        },
        scales: { y: { beginAtZero: true, ticks: { callback: v => (v || 0).toLocaleString('vi-VN') + ' VNĐ' } } }
      }
    });
  });

  // Monthly Expense Chart
  buildChart(function () {
    const ctx = document.getElementById('monthlyExpenseChart');
    if (!ctx) return;
    const labels = safeJsonParse('monthly_expenses_labels');
    const data = toNumberArray(safeJsonParse('monthly_expenses_data'));
    if (!labels.length || !data.length) return;
    new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: 'Chi tiêu (VNĐ)',
          data,
          borderColor: '#0000cd',
          backgroundColor: 'rgba(0, 0, 205, 0.1)',
          tension: 0.4,
          fill: true
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom' },
          datalabels: {
            anchor: 'end',
            align: 'top',
            color: '#0f172a',
            font: { weight: 'bold', size: 10 },
            formatter: function(value) {
              const v = Number(value) || 0;
              if (v >= 1000000) return (v / 1000000).toFixed(1) + 'M';
              if (v >= 1000) return (v / 1000).toFixed(0) + 'K';
              return v.toLocaleString('vi-VN');
            }
          },
          tooltip: { callbacks: { label: c => (c.parsed.y || 0).toLocaleString('vi-VN') + ' VNĐ' } }
        },
        scales: { y: { beginAtZero: true, ticks: { callback: v => (v || 0).toLocaleString('vi-VN') + ' VNĐ' } } }
      }
    });
  });

  // Budget vs Spent Chart
  buildChart(function () {
    const ctx = document.getElementById('budgetVsSpentChart');
    if (!ctx) return;
    const labels = safeJsonParse('budget_vs_spent_projects');
    const allocated = toNumberArray(safeJsonParse('budget_vs_spent_allocated'));
    const spent = toNumberArray(safeJsonParse('budget_vs_spent_spent'));
    if (!labels.length || !allocated.length || !spent.length) return;
    new Chart(ctx, {
      type: 'bar',
      data: {
        labels,
        datasets: [
          { label: 'Phân bổ (VNĐ)', data: allocated, backgroundColor: '#3b82f6' },
          { label: 'Chi tiêu (VNĐ)', data: spent, backgroundColor: '#ef4444' }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom' },
          datalabels: {
            anchor: 'end',
            align: 'top',
            color: '#0f172a',
            font: { weight: 'bold', size: 10 },
            formatter: function(value) {
              const v = Number(value) || 0;
              if (v >= 1000000) return (v / 1000000).toFixed(1) + 'M';
              if (v >= 1000) return (v / 1000).toFixed(0) + 'K';
              return v.toLocaleString('vi-VN');
            }
          },
          tooltip: { callbacks: { label: c => `${c.dataset.label}: ${(c.parsed.y || 0).toLocaleString('vi-VN')} VNĐ` } }
        },
        scales: { y: { beginAtZero: true, ticks: { callback: v => (v || 0).toLocaleString('vi-VN') + ' VNĐ' } } }
      }
    });
  });

  // Project Completion Chart
  buildChart(function () {
    const ctx = document.getElementById('projectCompletionChart');
    if (!ctx) return;
    const labels = safeJsonParse('project_completion_names');
    const data = toNumberArray(safeJsonParse('project_completion_rates'));
    if (!labels.length || !data.length) return;
    const colors = data.map(rate => rate >= 80 ? '#22c55e' : rate >= 50 ? '#f59e0b' : '#ef4444');
    new Chart(ctx, {
      type: 'bar',
      data: { labels, datasets: [{ label: 'Tỷ lệ hoàn thành (%)', data, backgroundColor: colors }] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          datalabels: {
            anchor: 'end',
            align: 'top',
            color: '#0f172a',
            font: { weight: 'bold', size: 10 },
            formatter: function(value) {
              const v = Number(value) || 0;
              return v.toFixed(1) + '%';
            }
          },
          tooltip: { callbacks: { label: c => (c.parsed.y || 0).toFixed(1) + '%' } }
        },
        scales: { y: { beginAtZero: true, max: 100, ticks: { callback: v => (v || 0) + '%' } } }
      }
    });
  });

  // Expense by Category Chart
  buildChart(function () {
    const ctx = document.getElementById('expenseByCategoryChart');
    if (!ctx) return;
    const labels = safeJsonParse('expense_by_category_labels');
    const data = toNumberArray(safeJsonParse('expense_by_category_data'));
    if (!labels.length || !data.length) return;
    new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels,
        datasets: [{
          data,
          backgroundColor: ['#0000cd', '#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16', '#f97316']
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom' },
          datalabels: {
            color: '#ffffff',
            font: { weight: 'bold', size: 12 },
            formatter: function(value, context) {
              const total = (context.dataset.data || []).reduce((a, b) => a + (Number(b) || 0), 0);
              const pct = total > 0 ? Math.round((Number(value) / total) * 100) : 0;
              return pct >= 5 ? pct + '%' : '';
            }
          },
          tooltip: { callbacks: { label: c => `${c.label}: ${(c.parsed || 0).toLocaleString('vi-VN')} VNĐ` } }
        }
      }
    });
  });

  // Top Employees Chart
  buildChart(function () {
    const ctx = document.getElementById('topEmployeesChart');
    if (!ctx) return;
    const labels = safeJsonParse('top_employees_names');
    const data = toNumberArray(safeJsonParse('top_employees_scores'));
    if (!labels.length || !data.length) return;
    new Chart(ctx, {
      type: 'bar',
      data: { labels, datasets: [{ label: 'Điểm hiệu suất', data, backgroundColor: '#0000cd' }] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: 'y',
        plugins: {
          legend: { display: false },
          datalabels: {
            anchor: 'end',
            align: 'right',
            color: '#0f172a',
            font: { weight: 'bold', size: 10 },
            formatter: function(value) {
              const v = Number(value) || 0;
              return v.toFixed(1);
            }
          },
          tooltip: { callbacks: { label: c => (c.parsed.x || 0).toFixed(1) + '/100' } }
        },
        scales: {
          x: {
            beginAtZero: true,
            max: 100,
            ticks: { callback: v => (v || 0) + '/100' }
          }
        }
      }
    });
  });
