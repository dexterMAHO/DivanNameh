import {verseElement} from './api.js';
const editor = document.getElementById('poem-editor');
if (editor) {
  const rows = document.getElementById('structured-rows');
  const mode = document.getElementById('id_input_mode');
  const bulk = document.getElementById('bulk-entry');
  const error = document.getElementById('editor-error');
  const add = document.getElementById('add-verse');
  function updateMode() {
    const structured = mode.value === 'structured';
    rows.hidden = !structured; add.hidden = !structured; bulk.hidden = structured;
  }
  mode.addEventListener('change', updateMode); updateMode();
  function renumber() { [...rows.children].forEach((row, i) => row.querySelector('.row-number').textContent = i + 1); }
  function addRow(first = '', second = '') {
    if (rows.children.length >= 500) throw new Error('حداکثر ۵۰۰ بیت در هر شعر مجاز است.');
    const row = document.createElement('div'); row.className = 'verse-input';
    const number = document.createElement('span'); number.className = 'row-number'; row.append(number);
    [first, second].forEach((value, index) => {
      const label = document.createElement('label'); label.textContent = index ? 'مصرع دوم (اختیاری)' : 'مصرع اول';
      const input = document.createElement('input'); input.name = `hemistich_${index + 1}`; input.maxLength = 1000; input.value = value;
      label.append(input); row.append(label);
    });
    const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'remove-row text-button'; remove.textContent = 'حذف ردیف'; row.append(remove);
    rows.append(row); renumber(); return row;
  }
  add.addEventListener('click', () => {
    try { const row = addRow(); row.querySelector('input').focus(); } catch (e) { error.textContent = e.message; }
  });
  rows.addEventListener('click', event => {
    if (!event.target.matches('.remove-row')) return;
    const row = event.target.closest('.verse-input');
    const next = row.nextElementSibling || row.previousElementSibling;
    row.remove(); renumber();
    (next?.querySelector('input') || add).focus();
  });
  function parsed() {
    if (mode.value === 'structured') return [...rows.children].map(row => [...row.querySelectorAll('input')].map(i => i.value.trim()));
    const lines = document.getElementById('id_bulk_text').value.split('\n').map(x => x.trim()).filter(Boolean);
    if (mode.value === 'pairs') {
      if (lines.length % 2) throw new Error('تعداد سطرها فرد است؛ سطر پایانی را اصلاح کنید.');
      return lines.filter((_, i) => i % 2 === 0).map((line, i) => [line, lines[i * 2 + 1]]);
    }
    return lines.map(line => { const at = line.indexOf('|'); return at < 0 ? [line, ''] : [line.slice(0, at).trim(), line.slice(at + 1).trim()]; });
  }
  function validated() {
    const values = parsed();
    if (!values.length || values.length > 500 || values.some(([a,b]) => !a || a.length > 1000 || b.length > 1000)) throw new Error('۱ تا ۵۰۰ بیت با مصرع اول غیرخالی و حداکثر ۱۰۰۰ نویسه برای هر مصرع وارد کنید.');
    error.textContent = ''; return values;
  }
  document.getElementById('parse-verses').addEventListener('click', () => {
    try { const values = validated(); rows.replaceChildren(); values.forEach(([a,b]) => addRow(a,b)); mode.value = 'structured'; updateMode(); }
    catch (e) { error.textContent = e.message; }
  });
  document.getElementById('preview-button').addEventListener('click', () => {
    try { const values = validated(); const preview = document.getElementById('preview'); preview.replaceChildren(...values.map(([a,b], i) => verseElement(a,b,i + 1))); preview.hidden = false; }
    catch (e) { error.textContent = e.message; }
  });
  document.getElementById('tag-search').addEventListener('input', event => {
    const normalize = s => s.replaceAll('ك','ک').replaceAll('ي','ی').trim();
    document.querySelectorAll('#id_tags > div').forEach(row => row.hidden = !normalize(row.textContent).includes(normalize(event.target.value)));
  });
  editor.addEventListener('submit', event => {
    try { validated(); editor.querySelector('[type=submit]').disabled = true; }
    catch (e) { event.preventDefault(); error.textContent = e.message; error.scrollIntoView(); }
  });
}
