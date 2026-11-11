const tools = document.getElementById('copy-tools');

if (tools) {
  const verses = [...document.querySelectorAll('.reading-sheet .verse')];
  const status = tools.querySelector('.copy-status');
  const fallback = document.getElementById('copy-fallback');
  const output = document.getElementById('copy-output');

  async function copy(rows) {
    fallback.hidden = true;
    output.value = '';
    if (!rows.length) {
      status.textContent = 'ابتدا دست‌کم یک بیت انتخاب کنید.';
      return;
    }
    const text = rows.map(row => [...row.querySelectorAll('.hemistich')]
      .map(hemistich => hemistich.textContent.trim()).join('\n')).join('\n\n');
    try {
      await navigator.clipboard.writeText(text);
      status.textContent = 'متن شعر کپی شد.';
    } catch {
      status.textContent = 'متن آماده است. آن را از کادر زیر کپی کنید.';
      fallback.hidden = false;
      output.value = text;
      output.focus();
      output.select();
    }
  }

  document.getElementById('copy-all').addEventListener('click', () => copy(verses));
  document.getElementById('copy-selected').addEventListener('click', () => {
    const selected = new Set([...tools.querySelectorAll('input:checked')].map(input => input.value));
    copy(verses.filter(verse => selected.has(verse.dataset.position)));
  });
  tools.hidden = false;
}
