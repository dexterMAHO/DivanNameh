const form = document.getElementById('post-editor');
if (form) {
  const mode = form.elements.input_mode;
  const free = form.elements.line_layout;
  const rows = document.getElementById('post-rows');
  const add = document.getElementById('post-add-row');
  const update = () => {
    rows.hidden = mode.value !== 'structured';
    document.getElementById('post-bulk').hidden = mode.value === 'structured';
    document.getElementById('post-input-help').textContent = free.checked ? 'شعر نو: هر سطر را در یک خط بنویسید.' : mode.value === 'pairs' ? 'هر مصرع در یک خط؛ هر دو خط یک بیت می‌شود.' : 'هر خط یک بیت؛ دو مصرع را با | جدا کنید.';
    rows.querySelectorAll('[name=hemistich_2]').forEach(input => {input.closest('label').hidden = free.checked;});
  };
  add.hidden = false;
  add.addEventListener('click', () => {
    if (rows.querySelectorAll('.post-verse-row').length >= 500) return;
    const row = rows.querySelector('.post-verse-row').cloneNode(true);
    row.querySelectorAll('input').forEach(input => input.value = '');
    rows.insertBefore(row, add);
    update();
    row.querySelector('input').focus();
  });
  rows.addEventListener('click', event => {
    const button = event.target.closest('[data-remove-row]');
    if (!button) return;
    if (rows.querySelectorAll('.post-verse-row').length > 1) button.closest('.post-verse-row').remove();
    else button.closest('.post-verse-row').querySelectorAll('input').forEach(input => input.value = '');
  });
  mode.addEventListener('change', update);
  free.addEventListener('change', update);
  update();
}
