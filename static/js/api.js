export function announce(message, error = false) {
  const box = document.getElementById('notifications');
  const p = document.createElement('p');
  p.className = error ? 'notice error' : 'notice';
  p.textContent = message;
  box.replaceChildren(p);
  if (error) box.scrollIntoView({behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'nearest'});
}
export async function request(url, form = null, submitter = undefined) {
  const options = {credentials: 'same-origin', headers: {'Accept': 'application/json'}};
  if (form) {
    options.method = 'POST';
    options.body = new FormData(form, submitter);
    options.headers['X-CSRFToken'] = form.querySelector('[name=csrfmiddlewaretoken]').value;
  }
  const response = await fetch(url, options);
  let data;
  try { data = await response.json(); } catch { throw new Error('پاسخ سرور دریافت نشد؛ دوباره تلاش کنید.'); }
  if (!response.ok) throw new Error(data.message || 'درخواست انجام نشد؛ ورود به حساب و اتصال را بررسی کنید.');
  return data;
}
export function verseElement(first, second, position, lineLayout = false) {
  const row = document.createElement('div'); row.className = lineLayout ? 'verse verse-line' : 'verse';
  const number = document.createElement('span'); number.className = 'verse-number'; number.textContent = Number(position).toLocaleString('fa-IR', {useGrouping: false});
  row.append(number);
  for (const text of [first, second]) {
    if (!text) continue;
    const line = document.createElement('div'); line.className = 'hemistich'; line.textContent = text; row.append(line);
  }
  return row;
}
