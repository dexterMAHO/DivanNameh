export async function request(url, form = null, submitter = undefined) {
  const options = {credentials: 'same-origin', headers: {'Accept': 'application/json'}};
  if (form) {
    options.method = 'POST';
    options.body = new FormData(form, submitter);
    options.headers['X-CSRFToken'] = form.querySelector('[name=csrfmiddlewaretoken]').value;
  }
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  let response;
  let data;
  try {
    response = await fetch(url, {...options, signal: controller.signal});
    if (response.redirected && new URL(response.url).pathname === '/login/') {
      const error = new Error('نشست ورود پایان یافته است.');
      error.code = 'login_required';
      throw error;
    }
    try {
      data = await response.json();
    } catch {
      throw new Error('پاسخ سرور قابل خواندن نیست. دوباره تلاش کنید.');
    }
  } catch (error) {
    if (!response) throw new Error('اتصال برقرار نشد. دوباره تلاش کنید.');
    throw error;
  } finally {
    clearTimeout(timeout);
  }
  if (!response.ok) {
    const error = new Error(data.message || (response.status === 401 ?
      'نشست ورود پایان یافته است.' : 'درخواست انجام نشد. دوباره تلاش کنید.'));
    error.code = data.code;
    throw error;
  }
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
