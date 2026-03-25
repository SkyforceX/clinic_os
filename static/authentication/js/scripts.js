document.addEventListener('DOMContentLoaded', function() {
    var msgBox = document.querySelector('.django-messages');
    if (msgBox) {
        setTimeout(function() {
            msgBox.style.transition = "opacity 0.7s";
            msgBox.style.opacity = "0";
            setTimeout(function() {
                if (msgBox && msgBox.parentNode) {
                    msgBox.parentNode.removeChild(msgBox);
                }
            }, 800);
        }, 4000); // 4 giây
    }
});
