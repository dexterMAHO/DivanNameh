import {request} from './api.js';
const favicon = document.querySelector('link[rel="icon"][data-dark]');
if (favicon) {
  const root = document.documentElement;
  const deviceTheme = matchMedia('(prefers-color-scheme: dark)');
  const updateFavicon = () => {
    const dark = root.dataset.theme === 'dark' || (root.dataset.theme === 'auto' && deviceTheme.matches);
    const href = dark ? favicon.dataset.dark : favicon.dataset.light;
    if (favicon.getAttribute('href') !== href) favicon.setAttribute('href', href);
  };
  new MutationObserver(updateFavicon).observe(root, {attributes: true, attributeFilter: ['data-theme']});
  deviceTheme.addEventListener('change', updateFavicon);
  updateFavicon();
}

const digits = new Intl.NumberFormat('fa-IR', {useGrouping: false});

for (const message of document.querySelectorAll('[data-message-tags]')) {
  const key = message.dataset.messageTags.split(' ').find(tag => tag.startsWith('poem-draft-'));
  if (key) {
    try { localStorage.removeItem(key); } catch { /* Storage can be blocked by the browser. */ }
  }
}

function showStatus(status, message, error = false) {
  status.textContent = message;
  status.toggleAttribute('data-error', error);
}

function appendLogin(status, error) {
  if (error.code !== 'login_required') return;
  const login = document.createElement('a');
  login.href = '/login/?next=' + encodeURIComponent(location.pathname + location.search);
  login.textContent = 'ورود دوباره';
  status.append(' ', login);
}

for (const form of document.querySelectorAll('form[data-ajax],form[data-favorite]')) {
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const button = event.submitter || form.querySelector('button');
    if (button.disabled) return;
    const status = form.querySelector('[role="status"]');
    button.setAttribute('aria-disabled', 'true');
    button.disabled = true;
    try {
      const data = await request(form.action, form);
      if (data.remaining_due_count !== undefined) {
        document.querySelectorAll('.count').forEach(el => el.textContent = digits.format(data.remaining_due_count));
      }
      if (data.item) {
        const cards = document.getElementById('poem-study-cards');
        const card = document.createElement('li');
        card.textContent = data.item.label + ' · فعال';
        cards.append(card);
        cards.hidden = false;
        if (data.item.scope === 'full') {
          const feedback = document.getElementById('study-feedback');
          showStatus(feedback, data.message);
          form.hidden = true;
          document.querySelector('#study-range summary').focus();
        }
        const password = form.elements.action_password;
        if (password) password.value = '';
      }
      if (form.hasAttribute('data-favorite')) {
        button.setAttribute('aria-pressed', String(data.favorite));
        form.action = data.favorite ? form.dataset.remove : form.dataset.add;
      }
      showStatus(status, data.message);
    } catch (error) {
      showStatus(status, error.message, true);
      appendLogin(status, error);
    } finally {
      button.disabled = false;
      button.removeAttribute('aria-disabled');
    }
  });
}

for (const form of document.querySelectorAll('.range-form')) {
  const [startSelect, endSelect] = form.querySelectorAll('select');
  const summary = form.closest('details');
  const update = () => {
    const start = Number(startSelect.selectedOptions[0].dataset.position);
    const end = Number(endSelect.selectedOptions[0].dataset.position);
    const valid = end >= start;
    form.querySelector('.selection-count').textContent = valid ?
      digits.format(end - start + 1) + ' ردیف انتخاب شده' : 'پایان بازه باید از آغاز آن عقب‌تر نباشد.';
    form.querySelector('.range-preview').textContent = valid ?
      [startSelect.selectedOptions[0].text, endSelect.selectedOptions[0].text].filter((text, index, all) => all.indexOf(text) === index).join(' تا ') : '';
    endSelect.setAttribute('aria-invalid', String(!valid));
    form.querySelector('button').disabled = !valid;
    for (const row of document.querySelectorAll('.reading-sheet .verse[data-position]')) {
      const position = Number(row.dataset.position);
      row.classList.toggle('selected', summary.open && valid && position >= start && position <= end);
    }
  };
  startSelect.addEventListener('change', update);
  endSelect.addEventListener('change', update);
  summary.addEventListener('toggle', update);
  if (summary.open) update();
}
const answer = document.getElementById('review-answer');
if (answer) {
  const buttons = [...answer.querySelectorAll('button')];
  buttons.forEach(b => b.disabled = true);
  answer.addEventListener('toggle', () => {
    buttons.forEach(b => b.disabled = !answer.open);
  });
  document.getElementById('rating-form').addEventListener('submit', event => {
    if (!event.submitter) return;
    // Preserve the selected submitter when disabling the buttons.
    const input = document.createElement('input'); input.type = 'hidden'; input.name = 'rating'; input.value = event.submitter.value;
    event.target.append(input); buttons.forEach(b => b.disabled = true);
  });
}
const navToggle = document.getElementById('nav-toggle');
if (navToggle) {
  document.body.classList.add('has-js');
  const sidebar = document.querySelector('.sidebar');
  const setOpen = open => {
    navToggle.setAttribute('aria-expanded', String(open));
    sidebar.classList.toggle('mobile-open', open);
  };
  navToggle.addEventListener('click', () => {
    const open = navToggle.getAttribute('aria-expanded') !== 'true';
    setOpen(open);
    if (open) sidebar.querySelector('nav a').focus();
  });
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
if (treasury) {
  const selected = () => [...treasury.querySelectorAll('input[name="verse"]:checked')];
  const clear = document.getElementById('clear-selection');
  const feedback = document.getElementById('treasury-feedback');
  const update = () => {
    const count = selected().length;
    clear.hidden = !count;
    treasury.querySelector('button[value="memorize"]').textContent =
      count ? 'حفظ ' + digits.format(count) + ' ردیف انتخابی' : 'حفظ کل اثر';
    treasury.querySelector('button[value="library"]').textContent =
      count ? 'ذخیرهٔ ' + digits.format(count) + ' ردیف انتخابی' : 'ذخیرهٔ گزیده';
    showStatus(feedback, count ? digits.format(count) + ' ردیف انتخاب شده' : '');
  };
  treasury.addEventListener('change', event => {
    if (event.target.name === 'verse') update();
  });
  clear.addEventListener('click', () => {
    selected().forEach(input => input.checked = false);
    update();
    treasury.querySelector('button[value="library-all"]').focus();
  });
  update();

  treasury.addEventListener('submit', async event => {
    const button = event.submitter;
    if (!button) return;
    event.preventDefault();
    if (['library', 'merge'].includes(button.value) && !selected().length) {
      showStatus(feedback, 'ابتدا بخشی از متن را با نشانک انتخاب کنید.', true);
      treasury.querySelector('input[name="verse"]').focus();
      return;
    }
    const favorite = button.matches('.treasury-favorite');
    const status = favorite ? button.parentElement.querySelector('[role="status"]') : feedback;
    const saving = request(treasury.getAttribute('action'), treasury, button);
    button.disabled = true;
    try {
      const data = await saving;
      if (favorite) {
        const position = button.value.split(':')[1];
        button.value = (data.favorite ? 'unfavorite:' : 'favorite:') + position;
        button.setAttribute('aria-pressed', String(data.favorite));
      }
      showStatus(status, data.message);
      if (data.target_url) {
        const link = document.createElement('a');
        link.href = data.target_url;
        link.textContent = data.target_label;
        status.append(' ', link);
      }
      if (data.remaining_due_count !== undefined) {
        document.querySelectorAll('.count').forEach(el => el.textContent = digits.format(data.remaining_due_count));
      }
    } catch (error) {
      showStatus(status, error.message, true);
      appendLogin(status, error);
    } finally {
      button.disabled = false;
    }
  });
}

const themeMenu = document.getElementById('header-theme');
const themeForm = themeMenu?.querySelector('form');
themeForm?.addEventListener('submit', async event => {
  const button = event.submitter;
  if (!button) return;
  event.preventDefault();
  const pending = request(themeForm.action, themeForm, button);
  const status = themeForm.querySelector('[role="status"]');
  button.disabled = true;
  try {
    const data = await pending;
    document.documentElement.dataset.theme = data.theme;
    for (const choice of themeForm.querySelectorAll('button')) {
      const current = choice.value === data.theme;
      choice.toggleAttribute('data-current', current);
      choice.setAttribute('aria-pressed', String(current));
    }
    const summary = themeMenu.querySelector('summary');
    summary.setAttribute('aria-label', 'حالت نمایش، ' + button.textContent);
    status.textContent = '';
    themeMenu.open = false;
    summary.focus({preventScroll: true});
    showStatus(document.getElementById('theme-feedback'), data.message + ' ' + button.textContent);
    document.dispatchEvent(new CustomEvent('theme-saved', {detail: data.theme}));
  } catch (error) {
    showStatus(status, error.message, true);
  } finally {
    button.disabled = false;
  }
});
themeMenu?.addEventListener('keydown', event => {
  if (event.key === 'Escape' && themeMenu.open) {
    themeMenu.open = false;
    themeMenu.querySelector('summary').focus();
  }
});
for (const button of document.querySelectorAll('[data-copy-field]')) {
  button.hidden = false;
  button.addEventListener('click', async () => {
    const field = document.getElementById(button.dataset.copyField);
    const status = button.nextElementSibling;
    try {
      await navigator.clipboard.writeText(field.value);
      showStatus(status, 'کپی شد.');
    } catch {
      field.focus();
      field.select();
      showStatus(status, 'متن انتخاب شد. آن را کپی کنید.');
    }
  });
}

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
const invalidField = document.querySelector('[aria-invalid="true"]:not([data-example])');
if (invalidField) invalidField.focus();
else document.querySelector('[data-form-error]')?.focus();
