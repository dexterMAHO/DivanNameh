/* Blocking, tiny bootstrap: apply local reading/accent preferences before first paint.
   Account palette, day/night mode and reduced motion remain server-owned.
   Everything stored here is per account id, so two readers sharing a browser
   do not inherit each other's reading size, column width or accent colour. */
(() => {
  const root = document.documentElement;
  const key = 'divan-appearance-' + root.dataset.preferenceUser;
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(key)) || {}; } catch { /* Optional storage. */ }
  if (!saved || typeof saved !== 'object' || Array.isArray(saved)) saved = {};
  const validColor = color => typeof color === 'string' && /^#[0-9a-f]{6}$/i.test(color);
  const sizes = ['normal', 'large', 'largest'];
  const serverSize = root.dataset.readingSize;
  if (sizes.includes(saved.size) && saved.serverSize === root.dataset.readingSize) root.dataset.readingSize = saved.size;

  // Reading scale and column width belong to the reader, not the account, and
  // must land before the first paint so the poem never resizes under the eye.
  const SCALE_MIN = 85, SCALE_MAX = 135;
  const clampScale = value => Math.min(SCALE_MAX, Math.max(SCALE_MIN, Math.round(Number(value) / 5) * 5));
  const applyScale = percent => root.style.setProperty('--reading-scale', String(percent / 100));
  if (Number.isFinite(Number(saved.scale))) applyScale(clampScale(saved.scale));
  if (saved.wide === true) root.dataset.readingWidth = 'wide';
  if (saved.sceneStopped === true) root.dataset.sceneMotion = 'off';
  const props = ['primary', 'primary-hover', 'primary-soft', 'on-primary', 'focus'];
  const rgb = hex => hex.slice(1).match(/../g).map(x => parseInt(x, 16));
  const hex = channels => '#' + channels.map(x => Math.round(x).toString(16).padStart(2, '0')).join('');
  const mix = (a, b, amount) => hex(rgb(a).map((v, i) => v * (1 - amount) + rgb(b)[i] * amount));
  const lum = color => rgb(color).map(x => { x /= 255; return x <= .04045 ? x / 12.92 : ((x + .055) / 1.055) ** 2.4; }).reduce((sum, x, i) => sum + x * [.2126, .7152, .0722][i], 0);
  const ratio = (a, b) => (Math.max(lum(a), lum(b)) + .05) / (Math.min(lum(a), lum(b)) + .05);
  const current = name => getComputedStyle(root).getPropertyValue('--color-' + name).trim();
  const apply = color => {
    props.forEach(name => root.style.removeProperty('--color-' + name));
    if (!validColor(color)) return null;
    const surface = current('surface'), background = current('background');
    const dark = lum(surface) < .3;
    let safe = color;
    for (let i = 1; i <= 100 && (ratio(safe, surface) < 4.5 || ratio(safe, background) < 4.5 || ratio(safe, mix(surface, safe, .1)) < 4.5); i++) safe = mix(color, dark ? '#ffffff' : '#000000', i / 100);
    const ink = ratio(safe, '#ffffff') >= 4.5 ? '#ffffff' : '#000000';
    const hover = mix(safe, dark ? '#ffffff' : '#000000', .08);
    root.style.setProperty('--color-primary', safe);
    root.style.setProperty('--color-primary-hover', hover);
    root.style.setProperty('--color-on-primary', ink);
    root.style.setProperty('--color-primary-soft', mix(surface, safe, .1));
    root.style.setProperty('--color-focus', safe);
    return safe;
  };
  apply(saved.accent);
  new MutationObserver(() => apply(saved.accent)).observe(root, {attributes: true, attributeFilter: ['data-theme', 'data-palette']});
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => apply(saved.accent));
  const persist = () => {
    try { localStorage.setItem(key, JSON.stringify(saved)); return true; } catch { return false; }
  };

  /* The reading toolbar and the settings page both drive these; one owner keeps
     the stored shape and the clamping in a single place. */
  window.divanAppearance = {
    scale: () => clampScale(saved.scale ?? 100),
    setScale(percent) {
      const value = clampScale(percent);
      saved.scale = value;
      applyScale(value);
      return {value, stored: persist()};
    },
    sceneStopped: () => saved.sceneStopped === true,
    setSceneStopped(stopped) {
      saved.sceneStopped = Boolean(stopped);
      persist();
      return saved.sceneStopped;
    },
    wide: () => saved.wide === true,
    setWide(on) {
      saved.wide = Boolean(on);
      if (saved.wide) root.dataset.readingWidth = 'wide';
      else delete root.dataset.readingWidth;
      return {value: saved.wide, stored: persist()};
    },
  };
  document.addEventListener('DOMContentLoaded', () => {
    const size = document.querySelector('[data-poem-size]');
    if (size) {
      size.parentElement.hidden = false;
      size.value = sizes.includes(root.dataset.readingSize) ? root.dataset.readingSize : 'normal';
      size.addEventListener('change', () => {
        root.dataset.readingSize = size.value;
        saved.size = size.value; saved.serverSize = serverSize;
        const stored = persist();
        document.getElementById('reader-status').textContent = stored ? 'اندازهٔ شعر در این مرورگر ذخیره شد.' : 'اندازه تغییر کرد؛ ذخیره‌سازی مرورگر در دسترس نیست.';
      });
    }
    const defaultButton = document.getElementById('appearance-default');
    if (defaultButton) defaultButton.hidden = false;
    defaultButton?.addEventListener('click', () => {
      const form = document.getElementById('appearance-form');
      form.elements.palette.value = 'paper'; form.elements.theme.value = 'auto';
      delete saved.accent; apply(null); persist();
    });
    /* The settings page offers the same scale as the reading toolbar, so the two
       stay in step through the one owner above. */
    const slider = document.getElementById('reading-scale');
    if (slider) {
      slider.closest('.reading-scale-editor').hidden = false;
      const readout = document.getElementById('reading-scale-value');
      const scaleStatus = document.getElementById('reading-scale-status');
      const digits = new Intl.NumberFormat('fa-IR', {useGrouping: false});
      const show = value => {
        slider.value = String(value);
        readout.textContent = digits.format(value) + '٪';
      };
      show(window.divanAppearance.scale());
      const change = next => {
        const {value, stored} = window.divanAppearance.setScale(next);
        show(value);
        scaleStatus.textContent = stored ? 'اندازهٔ شعر در این مرورگر ذخیره شد.'
                                         : 'اندازه تغییر کرد؛ ذخیره‌سازی مرورگر در دسترس نیست.';
      };
      slider.addEventListener('input', () => change(slider.value));
      document.getElementById('scale-minus').addEventListener('click', () => change(Number(slider.value) - 5));
      document.getElementById('scale-plus').addEventListener('click', () => change(Number(slider.value) + 5));
    }

    const picker = document.getElementById('accent-color');
    if (!picker) return;
    picker.closest('.accent-editor').hidden = false;
    const status = document.getElementById('accent-status');
    const suggestion = document.getElementById('accent-suggestion');
    picker.value = validColor(saved.accent) ? saved.accent : current('primary');
    picker.addEventListener('input', () => {
      const safe = apply(picker.value);
      suggestion.hidden = safe === picker.value;
      suggestion.dataset.color = safe;
      status.textContent = safe === picker.value ? 'پیش‌نمایش آماده است؛ برای نگهداری، رنگ را ذخیره کنید.' : 'رنگ انتخابی با زمینه کنتراست کافی ندارد؛ نسخهٔ خواناتر در پیش‌نمایش اعمال شد.';
    });
    suggestion.addEventListener('click', () => { picker.value = suggestion.dataset.color; picker.dispatchEvent(new Event('input')); });
    document.getElementById('accent-save').addEventListener('click', () => {
      saved.accent = apply(picker.value); picker.value = saved.accent; suggestion.hidden = true;
      status.textContent = persist() ? 'رنگ خوانا در این مرورگر ذخیره شد.' : 'رنگ اعمال شد؛ ذخیره‌سازی مرورگر در دسترس نیست.';
    });
    document.getElementById('accent-reset').addEventListener('click', () => {
      delete saved.accent; apply(null); picker.value = current('primary'); suggestion.hidden = true;
      status.textContent = persist() ? 'رنگ تأکیدی پالت بازگردانده شد.' : 'رنگ بازگردانده شد؛ ذخیره‌سازی مرورگر در دسترس نیست.';
    });
  });
})();
