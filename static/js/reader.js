/* The reading toolbar of the poem page.

   Everything here is an enhancement over a page that already reads correctly:
   the controls stay hidden until this module runs, so a reader without
   JavaScript sees the account-wide size selector instead of dead buttons.
   Size and column width are per reader and per browser; they are owned by
   appearance.js, which also restores them before the first paint. */

const sheet = document.querySelector('.reading-sheet');
const status = document.getElementById('reader-status');
const digits = new Intl.NumberFormat('fa-IR', {useGrouping: false});
const percent = value => digits.format(value) + '٪';

function announce(message) {
  if (status) status.textContent = message;
}

/* ---------- Reading progress ---------- */
const bar = document.getElementById('reading-progress-bar');
const barText = document.getElementById('reading-progress-text');
if (sheet && bar && barText) {
  let queued = false;
  const update = () => {
    queued = false;
    const box = sheet.getBoundingClientRect();
    // How far the viewport's reading line has travelled through the poem.
    const travelled = Math.min(box.height, Math.max(0, window.innerHeight * 0.6 - box.top));
    const share = box.height > 0 ? Math.round((travelled / box.height) * 100) : 0;
    bar.style.inlineSize = share + '%';
    barText.textContent = percent(share);
  };
  const schedule = () => {
    if (queued) return;
    queued = true;
    requestAnimationFrame(update);
  };
  addEventListener('scroll', schedule, {passive: true});
  addEventListener('resize', schedule, {passive: true});
  update();
}

/* ---------- Size, column width, print ---------- */
const appearance = window.divanAppearance;
const controls = document.getElementById('reader-controls');
if (appearance && controls) {
  controls.hidden = false;
  // The toolbar now covers poem size, so the account-wide selector would be a
  // duplicate control. It stays in the DOM as the no-JavaScript fallback.
  document.body.classList.add('has-reader-tools');
  const value = document.getElementById('scale-value');
  const showScale = scale => { value.textContent = percent(scale); };
  showScale(appearance.scale());

  const step = direction => {
    const {value: scale, stored} = appearance.setScale(appearance.scale() + direction * 5);
    showScale(scale);
    announce(stored ? `اندازهٔ شعر ${percent(scale)} شد و در این مرورگر ذخیره شد.`
                    : `اندازهٔ شعر ${percent(scale)} شد؛ ذخیره‌سازی مرورگر در دسترس نیست.`);
  };
  document.getElementById('scale-down').addEventListener('click', () => step(-1));
  document.getElementById('scale-up').addEventListener('click', () => step(1));

  const width = document.getElementById('reading-width');
  const showWidth = on => width.setAttribute('aria-pressed', String(on));
  showWidth(appearance.wide());
  width.addEventListener('click', () => {
    const {value: wide, stored} = appearance.setWide(!appearance.wide());
    showWidth(wide);
    announce(`${wide ? 'ستون خواندن پهن شد' : 'ستون خواندن به عرض معمول بازگشت'}${stored ? ' و ذخیره شد.' : '؛ ذخیره‌سازی مرورگر در دسترس نیست.'}`);
  });

  document.getElementById('print-poem').addEventListener('click', () => window.print());
}

/* ---------- Focus mode ---------- */
/* Hides everything but the poem itself. Escape leaves, so the reader is never
   trapped, and the toggle keeps the focus ring where it was. */
const focusToggle = document.getElementById('focus-mode');
if (focusToggle) {
  const setFocus = on => {
    document.body.classList.toggle('focus-mode', on);
    focusToggle.setAttribute('aria-pressed', String(on));
    announce(on ? 'حالت تمرکز روشن شد؛ برای خروج کلید Esc را بزنید.' : 'حالت تمرکز خاموش شد.');
  };
  focusToggle.addEventListener('click', () => setFocus(!document.body.classList.contains('focus-mode')));
  addEventListener('keydown', event => {
    if (event.key === 'Escape' && document.body.classList.contains('focus-mode')) {
      setFocus(false);
      focusToggle.focus();
    }
  });
}

/* ---------- Copy one verse ---------- */
/* The bulk copy panel handles whole poems and selections; this is the shortcut
   for the single verse a reader is looking at. */
for (const button of document.querySelectorAll('[data-copy-verse-now]')) {
  const row = sheet?.querySelector(`.verse[data-position="${button.dataset.copyVerseNow}"]`);
  if (!row) continue;
  button.hidden = false;
  button.addEventListener('click', async () => {
    const text = [...row.querySelectorAll('.hemistich')].map(line => line.textContent.trim()).join('\n');
    const feedback = button.parentElement.querySelector('[role="status"]');
    try {
      await navigator.clipboard.writeText(text);
      announce('بیت رونوشت شد.');
      if (feedback) feedback.textContent = 'رونوشت شد.';
    } catch {
      announce('رونوشت خودکار ممکن نشد؛ متن بیت انتخاب شد تا دستی کپی کنید.');
      const range = document.createRange();
      range.selectNodeContents(row);
      getSelection().removeAllRanges();
      getSelection().addRange(range);
    }
  });
}

/* ---------- Send a verse to the range form ---------- */
/* When the reader has an operation password, a verse cannot be memorised in one
   click. Instead of repeating the password field beside every verse, the link
   preselects that verse in the study panel, which already asks for it once. */
for (const link of document.querySelectorAll('[data-memorize-verse]')) {
  link.addEventListener('click', () => {
    const panel = document.getElementById('study-range');
    const form = panel?.querySelector('.range-form');
    if (!form) return;
    panel.open = true;
    for (const name of ['start_verse_id', 'end_verse_id']) {
      form.elements[name].value = link.dataset.memorizeVerse;
      form.elements[name].dispatchEvent(new Event('change', {bubbles: true}));
    }
    const password = form.elements.action_password;
    (password || form.querySelector('button')).focus();
  });
}
