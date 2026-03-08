document.addEventListener("DOMContentLoaded", function () {
    const departmentSelector = document.getElementById("departmentSelector");
    const departmentInput = document.getElementById("department-input");
    const departmentSearch = document.getElementById("department-search");
    const departmentItems = document.querySelectorAll(".department-item");
    const checkboxes = document.querySelectorAll('input[name="departments"]');

    // Mở/đóng dropdown
    if (departmentInput && departmentSelector) {
      departmentInput.addEventListener("click", function (e) {
        e.preventDefault();
        departmentSelector.classList.toggle("active");
        if (departmentSelector.classList.contains("active")) {
          setTimeout(() => {
            departmentSearch?.focus();
          }, 100);
        }
      });

      // Đóng dropdown khi click bên ngoài
      document.addEventListener("click", function (e) {
        if (!departmentSelector.contains(e.target)) {
          departmentSelector.classList.remove("active");
        }
      });

      // Ngăn đóng dropdown khi click vào dropdown container
      const dropdownContainer = departmentSelector.querySelector(
        ".department-checkbox-container"
      );
      if (dropdownContainer) {
        dropdownContainer.addEventListener("click", function (e) {
          e.stopPropagation();
        });
      }
    }

    // Tìm kiếm phòng ban
    if (departmentSearch) {
      departmentSearch.addEventListener("input", function (e) {
        const searchTerm = e.target.value.toLowerCase().trim();

        departmentItems.forEach((item) => {
          const departmentName = item.getAttribute("data-name") || "";
          const labelText =
            item
              .querySelector(".form-check-label")
              ?.textContent.toLowerCase() || "";

          if (
            departmentName.includes(searchTerm) ||
            labelText.includes(searchTerm)
          ) {
            item.style.display = "block";
          } else {
            item.style.display = "none";
          }
        });
      });
    }

    // Cập nhật input text khi chọn/bỏ chọn phòng ban
    function updateDepartmentInput() {
      const checked = Array.from(checkboxes).filter((cb) => cb.checked);
      const checkedNames = checked
        .map((cb) => {
          const label = document.querySelector(`label[for="${cb.id}"]`);
          return label
            ? label.querySelector("strong")?.textContent ||
                label.textContent.trim()
            : "";
        })
        .filter((name) => name);

      if (checkedNames.length > 0) {
        if (checkedNames.length === 1) {
          departmentInput.value = checkedNames[0];
        } else if (checkedNames.length <= 3) {
          departmentInput.value = checkedNames.join(", ");
        } else {
          departmentInput.value = `${checkedNames.slice(0, 3).join(", ")} và ${
            checkedNames.length - 3
          } phòng ban khác`;
        }
      } else {
        departmentInput.value = "";
        departmentInput.placeholder = "Chọn phòng ban...";
      }
    }

    // Lắng nghe sự kiện thay đổi checkbox
    checkboxes.forEach((checkbox) => {
      checkbox.addEventListener("change", function () {
        updateDepartmentInput();
      });
    });

    // Cập nhật lần đầu
    updateDepartmentInput();

    // Ngăn form submit khi nhấn Enter trong search input
    if (departmentSearch) {
      departmentSearch.addEventListener("keydown", function (e) {
        if (e.key === "Enter") {
          e.preventDefault();
        }
      });
    }

    // Required departments selector
    const requiredDepartmentSelector = document.getElementById("requiredDepartmentSelector");
    const requiredDepartmentInput = document.getElementById("required-department-input");
    const requiredDepartmentSearch = document.getElementById("required-department-search");
    const requiredDepartmentItems = document.querySelectorAll('#required-department-list .department-item');
    const requiredCheckboxes = document.querySelectorAll('input[name="required_departments"]');

    // Mở/đóng dropdown cho required departments
    if (requiredDepartmentInput && requiredDepartmentSelector) {
      requiredDepartmentInput.addEventListener("click", function (e) {
        e.preventDefault();
        requiredDepartmentSelector.classList.toggle("active");
        if (requiredDepartmentSelector.classList.contains("active")) {
          setTimeout(() => {
            requiredDepartmentSearch?.focus();
          }, 100);
        }
      });

      // Đóng dropdown khi click bên ngoài
      document.addEventListener("click", function (e) {
        if (!requiredDepartmentSelector.contains(e.target)) {
          requiredDepartmentSelector.classList.remove("active");
        }
      });

      // Tìm kiếm required departments
      if (requiredDepartmentSearch) {
        requiredDepartmentSearch.addEventListener("input", function () {
          const searchTerm = this.value.toLowerCase();
          requiredDepartmentItems.forEach((item) => {
            const name = item.dataset.name || "";
            if (name.includes(searchTerm)) {
              item.style.display = "block";
            } else {
              item.style.display = "none";
            }
          });
        });
      }

      // Cập nhật input text khi chọn required departments
      function updateRequiredDepartmentInput() {
        const checked = Array.from(requiredCheckboxes)
          .filter((cb) => cb.checked)
          .map((cb) => {
            const label = document.querySelector(
              `label[for="${cb.id}"]`
            );
            return label ? label.textContent.trim().split("\n")[0] : "";
          });
        if (checked.length > 0) {
          requiredDepartmentInput.value = checked.join(", ");
        } else {
          requiredDepartmentInput.value = "";
        }
      }

      // Lắng nghe thay đổi checkbox
      requiredCheckboxes.forEach((checkbox) => {
        checkbox.addEventListener("change", updateRequiredDepartmentInput);
      });

      // Khởi tạo giá trị ban đầu
      updateRequiredDepartmentInput();
    }

    // Format số tiền cho input Ngân sách dự kiến
    const estimatedBudgetInput = document.getElementById("id_estimated_budget");

    if (estimatedBudgetInput) {
      function formatNumber(value) {
        if (!value) return "";
        // Remove all non-digit characters except for a potential decimal point
        let cleanedValue = value.toString().replace(/[^\d.]/g, "");
        // Handle decimal part
        const parts = cleanedValue.split(".");
        let integerPart = parts[0];
        let decimalPart =
          parts.length > 1 ? "." + parts[1].substring(0, 2) : "";

        // Add commas to the integer part
        integerPart = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
        return integerPart + decimalPart;
      }

      function unformatNumber(value) {
        if (!value) return "";
        return value.toString().replace(/,/g, "");
      }

      // Format on initial load (for edit forms)
      if (estimatedBudgetInput.value) {
        estimatedBudgetInput.value = formatNumber(estimatedBudgetInput.value);
      }

      // Format on input
      estimatedBudgetInput.addEventListener("input", function (e) {
        const start = this.selectionStart;
        const end = this.selectionEnd;
        const oldLength = this.value.length;

        this.value = formatNumber(this.value);

        const newLength = this.value.length;
        const cursorOffset = newLength - oldLength;
        this.setSelectionRange(start + cursorOffset, end + cursorOffset);
      });

      // Unformat before form submission
      estimatedBudgetInput
        .closest("form")
        .addEventListener("submit", function () {
          if (estimatedBudgetInput) {
            estimatedBudgetInput.value = unformatNumber(
              estimatedBudgetInput.value
            );
          }
        });
    }
  });
