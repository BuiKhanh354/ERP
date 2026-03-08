// Format số tiền cho input Số tiền phân bổ
  const allocatedAmountInput = document.getElementById("id_allocated_amount");

  if (allocatedAmountInput) {
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
    if (allocatedAmountInput.value) {
      allocatedAmountInput.value = formatNumber(allocatedAmountInput.value);
    }

    // Format on input
    allocatedAmountInput.addEventListener("input", function (e) {
      const start = this.selectionStart;
      const end = this.selectionEnd;
      const oldLength = this.value.length;

      this.value = formatNumber(this.value);

      const newLength = this.value.length;
      const cursorOffset = newLength - oldLength;
      this.setSelectionRange(start + cursorOffset, end + cursorOffset);
    });

    // Unformat before form submission
    allocatedAmountInput
      .closest("form")
      .addEventListener("submit", function () {
        if (allocatedAmountInput) {
          allocatedAmountInput.value = unformatNumber(
            allocatedAmountInput.value
          );
        }
      });
  }
