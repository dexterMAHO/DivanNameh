// A hemistich is never shown on two lines: measure every poetry line and shrink
// its verse until the longest one fits the column it sits in.
const BLOCKS = '.verse:not(.verse-line), .cue:not(.modern-text), .poem-line:not(.modern-text)';
const MINIMUM = 9;
const main = document.getElementById('main');
let scheduled = false;

function boxes(block) {
  const hemistichs = block.getElementsByClassName('hemistich');
  return hemistichs.length ? [...hemistichs] : [block];
}

function lines(box) {
  // Every <br> starts a new line; the rest of the inline content is one run.
  const children = [...box.childNodes];
  const bounds = [];
  let start = 0;
  for (let index = 0; index <= children.length; index++) {
    if (index === children.length || children[index].nodeName === 'BR') {
      if (index > start) bounds.push([start, index]);
      start = index + 1;
    }
  }
  return bounds.map(([from, to]) => {
    const range = document.createRange();
    range.setStart(box, from);
    range.setEnd(box, to);
    return range;
  });
}

function room(box) {
  const style = getComputedStyle(box);
  const borders = parseFloat(style.borderLeftWidth) + parseFloat(style.borderRightWidth);
  let outer = box.clientWidth + borders;
  // A hemistich hugs its text in the treasury, so its grid column gives the real width.
  const track = box.classList.contains('hemistich') && getComputedStyle(box.parentElement);
  const columns = track ? track.gridTemplateColumns.split(' ').map(parseFloat).filter(width => width > 0) : [];
  if (columns.length) {
    const together = box.parentElement.getElementsByClassName('hemistich').length === 1 || style.gridColumnEnd === '-1';
    let column = 0;
    for (let sibling = box.previousElementSibling; sibling; sibling = sibling.previousElementSibling) {
      if (sibling.classList.contains('hemistich')) column++;
    }
    outer = together
      ? columns.reduce((total, width) => total + width, 0) + (parseFloat(track.columnGap) || 0) * (columns.length - 1)
      : columns[Math.min(column, columns.length - 1)];
  }
  return outer - borders - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight) - 1;
}

function plan(block) {
  const size = parseFloat(getComputedStyle(block).fontSize);
  const crowded = [];
  let ratio = 1;
  for (const box of boxes(block)) {
    const width = room(box);
    if (width <= 0) continue;
    for (const line of lines(box)) {
      const text = line.getBoundingClientRect().width;
      if (text <= width) continue;
      ratio = Math.min(ratio, width / text);
      crowded.push(box);
    }
  }
  if (ratio === 1) return null;
  return {size: Math.max(MINIMUM, Math.floor(size * ratio * 20) / 20), previous: size, crowded};
}

function fit() {
  scheduled = false;
  const blocks = [...document.querySelectorAll(BLOCKS)];
  for (const block of blocks) {
    block.style.removeProperty('font-size');
    for (const box of boxes(block)) box.removeAttribute('data-verse-overflow');
  }
  // Type metrics are only roughly linear, so confirm the fit and shave what is left.
  for (let pass = 0, pending = blocks; pass < 3 && pending.length; pass++) {
    const plans = pending.map(plan);
    const unresolved = [];
    pending.forEach((block, index) => {
      const fitted = plans[index];
      if (!fitted) return;
      block.style.fontSize = fitted.size + 'px';
      if (fitted.size < fitted.previous) unresolved.push(block);
      else for (const box of fitted.crowded) box.setAttribute('data-verse-overflow', '');
    });
    pending = unresolved;
  }
}

function schedule() {
  if (!scheduled) {
    scheduled = true;
    requestAnimationFrame(fit);
  }
}

if (main) {
  new ResizeObserver(schedule).observe(main);
  new MutationObserver(schedule).observe(main, {childList: true, subtree: true});
}
new MutationObserver(schedule).observe(document.documentElement,
  {attributes: true, attributeFilter: ['data-reading-size', 'data-reading-layout', 'data-reading-spacing', 'data-reading-numbers']});
window.addEventListener('resize', schedule, {passive: true});
document.addEventListener('toggle', schedule, true);
document.fonts.ready.then(schedule);
schedule();
