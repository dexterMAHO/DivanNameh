const sheet = document.querySelector('.treasury-text');
const verses = sheet ? [...sheet.querySelectorAll('.verse')] : [];

if (verses.length) {
  const goldenRatio = (1 + Math.sqrt(5)) / 2;
  let previousWidth;
  const updateGaps = () => {
    const gaps = verses.map(verse => {
      const [first, second] = verse.children;
      const width = Math.max(first.offsetWidth, second.offsetWidth);
      const height = first.offsetHeight + second.offsetHeight;
      // Aim for a golden rectangle around the two lines. CSS bounds the gap
      // so wrapped lines and very wide verses still read as a single couplet.
      return width / goldenRatio - height;
    });
    verses.forEach((verse, index) => verse.style.setProperty('--hemistich-gap', `${gaps[index]}px`));
  };
  new ResizeObserver(([entry]) => {
    if (entry.contentRect.width === previousWidth) return;
    previousWidth = entry.contentRect.width;
    updateGaps();
  }).observe(sheet);
  document.fonts.ready.then(updateGaps);
}
