import {verseElement} from './api.js';

const editor = document.getElementById('poem-editor');
const rows = document.getElementById('structured-rows');
const mode = editor.elements.input_mode;
const lineLayout = editor.elements.line_layout;
const bulk = document.getElementById('bulk-entry');
const bulkText = editor.elements.bulk_text;
const error = document.getElementById('editor-error');
const add = document.getElementById('add-verse');
const parse = document.getElementById('parse-verses');
const preview = document.getElementById('preview');
const minimum = Number(editor.dataset.minimum);
const digits = new Intl.NumberFormat('fa-IR', {useGrouping: false});
const draftKey = editor.dataset.draftKey;
const draftControls = document.getElementById('draft-controls');
const enabled = document.getElementById('draft-enabled');
const restore = document.getElementById('restore-draft');
const discard = document.getElementById('discard-draft');
const status = document.getElementById('draft-status');
const fields = [...editor.querySelectorAll('input, select, textarea')].filter(field =>
  !['password', 'hidden', 'search'].includes(field.type) &&
  !['hemistich_1', 'hemistich_2'].includes(field.name) && field.name);
let dirty = false;
let submitted = false;
let stored = null;
let saveTimer;

function rowValues() {
  return [...rows.children].map(row => [...row.querySelectorAll('input')].map(input => input.value));
}

function renumber() {
  [...rows.children].forEach((row, index) => {
    const number = digits.format(index + 1);
    row.querySelector('.row-number').textContent = number;
    row.querySelector('.first-label').textContent = (lineLayout.checked ? 'سطر ' : 'مصرع اول ردیف ') + number;
    const second = row.querySelector('.second-label');
    second.textContent = 'مصرع دوم ردیف ' + number + ' (اختیاری)';
    second.parentElement.hidden = lineLayout.checked && !second.parentElement.querySelector('input').value;
    const remove = row.querySelector('.remove-row');
    if (remove) {
      remove.hidden = index < minimum;
      remove.textContent = 'حذف ردیف ' + number;
    }
  });
}

function addRow(first = '', second = '') {
  const row = document.createElement('div');
  row.className = 'verse-input';
  const number = document.createElement('span');
  number.className = 'row-number';
  number.setAttribute('aria-hidden', 'true');
  row.append(number);
  [first, second].forEach((value, index) => {
    const label = document.createElement('label');
    const caption = document.createElement('span');
    caption.className = index ? 'second-label' : 'first-label';
    const input = document.createElement('input');
    input.name = 'hemistich_' + (index + 1);
    input.maxLength = 1000;
    input.value = value;
    label.append(caption, input);
    row.append(label);
  });
  const remove = document.createElement('button');
  remove.type = 'button';
  remove.className = 'remove-row text-button';
  row.append(remove);
  rows.append(row);
  return row;
}

function setRows(values) {
  rows.replaceChildren();
  for (const [first, second] of values) addRow(first, second);
  if (!rows.children.length) addRow();
  renumber();
}

function updateMode() {
  const structured = mode.value === 'structured';
  rows.hidden = !structured;
  add.hidden = !structured;
  bulk.hidden = structured;
  parse.hidden = false;
  document.getElementById('preview-button').hidden = false;
  renumber();
}

function snapshot() {
  return {
    revision: editor.dataset.revision,
    rows: rowValues(),
    fields: fields.map(field => [field.name, field.value, field.type === 'checkbox' ? field.checked : null]),
  };
}

function saveDraft() {
  if (!enabled.checked) return;
  try {
    stored = snapshot();
    localStorage.setItem(draftKey, JSON.stringify(stored));
    discard.hidden = false;
    status.textContent = 'پیش‌نویس در این مرورگر ذخیره شد.';
  } catch {
    status.textContent = 'مرورگر نتوانست پیش‌نویس را ذخیره کند.';
  }
}

function changed() {
  dirty = true;
  preview.hidden = true;
  clearTimeout(saveTimer);
  saveTimer = setTimeout(saveDraft, 250);
}

function report(message, field = error) {
  error.textContent = message;
  field.focus();
  if (field !== error) {
    field.setAttribute('aria-invalid', 'true');
    field.setAttribute('aria-describedby', error.id);
  }
}

function parsed() {
  if (mode.value === 'structured') {
    const values = rowValues().map(parts => parts.map(part => part.trim()));
    while (values.length > minimum && !values.at(-1).some(Boolean)) values.pop();
    return values;
  }
  const lines = bulkText.value.split(/[\n\r\v\f\x1c-\x1e\x85\u2028\u2029]+/u).map(line => line.trim()).filter(Boolean);
  if (lineLayout.checked) return lines.map(line => [line, '']);
  if (mode.value === 'pairs') {
    if (lines.length % 2) throw new Error('تعداد سطرها فرد است؛ سطر پایانی را کامل کنید.');
    return lines.filter((_, index) => index % 2 === 0).map((line, index) => [line, lines[index * 2 + 1]]);
  }
  return lines.map(line => {
    const separator = line.indexOf('|');
    return separator < 0 ? [line, ''] : [line.slice(0, separator).trim(), line.slice(separator + 1).trim()];
  });
}

function validated() {
  const values = parsed();
  if (values.length < Math.max(1, minimum) || values.length > 500) {
    throw new Error(minimum && values.length < minimum ? 'ردیف‌های موجود باید حفظ شوند.' : 'بین ۱ تا ۵۰۰ ردیف وارد کنید.');
  }
  const invalid = values.findIndex(([first, second]) =>
    !first || [...first].length > 1000 || [...second].length > 1000 || (lineLayout.checked && second));
  if (invalid >= 0) {
    const [first, second] = values[invalid];
    const message = lineLayout.checked && second ?
      'در چیدمان سطری مصرع دوم باید خالی بماند.' : 'متن اول الزامی است و هر مصرع حداکثر ۱۰۰۰ نویسه دارد.';
    const problem = new Error('ردیف ' + digits.format(invalid + 1) + ': ' + message);
    if (mode.value === 'structured') {
      problem.field = rows.children[invalid].querySelectorAll('input')[!first || [...first].length > 1000 ? 0 : 1];
    }
    throw problem;
  }
  error.textContent = '';
  return values;
}

function handleError(problem) {
  report(problem.message, problem.field || (mode.value === 'structured' ? error : bulkText));
}

try {
  stored = JSON.parse(localStorage.getItem(draftKey));
  if (stored && (!Array.isArray(stored.fields) || !Array.isArray(stored.rows))) stored = null;
  restore.hidden = discard.hidden = !stored;
  draftControls.open = Boolean(stored);
  draftControls.hidden = false;
} catch {
  // The editor works with storage disabled.
}
enabled.addEventListener('change', () => {
  if (enabled.checked) {
    if (!stored || restore.hidden || confirm('پیش‌نویس قبلی با متن فعلی جایگزین شود؟')) {
      restore.hidden = true;
      saveDraft();
    } else {
      enabled.checked = false;
    }
  }
});
restore.addEventListener('click', () => {
  const stale = stored.revision !== editor.dataset.revision;
  if (stale && !confirm('شعر پس از ذخیرهٔ پیش‌نویس تغییر کرده است. متن پیش‌نویس برای بازبینی در فرم بارگذاری شود؟')) return;
  if (!stale && dirty && !confirm('متن فعلی با پیش‌نویس جایگزین شود؟')) return;
  for (const [name, value, checked] of stored.fields) {
    const field = fields.find(input => input.name === name && (checked === null || input.value === value));
    if (field) {
      if (checked === null) field.value = value;
      else field.checked = checked;
    }
  }
  setRows(stored.rows);
  enabled.checked = true;
  restore.hidden = true;
  updateMode();
  changed();
  status.textContent = 'پیش‌نویس بازیابی شد.';
  editor.elements.poet_name.focus();
});
discard.addEventListener('click', () => {
  if (!confirm('پیش‌نویس ذخیره‌شده پاک شود؟')) return;
  try { localStorage.removeItem(draftKey); } catch { /* Storage may be unavailable. */ }
  stored = null;
  restore.hidden = discard.hidden = true;
  enabled.checked = false;
  enabled.focus();
  status.textContent = 'پیش‌نویس پاک شد.';
});
editor.addEventListener('input', event => {
  if (event.target.closest('#draft-controls,[data-tag-search]')) return;
  if (event.target.getAttribute('aria-describedby') === error.id) {
    event.target.removeAttribute('aria-invalid');
    event.target.removeAttribute('aria-describedby');
  }
  changed();
});
mode.addEventListener('change', updateMode);
lineLayout.addEventListener('change', updateMode);
add.addEventListener('click', () => {
  if (rows.children.length >= 500) {
    report('حداکثر ۵۰۰ ردیف مجاز است.');
    return;
  }
  const row = addRow();
  renumber();
  changed();
  row.querySelector('input').focus();
});
rows.addEventListener('click', event => {
  if (!event.target.matches('.remove-row')) return;
  const row = event.target.closest('.verse-input');
  const next = row.nextElementSibling || row.previousElementSibling;
  row.remove();
  renumber();
  changed();
  (next?.querySelector('input') || add).focus();
});
parse.addEventListener('click', () => {
  try {
    const values = validated();
    if (rowValues().some(parts => parts.some(part => part.trim())) &&
        !confirm('ردیف‌های فعلی با متن چسبانده‌شده جایگزین شوند؟')) return;
    setRows(values);
    mode.value = 'structured';
    updateMode();
    changed();
    rows.querySelector('input').focus();
  } catch (problem) {
    handleError(problem);
  }
});
document.getElementById('preview-button').addEventListener('click', () => {
  try {
    preview.replaceChildren(...validated().map(([first, second], index) =>
      verseElement(first, second, index + 1, lineLayout.checked)));
    preview.hidden = false;
    preview.focus();
  } catch (problem) {
    handleError(problem);
  }
});
const tagSearch = document.getElementById('tag-search');
tagSearch.parentElement.hidden = false;
tagSearch.addEventListener('input', () => {
  const normalize = value => value.replaceAll('ك', 'ک').replaceAll('ي', 'ی').replace(/[\s\u200c]+/gu, '');
  document.querySelectorAll('#id_tags > div').forEach(row =>
    row.hidden = !normalize(row.textContent).includes(normalize(tagSearch.value)));
});
editor.addEventListener('submit', event => {
  try {
    validated();
    saveDraft();
    submitted = true;
  } catch (problem) {
    event.preventDefault();
    handleError(problem);
  }
});
window.addEventListener('beforeunload', event => {
  if (dirty && !submitted) {
    event.preventDefault();
    event.returnValue = '';
  }
});
window.addEventListener('pagehide', () => {
  clearTimeout(saveTimer);
  if (dirty && !submitted) saveDraft();
});
window.addEventListener('pageshow', () => { submitted = false; });
updateMode();
