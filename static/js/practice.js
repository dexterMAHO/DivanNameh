const practice = document.getElementById('typed-practice');
const answer = document.getElementById('review-answer');
const input = document.getElementById('practice-response');
const actual = answer.querySelector('.hemistich')?.textContent || '';
const feedback = practice.querySelector('[role="status"]');

function normalize(text) {
  return text.normalize('NFKC').replace(/[يى]/gu, 'ی').replace(/ك/gu, 'ک')
    .replace(/[\u0640\u200c\u200d\p{M}\p{P}\s]/gu, '');
}

practice.hidden = false;
document.getElementById('check-practice').addEventListener('click', () => {
  if (!input.value.trim()) {
    feedback.textContent = 'ابتدا سطر را بنویسید.';
    input.focus();
    return;
  }
  feedback.textContent = normalize(input.value) === normalize(actual) ?
    'پاسخ با متن شعر هم‌خوان است.' : 'متن نوشته‌شده با پاسخ تفاوت دارد. پاسخ را برای مقایسه ببینید.';
  answer.open = true;
});
