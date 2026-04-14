document.addEventListener("DOMContentLoaded", function() {
    // Fetch data from data.json
    fetch(LOAD_FIXTURE_URL)
      .then(response => response.json())
      .then(data => {
        renderCheckboxGroups(data);
      })
      .catch(error => console.error('Error loading data:', error));
});
  
function renderCheckboxGroups(data) {
  const checkboxGroups = document.getElementById('checkboxGroups');
  checkboxGroups.innerHTML = '';

  // Gom nhóm theo ID
  const groupsById = {};
  data.forEach(group => {
    groupsById[group.id] = group;
  });

  // Cấu hình nhóm theo cột
  const columnGroups = [
    ['group1','group6'], ['group2'], ['group3'], // Cột 1,2,3
    ['group4', 'group5'],           // Cột 4
    ['group7']            // Cột 5
  ];

  // Tạo 3 cột
  columnGroups.forEach(columnIds => {
    const columnDiv = document.createElement('div');
    columnDiv.classList.add('col-group');

    columnIds.forEach(groupId => {
      const group = groupsById[groupId];
      if (!group) return;

      const groupDiv = document.createElement('div');
      groupDiv.classList.add('group');
      groupDiv.dataset.group = group.id;

      const groupTitle = document.createElement('h3');
      groupTitle.textContent = group.name;
      groupDiv.appendChild(groupTitle);

      const checkboxList = document.createElement('div');
      checkboxList.classList.add('checkbox-list');

      group.items.forEach(item => {
        const label = document.createElement('label');
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.value = item.name;
        checkbox.dataset.hidden = item.hidden;
        label.appendChild(checkbox);
        label.appendChild(document.createTextNode(item.name));
        checkboxList.appendChild(label);
      });

      groupDiv.appendChild(checkboxList);
      columnDiv.appendChild(groupDiv);
    });

    checkboxGroups.appendChild(columnDiv);
  });
 // Sortable
  document.querySelectorAll('.checkbox-list').forEach(list => {
    Sortable.create(list, {
      animation: 150,
      ghostClass: 'sortable-ghost',
      onEnd: updateTextareas
    });
  });
  
// Add event listeners for the checkboxes
document.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.addEventListener('change', updateTextareas));

// Search functionality
document.getElementById('search').addEventListener('input', function () {
const keyword = this.value.toLowerCase();
const labels = document.querySelectorAll('.group label');
labels.forEach(label => {
  const text = label.textContent.toLowerCase();
  label.style.display = text.includes(keyword) ? 'block' : 'none';
});
});
  
// Group filter functionality
document.getElementById('groupFilter').addEventListener('change', function () {
const val = this.value;
document.querySelectorAll('.group').forEach(group => {
  group.style.display = val === 'all' || group.dataset.group === val ? 'block' : 'none';
});
});
}
  
function updateTextareas() {
  const selected = Array.from(document.querySelectorAll('input[type="checkbox"]:checked'));
  const textarea1 = document.getElementById('textarea1');
  const textarea2 = document.getElementById('textarea2');

  textarea1.value = selected.map(cb => "- " + cb.value).join('\n');
  textarea2.value = selected.map(cb => `- ${cb.value}: ${cb.dataset.hidden}`).join('\n\n');
    // Gọi hàm auto-resize
  autoResizeTextarea(textarea1);
  autoResizeTextarea(textarea2);
}

function toggleDarkMode() {
document.body.classList.toggle('dark');
}

function clearAll() {
  document.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = false);
  updateTextareas();
}

function copyToClipboard(id, btn) {
  const textarea = document.getElementById(id);
  textarea.select();
  document.execCommand("copy");
  const original = btn.textContent;
  btn.textContent = "✅ Đã sao chép!";
  setTimeout(() => btn.textContent = original, 1500);
}

function autoResizeTextarea(textarea) {
  textarea.style.height = 'auto'; // reset trước
  textarea.style.height = textarea.scrollHeight + 'px'; // set theo nội dung
}