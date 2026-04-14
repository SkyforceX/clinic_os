(function () {
  const form = document.getElementById("issueContractForm");
  const submitBtn = document.getElementById("issueContractBtn");
  const overlay = document.getElementById("issueProgressOverlay");
  const bar = document.getElementById("issueProgressBar");
  const percent = document.getElementById("issueProgressPercent");
  const statusText = document.getElementById("issueProgressStatus");
  const steps = Array.from(document.querySelectorAll("#issueProgressSteps li"));

  if (!form || !submitBtn || !overlay || !bar || !percent || !statusText) {
    return;
  }

  let progressValue = 0;
  let timer = null;
  let isSubmitting = false;

  const milestones = [
    { until: 18, step: 1, text: "Đang chuẩn bị dữ liệu hợp đồng..." },
    { until: 52, step: 2, text: "Đang tạo file DOCX..." },
    { until: 84, step: 3, text: "Đang chuyển đổi sang PDF..." },
    { until: 95, step: 4, text: "Đang hoàn tất phát hành tài liệu..." },
  ];

  function renderProgress(value) {
    bar.style.width = value + "%";
    percent.textContent = value + "%";

    let activeStep = 1;
    let activeText = milestones[0].text;

    for (const item of milestones) {
      if (value <= item.until) {
        activeStep = item.step;
        activeText = item.text;
        break;
      }
      activeStep = item.step;
      activeText = item.text;
    }

    statusText.textContent = activeText;

    steps.forEach((el) => {
      const stepNum = Number(el.dataset.step || "0");
      el.classList.remove("active", "done");

      if (stepNum < activeStep) {
        el.classList.add("done");
      } else if (stepNum === activeStep) {
        el.classList.add("active");
      }
    });
  }

  function showOverlay() {
    overlay.classList.add("show");
    overlay.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
  }

  function disableActionArea() {
    submitBtn.disabled = true;
    submitBtn.innerHTML = "⏳ Đang phát hành...";

    document.querySelectorAll(".no-print a, .no-print button").forEach((el) => {
      if (el !== submitBtn) {
        el.classList.add("btn-loading-disabled");
        el.setAttribute("tabindex", "-1");
        el.setAttribute("aria-disabled", "true");
        el.style.pointerEvents = "none";
      }
    });
  }

  function startFakeProgress() {
    renderProgress(6);

    timer = window.setInterval(() => {
      if (progressValue < 18) {
        progressValue += 3;
      } else if (progressValue < 52) {
        progressValue += 2;
      } else if (progressValue < 84) {
        progressValue += 1;
      } else if (progressValue < 95) {
        progressValue += 0.5;
      }

      progressValue = Math.min(95, Math.round(progressValue));
      renderProgress(progressValue);

      if (progressValue >= 95) {
        window.clearInterval(timer);
      }
    }, 320);
  }

  form.addEventListener("submit", function (event) {
    if (isSubmitting) {
      event.preventDefault();
      return;
    }

    const ok = window.confirm("Phát hành hợp đồng PDF? Bản phát hành cũ sẽ bị thay thế.");
    if (!ok) {
      event.preventDefault();
      return;
    }

    isSubmitting = true;
    progressValue = 6;

    showOverlay();
    disableActionArea();
    startFakeProgress();
  });

  window.addEventListener("pageshow", function () {
    if (!isSubmitting) return;

    if (timer) {
      window.clearInterval(timer);
    }

    renderProgress(100);
    statusText.textContent = "Đã hoàn tất. Đang cập nhật giao diện...";
  });
})();