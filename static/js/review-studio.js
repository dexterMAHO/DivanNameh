const studio = document.querySelector('.review-studio');
const button = document.getElementById('review-focus');
const answer = document.getElementById('review-answer');
if (studio && button && answer) {
  button.hidden = false;
  button.addEventListener('click', () => {
    const focused = studio.classList.toggle('is-focused');
    button.setAttribute('aria-pressed', String(focused));
  });
  answer.addEventListener('toggle', () => {
    const recall = studio.querySelector('[data-review-step="recall"]');
    const reveal = studio.querySelector('[data-review-step="reveal"]');
    recall.toggleAttribute('data-complete', answer.open);
    (answer.open ? recall : reveal).removeAttribute('aria-current');
    (answer.open ? reveal : recall).setAttribute('aria-current', 'step');
  });
}
