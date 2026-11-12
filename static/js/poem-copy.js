const tools = document.getElementById('copy-tools');
const sheet = document.querySelector('.reading-sheet');

if (tools && sheet) {
  const status = tools.querySelector('.copy-status');
  const fallback = document.getElementById('copy-fallback');
  const output = document.getElementById('copy-output');
  const choices = sheet.querySelectorAll('input[data-copy-verse], input[name=verse]');
  const verses = [...sheet.querySelectorAll('.verse')];
  const paragraphs = [...sheet.querySelectorAll('[data-copy-paragraph]')];

  async function copy(rows) {
    fallback.hidden = true;
    output.value = '';
    if (!rows.length) {
      status.textContent = 'ابتدا بخشی از متن را انتخاب کنید.';
      return;
    }
    const lines = rows.map(row => row.matches('[data-copy-paragraph]') ? row.textContent.trim() :
      [...row.querySelectorAll('.hemistich')].map(line => line.textContent.trim()).join('\n'));
    const credit = document.getElementById('copy-credit').checked;
    const text = lines.join(rows[0].classList.contains('verse-line') ? '\n' : '\n\n') +
      (credit && sheet.dataset.copyCredit ? '\n\n' + sheet.dataset.copyCredit : '');
    try {
      await navigator.clipboard.writeText(text);
      status.textContent = 'متن شعر کپی شد.';
    } catch {
      status.textContent = 'متن را از کادر زیر کپی کنید.';
      fallback.hidden = false;
      output.value = text;
      output.focus();
      output.select();
    }
  }

  document.getElementById('copy-all').addEventListener('click', () => copy(verses.length ? verses : paragraphs));
  document.getElementById('copy-selected')?.addEventListener('click', () => {
    const selected = new Set([...choices].filter(input => input.checked).map(input => input.value));
    copy(verses.filter(verse => selected.has(verse.dataset.position)));
  });
  sheet.querySelectorAll('.copy-choice').forEach(choice => choice.hidden = false);
  tools.hidden = false;
}

const resume = document.querySelector('.resume-reading');
if (resume && sheet?.dataset.readingKey) {
  const key = 'divan-reading-' + sheet.dataset.readingKey;
  const lines = [...sheet.querySelectorAll('.verse[data-position]')];
  try {
    const previous = localStorage.getItem(key);
    const line = lines.find(row => row.dataset.position === previous);
    if (line && line !== lines[0]) {
      resume.hidden = false;
      resume.addEventListener('click', () => {
        line.tabIndex = -1;
        line.focus({preventScroll: true});
        line.scrollIntoView({block: 'start'});
      });
    }
    let moved = false;
    window.addEventListener('scroll', () => { moved = true; }, {passive: true});
    window.addEventListener('pagehide', () => {
      if (!moved) return;
      const current = lines.find(row => {
        const box = row.getBoundingClientRect();
        return box.bottom > 20 && box.top < window.innerHeight * 0.65;
      });
      if (current) {
        try { localStorage.setItem(key, current.dataset.position); } catch { /* Storage can be disabled. */ }
      }
    });
  } catch {
    // Reading remains available when storage is disabled.
  }
}
