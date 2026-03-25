// CSRF cho fetch
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
const csrftoken = getCookie('csrftoken');

function errorToast(msg) {
// show toast báo lỗi
    var toastEl = document.getElementById('successToast');
    var toast = new bootstrap.Toast(toastEl, { delay: 3000 });
    document.getElementById('toastMessage').textContent = "Có lỗi: " + msg;
    toastEl.classList.remove('bg-success');
    toastEl.classList.add('bg-danger');
    toast.show();
// Đổi lại màu thành công nếu lưu lại lần khác
    toastEl.classList.remove('bg-danger');
    toastEl.classList.add('bg-success');
}

function successToast(msg) {
// Show Bootstrap toast
    var toastEl = document.getElementById('successToast');
    var toast = new bootstrap.Toast(toastEl, { delay: 2200 });
    document.getElementById('toastMessage').textContent = msg;
    toast.show();
}

document.getElementById('sync-form').addEventListener('submit', function(e) {
    e.preventDefault();
    const from_date = document.getElementById('from_date').value;
    const to_date = document.getElementById('to_date').value;

    fetch(API_SYNC_PATIENT_URL, {
        method: "POST",
        headers: {
            'X-CSRFToken': csrftoken,
            'Accept': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: new URLSearchParams({
            'from_date': from_date,
            'to_date': to_date,
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            // Cập nhật dòng "Cập nhật lần cuối"
            document.getElementById('last-sync').innerHTML =
                'Cập nhật lần cuối: <b>' + data.last_synced + '</b>';
            successToast('Đồng bộ thành công: ' + data.created + ' BN mới, ' + data.updated + ' BN cập nhật!');
        } else {
            errorToast('Có lỗi khi đồng bộ!');
        }
    })
    .catch(() => errorToast('Có lỗi kết nối!'));
});