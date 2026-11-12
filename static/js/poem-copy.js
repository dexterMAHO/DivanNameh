const tools = document.getElementById('copy-tools');

if (tools) {
  const verses = [...document.querySelectorAll('.reading-sheet .verse')];
  const treasury = document.querySelector('.treasury-text');
  const paragraphs = treasury ? [...treasury.querySelectorAll('[data-copy-paragraph]')] : [];
  const status = tools.querySelector('.copy-status');
  const fallback = document.getElementById('copy-fallback');
  const output = document.getElementById('copy-output');

  async function copy(rows, credit = false) {
    fallback.hidden = true;
    output.value = '';
    if (!rows.length) {
      status.textContent = 'ابتدا دست‌کم یک بیت انتخاب کنید.';
      return;
    }
    const body = rows.map(row => row.matches('[data-copy-paragraph]') ? row.textContent.trim() :
      [...row.querySelectorAll('.hemistich')].map(line => line.textContent.trim()).join('\n')).join('\n\n');
    const text = credit && treasury ? body + '\n\n' + treasury.dataset.copyCredit : body;
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

  const selection = document.getElementById('treasury-selection') || tools;
  const includeCredit = () => document.getElementById('copy-credit')?.checked;
  document.getElementById('copy-all').addEventListener('click', () => copy(verses.length ? verses : paragraphs));
  document.getElementById('copy-selected')?.addEventListener('click', () => {
    const selected = new Set([...selection.querySelectorAll('input[type="checkbox"]:checked')].map(input => input.value));
    copy(verses.filter(verse => selected.has(verse.dataset.position)), includeCredit());
  });
  document.getElementById('copy-with-options')?.addEventListener('click', () =>
    copy(verses.length ? verses : paragraphs, includeCredit()));
  tools.hidden = false;
}
