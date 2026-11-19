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

const themeForm = document.getElementById('header-theme');
const themeButton = themeForm?.querySelector('button');
const updateThemeButton = () => {
  if (!themeButton) return;
  const theme = document.documentElement.dataset.theme;
  const dark = theme === 'dark' || (theme === 'auto' && matchMedia('(prefers-color-scheme: dark)').matches);
  themeButton.value = dark ? 'light' : 'dark';
  themeButton.setAttribute('aria-label', dark ? 'تغییر به حالت روشن' : 'تغییر به حالت تاریک');
};
updateThemeButton();
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', updateThemeButton);
new MutationObserver(updateThemeButton).observe(document.documentElement, {attributes: true, attributeFilter: ['data-theme']});
themeForm?.addEventListener('submit', async event => {
  event.preventDefault();
  if (themeButton.disabled) return;
  const root = document.documentElement;
  const previous = root.dataset.theme;
  const pending = request(themeForm.action, themeForm, themeButton);
  root.dataset.theme = themeButton.value;
  themeButton.disabled = true;
  const controls = [...document.querySelectorAll('#appearance-form select, #appearance-form input:not([type="hidden"])')];
  controls.forEach(control => control.disabled = true);
  try {
    const data = await pending;
    root.dataset.theme = data.theme;
    showStatus(document.getElementById('theme-feedback'), data.message);
    document.dispatchEvent(new CustomEvent('theme-saved', {detail: data.theme}));
  } catch (error) {
    root.dataset.theme = previous;
    showStatus(document.getElementById('theme-feedback'), error.message, true);
  } finally {
    themeButton.disabled = false;
    controls.forEach(control => control.disabled = false);
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

// Apply appearance immediately and persist through the existing settings endpoint.
const appearanceForm = document.getElementById('appearance-form');
if (appearanceForm) {
  const root = document.documentElement;
  const status = document.getElementById('appearance-status');
  const controls = [...appearanceForm.querySelectorAll('select, input:not([type="hidden"])')];
  let saved = {theme: root.dataset.theme, palette: root.dataset.palette};
  appearanceForm.addEventListener('submit', event => event.preventDefault());
  appearanceForm.addEventListener('change', async () => {
    const selected = {theme: appearanceForm.elements.theme.value, palette: appearanceForm.elements.palette.value};
    const body = new FormData(appearanceForm);
    Object.assign(root.dataset, selected);
    controls.forEach(control => control.disabled = true);
    if (themeButton) themeButton.disabled = true;
    showStatus(status, 'در حال ذخیرهٔ ظاهر…');
    try {
      const response = await fetch(appearanceForm.action, {
        method: 'POST', body, credentials: 'same-origin',
        headers: {'X-CSRFToken': body.get('csrfmiddlewaretoken')},
        signal: AbortSignal.timeout(15000),
      });
      const page = new DOMParser().parseFromString(await response.text(), 'text/html');
      if (!response.ok || !response.redirected ||
          page.documentElement.dataset.theme !== selected.theme ||
          page.documentElement.dataset.palette !== selected.palette) {
        throw new Error('ظاهر ذخیره نشد. دوباره انتخاب کنید.');
      }
      saved = selected;
      showStatus(status, 'ظاهر سایت ذخیره شد.');
    } catch (error) {
      Object.assign(root.dataset, saved);
      appearanceForm.elements.theme.value = saved.theme;
      appearanceForm.elements.palette.value = saved.palette;
      showStatus(status, 'ظاهر ذخیره نشد. اتصال را بررسی و دوباره انتخاب کنید.', true);
    } finally {
      controls.forEach(control => control.disabled = false);
      if (themeButton) themeButton.disabled = false;
    }
  });
  document.addEventListener('theme-saved', event => {
    saved.theme = event.detail;
    appearanceForm.elements.theme.value = event.detail;
  });
}

// Keep server validation errors discoverable after a full-page form submit.
const invalidField = document.querySelector('[aria-invalid="true"]:not([data-example])');
if (invalidField) invalidField.focus();
else document.querySelector('[data-form-error]')?.focus();
