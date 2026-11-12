const sheet = document.querySelector('.treasury-text');
const verses = sheet ? [...sheet.querySelectorAll('.verse')] : [];
const lines = verses.flatMap(verse => [...verse.querySelectorAll('.hemistich')]);

if (lines.length) {
  const goldenRatio = (1 + Math.sqrt(5)) / 2;
  let previousWidth;

  function fitPoem() {
    for (const line of lines) line.style.removeProperty('--fitted-font-size');

    const fittedSizes = lines.map(line => {
      const available = line.clientWidth;
      const naturalWidth = line.scrollWidth;
      if (!available || naturalWidth <= available) return null;
      return parseFloat(getComputedStyle(line).fontSize) * (available - 1) / naturalWidth;
    });
    lines.forEach((line, index) => {
      if (fittedSizes[index] !== null) {
        line.style.setProperty('--fitted-font-size', `${fittedSizes[index]}px`);
      }
    });

    const gaps = verses.map(verse => {
      const [first, second] = verse.querySelectorAll('.hemistich');
      if (!second) return null;
      const width = Math.max(first.offsetWidth, second.offsetWidth);
      return width / goldenRatio - first.offsetHeight - second.offsetHeight;
    });
    verses.forEach((verse, index) => {
      if (gaps[index] !== null) verse.style.setProperty('--hemistich-gap', `${gaps[index]}px`);
    });
  }

  new ResizeObserver(([entry]) => {
    if (entry.contentRect.width === previousWidth) return;
    previousWidth = entry.contentRect.width;
    fitPoem();
  }).observe(sheet);
  document.fonts.ready.then(fitPoem);
}
