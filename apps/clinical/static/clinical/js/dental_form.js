document.addEventListener('DOMContentLoaded', function() {
  const form = document.querySelector('#dental-exam-form');   // hoặc chọn form cụ thể của bạn
  const dobDisplay = document.getElementById('dob_display');
  const dobHidden = document.getElementById('dob');

  // Khi submit form → chuyển định dạng
  form.addEventListener('submit', function(e) {
    const parts = dobDisplay.value.split('/');
    if (parts.length === 3) {
      const [day, month, year] = parts;
      // Kiểm tra định dạng cơ bản
      if (day.length === 2 && month.length === 2 && year.length === 4) {
        dobHidden.value = `${year}-${month}-${day}`; // Django date format
      }
    }
  });
});

