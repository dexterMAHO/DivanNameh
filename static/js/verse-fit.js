// Fit classical hemistichs after the literary font loads and whenever available width changes.
const mobile = matchMedia('(max-width: 768px)');
const canvas = document.createElement('canvas');
const context = canvas.getContext('2d');
let scheduled = false;
function fit() {
  scheduled = false;
  for (const verse of document.querySelectorAll('.verse:not(.verse-line)')) {
    verse.style.removeProperty('--verse-fit-size');
    verse.classList.toggle('verse-fit', mobile.matches);
    if (!mobile.matches || !context) continue;
    const style = getComputedStyle(verse);
    const base = parseFloat(style.fontSize);
    let size = base;
    for (const line of verse.querySelectorAll('.hemistich')) {
      const width = line.clientWidth;
      if (!width) continue;
      context.font = `${style.fontWeight} ${base}px ${style.fontFamily}`;
      const measured = context.measureText(line.textContent.trim()).width;
      if (measured) size = Math.min(size, base * (width - 3) / measured);
    }
    verse.style.setProperty('--verse-fit-size', `${Math.max(11, Math.floor(size * 10) / 10)}px`);
  }
}
function schedule() { if (!scheduled) { scheduled = true; requestAnimationFrame(fit); } }
new ResizeObserver(schedule).observe(document.getElementById('main'));
new MutationObserver(schedule).observe(document.getElementById('main'), {childList: true, subtree: true});
mobile.addEventListener('change', schedule);
window.addEventListener('resize', schedule, {passive: true});
document.fonts.ready.then(schedule);
new MutationObserver(schedule).observe(document.documentElement, {attributes: true, attributeFilter: ['data-reading-size', 'data-reading-layout', 'data-reading-spacing']});
schedule();
