import {announce, request, verseElement} from './api.js';
import './editor.js';
import './poem-copy.js';
import './treasury-layout.js';
for (const form of document.querySelectorAll('form[data-ajax],form[data-favorite]')) {
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const button = form.querySelector('button'); if (button.disabled) return;
    button.disabled = true;
    try {
      const data = await request(form.action, form); announce(data.message);
      if (data.remaining_due_count !== undefined) document.querySelectorAll('.count').forEach(el => el.textContent = data.remaining_due_count);
      const memorize = form.closest('[data-memorize-options]');
      if (memorize) {
        memorize.querySelector('h2').textContent = 'در فهرست حفظ شماست';
        memorize.querySelectorAll('form, details').forEach(control => control.remove());
        document.querySelectorAll('.verse.selected').forEach(row => row.classList.remove('selected'));
        const listLink = memorize.querySelector('a');
        listLink.focus();
      }
      if (form.hasAttribute('data-favorite')) {
        button.setAttribute('aria-label', `${data.favorite ? 'برداشتن نشان' : 'افزودن به'} شاه‌بیت ${button.dataset.position}`);
        button.setAttribute('aria-pressed', String(data.favorite));
        form.action = data.favorite ? form.dataset.remove : form.dataset.add;
      }
    } catch (error) { announce(error.message, true); }
    finally { button.disabled = false; }
  });
}
for (const form of document.querySelectorAll('.range-form')) {
  const selects = [...form.querySelectorAll('select')];
  const update = () => {
    const [start, end] = selects.map(s => Number(s.selectedOptions[0].dataset.position));
    form.querySelector('.selection-count').textContent = end < start ? 'بیت پایانی باید پس از بیت آغازین باشد.' : `${end - start + 1} بیت انتخاب شده`;
    for (const row of document.querySelectorAll('[data-position].verse')) row.classList.toggle('selected', Number(row.dataset.position) >= start && Number(row.dataset.position) <= end);
  };
  selects.forEach(s => s.addEventListener('change', update));
  form.closest('details').addEventListener('toggle', () => {
    if (form.closest('details').open) update();
    else document.querySelectorAll('.verse.selected').forEach(row => row.classList.remove('selected'));
  });
}
const answer = document.getElementById('review-answer');
if (answer) {
  const buttons = [...answer.querySelectorAll('button')];
  buttons.forEach(b => b.disabled = true);
  answer.addEventListener('toggle', () => {
    answer.querySelector('summary').setAttribute('aria-expanded', String(answer.open));
    buttons.forEach(b => b.disabled = !answer.open);
  });
  document.getElementById('rating-form').addEventListener('submit', event => {
    // Preserve the selected submitter when disabling the buttons.
    const input = document.createElement('input'); input.type = 'hidden'; input.name = 'rating'; input.value = event.submitter.value;
    event.target.append(input); buttons.forEach(b => b.disabled = true);
  });
}
const discovery = document.getElementById('discover-form');
if (discovery) discovery.addEventListener('submit', async event => {
  event.preventDefault(); const button = discovery.querySelector('button'); button.disabled = true;
  try {
    const url = new URL(discovery.dataset.api, location.origin); url.searchParams.set('exclude_id', discovery.elements.exclude_id.value);
    const {poem} = await request(url);
    if (!poem) { announce('شعری برای نمایش وجود ندارد.'); return; }
    document.getElementById('discover-poet').textContent = poem.poet_name;
    document.getElementById('discover-title').textContent = poem.title;
    document.getElementById('discover-detail').href = poem.detail_url;
    document.getElementById('discover-verses').replaceChildren(...poem.verses.map(v => verseElement(v.hemistich_1, v.hemistich_2, v.position, poem.line_layout)));
    const same = discovery.elements.exclude_id.value === String(poem.id);
    discovery.elements.exclude_id.value = poem.id;
    document.getElementById('discovery').focus(); announce(same ? 'فعلاً همین یک شعر در دفتر شماست.' : 'شعر تازه‌ای از دفتر انتخاب شد.');
  } catch (error) { announce(error.message, true); } finally { button.disabled = false; }
});

const navToggle = document.getElementById('nav-toggle');
if (navToggle) {
  document.body.classList.add('has-js');
  const sidebar = document.querySelector('.sidebar');
  const setOpen = open => {
    navToggle.setAttribute('aria-expanded', String(open));
    sidebar.classList.toggle('mobile-open', open);
  };
  navToggle.addEventListener('click', () => setOpen(navToggle.getAttribute('aria-expanded') !== 'true'));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && navToggle.getAttribute('aria-expanded') === 'true') {
      setOpen(false);
      navToggle.focus();
    }
  });
  document.addEventListener('click', event => {
    if (!sidebar.contains(event.target) && !navToggle.contains(event.target)) setOpen(false);
  });
  matchMedia('(max-width: 1024px)').addEventListener('change', () => setOpen(false));
}

const treasury = document.getElementById('treasury-selection');
treasury?.addEventListener('submit', async event => {
  const button = event.submitter;
  if (!button) return;
  if (button.value === 'library' && !treasury.querySelector('input[name="verse"]:checked')) {
    event.preventDefault();
    treasury.querySelector('input[name="verse"]').focus();
    announce('ابتدا دست‌کم یک بیت انتخاب کنید.', true);
    return;
  }
  if (!button.matches('.treasury-favorite')) return;
  event.preventDefault();
  const status = button.parentElement.querySelector('[role="status"]');
  const saving = request(treasury.getAttribute('action'), treasury, button);
  button.disabled = true;
  try {
    const data = await saving;
    const position = button.value.split(':')[1];
    button.value = `${data.favorite ? 'unfavorite' : 'favorite'}:${position}`;
    button.setAttribute('aria-pressed', String(data.favorite));
    status.textContent = data.message;
  } catch (error) {
    status.textContent = error.message;
  } finally {
    button.disabled = false;
  }
});

const themeForm = document.getElementById('header-theme');
themeForm?.addEventListener('submit', async event => {
  event.preventDefault();
  const button = themeForm.querySelector('button');
  const root = document.documentElement;
  const dark = root.dataset.theme === 'dark' ||
    (root.dataset.theme === 'auto' && matchMedia('(prefers-color-scheme: dark)').matches);
  themeForm.elements.theme.value = dark ? 'light' : 'dark';
  button.disabled = true;
  try {
    const data = await request(themeForm.action, themeForm);
    root.dataset.theme = data.theme;
    document.dispatchEvent(new CustomEvent('theme-saved', {detail: data.theme}));
  } catch (error) {
    announce(error.message, true);
  } finally {
    button.disabled = false;
  }
});

// Preview is temporary; only a successful server form submission persists it.
const appearanceForm = document.getElementById('appearance-form');
if (appearanceForm) {
  const root = document.documentElement;
  const saved = {theme: root.dataset.theme, palette: root.dataset.palette};
  const reset = document.getElementById('appearance-reset');
  const status = document.getElementById('appearance-status');
  const preview = () => {
    root.dataset.theme = appearanceForm.elements.theme.value;
    root.dataset.palette = appearanceForm.elements.palette.value;
    const changed = root.dataset.theme !== saved.theme || root.dataset.palette !== saved.palette;
    reset.hidden = !changed;
    status.textContent = changed ? 'این یک پیش‌نمایش است؛ برای نگهداری انتخاب، «ذخیرهٔ ظاهر» را بزنید.' : '';
  };
  appearanceForm.addEventListener('change', preview);
  reset.addEventListener('click', () => {
    appearanceForm.elements.theme.value = saved.theme;
    appearanceForm.elements.palette.value = saved.palette;
    preview();
  });
  document.addEventListener('theme-saved', event => {
    saved.theme = event.detail;
    appearanceForm.elements.theme.value = event.detail;
    preview();
  });
  preview();
}

// Keep server validation errors discoverable after a full-page form submit.
const invalidField = document.querySelector('[aria-invalid="true"]');
if (invalidField) invalidField.focus();
