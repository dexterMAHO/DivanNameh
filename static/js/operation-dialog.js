const dialog = document.getElementById('operation-dialog');
if (dialog) {
  let pending;
  let approved;
  const input = dialog.querySelector('#operation-password');
  const confirm = dialog.querySelector('#operation-confirm');
  document.addEventListener('submit', event => {
    const form = event.target;
    const marker = form.querySelector('[data-operation-password]');
    if (!marker || form === confirm) return;
    if (approved === form) { approved = null; return; }
    if (marker.hasAttribute('data-operation-conditional') && event.submitter?.value !== 'memorize') return;
    event.preventDefault();
    event.stopImmediatePropagation();
    pending = {form, button: event.submitter};
    const available = marker.dataset.passwordAvailable === 'true';
    input.value = '';
    input.disabled = !available;
    input.required = available;
    confirm.querySelector('[value=password]').hidden = !available;
    dialog.querySelector('#operation-no-password').hidden = available;
    dialog.showModal();
    (available ? input : confirm.querySelector('[value=request]')).focus();
  }, true);
  confirm.addEventListener('submit', event => {
    event.preventDefault();
    if (!pending) return;
    const {form, button} = pending;
    const mode = event.submitter.value;
    form.querySelector('[data-operation-password]').value = mode === 'password' ? input.value : '';
    let choice = form.querySelector('[name=operation_mode]');
    if (!choice) { choice = document.createElement('input'); choice.type = 'hidden'; choice.name = 'operation_mode'; form.append(choice); }
    choice.value = mode;
    approved = form;
    pending = null;
    dialog.close();
    form.requestSubmit(button || undefined);
    // Async handlers have already captured FormData; never retain a password in the page.
    setTimeout(() => { form.querySelector('[data-operation-password]').value = ''; }, 0);
    input.value = '';
  });
  dialog.querySelector('[data-operation-cancel]').addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', () => { pending?.button?.focus(); pending = null; input.value = ''; });
}
