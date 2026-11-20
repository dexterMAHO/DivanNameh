// Runs in the head so a saved custom palette is ready before the first paint.
(() => {
  const root = document.documentElement;
  const system = matchMedia('(prefers-color-scheme: dark)');
  const applied = new Set();
  const rgb = (value, fallback) => /^#[\da-f]{6}$/i.test(value || '') ?
    [1, 3, 5].map(index => parseInt(value.slice(index, index + 2), 16)) : rgb(fallback);
  const hex = color => '#' + color.map(channel => Math.round(channel).toString(16).padStart(2, '0')).join('');
  const mix = (color, target, weight) => color.map((channel, index) => channel * (1 - weight) + target[index] * weight);
  const luminance = color => color.map(channel => {
    const value = channel / 255;
    return value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4;
  }).reduce((sum, value, index) => sum + value * [.2126, .7152, .0722][index], 0);
  const contrast = (a, b) => (Math.max(luminance(a), luminance(b)) + .05) / (Math.min(luminance(a), luminance(b)) + .05);
  const white = [255, 255, 255], black = [0, 0, 0];
  const textOn = background => contrast(white, background) > contrast(black, background) ? white : black;
  const readable = (color, backgrounds, target, minimum = 4.6) => {
    for (let step = 0; step <= 100; step++) {
      const candidate = mix(color, target, step / 100);
      if (backgrounds.every(background => contrast(candidate, background) >= minimum)) return candidate;
    }
    return target;
  };
  const update = () => {
    if (root.dataset.palette !== 'custom') {
      applied.forEach(property => root.style.removeProperty(property));
      applied.clear();
      return;
    }
    const primarySeed = rgb(root.dataset.customPrimary, '#6a4b8c');
    const accent = rgb(root.dataset.customAccent, '#3a4157');
    const dark = root.dataset.theme === 'dark' || (root.dataset.theme === 'auto' && system.matches);
    const background = mix(accent, dark ? black : white, dark ? .90 : .96);
    const surface = mix(accent, dark ? black : white, dark ? .82 : .99);
    const soft = mix(primarySeed, surface, .88);
    const target = dark ? white : black;
    const primary = readable(primarySeed, [background, surface, soft], target);
    const feature = mix(accent, black, dark ? .45 : .25);
    const featureText = textOn(feature);
    const values = {
      background, surface, 'surface-muted': mix(accent, surface, .84),
      foreground: readable(dark ? [244, 242, 247] : [32, 36, 46], [background, surface, soft], target),
      'muted-foreground': readable(dark ? [195, 199, 210] : [86, 93, 116], [background, surface, soft], target),
      primary, 'primary-hover': mix(primary, target, .12), 'primary-soft': soft,
      'on-primary': textOn(primary), feature, 'on-feature': featureText,
      'feature-muted': featureText, border: mix(accent, surface, .63),
      'control-border': readable(accent, [background, surface], target, 3.1), focus: primary,
    };
    for (const [name, value] of Object.entries(values)) {
      const property = '--color-' + name;
      root.style.setProperty(property, hex(value));
      applied.add(property);
    }
    root.style.setProperty('--custom-primary-seed', hex(primarySeed));
    root.style.setProperty('--custom-accent-seed', hex(accent));
    applied.add('--custom-primary-seed');
    applied.add('--custom-accent-seed');
  };
  new MutationObserver(update).observe(root, {attributes: true, attributeFilter: ['data-theme', 'data-palette', 'data-custom-primary', 'data-custom-accent']});
  system.addEventListener('change', update);
  update();
})();
