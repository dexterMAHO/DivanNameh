import {request} from './api.js';

for (const form of document.querySelectorAll('[data-discovery-action]')) {
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const button = event.submitter;
    if (!button || button.disabled || form.dataset.busy) return;
    const status = form.closest('.discovery-result').querySelector('.discovery-action-status');
    const buttons = [...form.querySelectorAll('button')];
    const action = button.value;
    const pending = request(form.getAttribute('action'), form, button);
    form.dataset.busy = 'true';
    buttons.forEach(control => control.disabled = true);
    status.textContent = 'در حال ثبت…';
    status.removeAttribute('data-error');
    try {
      const data = await pending;
      status.textContent = data.message;
      if (typeof data.favorite === 'boolean') {
        button.setAttribute('aria-pressed', String(data.favorite));
        if (form.dataset.addUrl) {
          form.setAttribute('action', data.favorite ? form.dataset.removeUrl : form.dataset.addUrl);
        } else {
          button.value = (data.favorite ? 'unfavorite:' : 'favorite:') + action.split(':')[1];
        }
      }
      if (data.remaining_due_count !== undefined) {
        document.querySelectorAll('.count').forEach(count => count.textContent = data.remaining_due_count.toLocaleString('fa-IR'));
      }
      if (button.hasAttribute('data-save-once') && !data.pending_approval) {
        button.dataset.saved = 'true';
        button.append(' ✓');
      }
      if (data.target_url) {
        const link = document.createElement('a');
        link.href = data.target_url;
        link.textContent = data.target_label || 'دیدن شعر';
        status.append(' ', link);
      }
    } catch (error) {
      status.textContent = error.message;
      status.setAttribute('data-error', '');
      if (error.code === 'login_required') {
        const link = document.createElement('a');
        link.href = '/login/?next=' + encodeURIComponent(location.pathname + location.search);
        link.textContent = 'ورود دوباره';
        status.append(' ', link);
      }
    } finally {
      buttons.forEach(control => control.disabled = control.dataset.saved === 'true');
      delete form.dataset.busy;
    }
  });
}

for (const button of document.querySelectorAll('[data-discovery-copy]')) {
  button.addEventListener('click', async () => {
    const section = button.closest('.discovery-result');
    const rows = JSON.parse(section.querySelector('script[type="application/json"]').textContent);
    const text = rows.map(row => row.filter(Boolean).join('\n')).join('\n\n');
    const status = section.querySelector('.discovery-copy-status');
    const fallback = section.querySelector('.discovery-copy-fallback');
    fallback.hidden = true;
    try {
      await navigator.clipboard.writeText(text);
      status.textContent = 'متن شعر کپی شد.';
    } catch {
      fallback.value = text;
      fallback.hidden = false;
      fallback.focus();
      fallback.select();
      status.textContent = 'متن آماده است؛ آن را از کادر کپی کنید.';
    }
  });
}
