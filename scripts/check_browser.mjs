import assert from 'node:assert/strict';
import {execFileSync, spawn} from 'node:child_process';
import {mkdir, mkdtemp, readFile, rm, writeFile} from 'node:fs/promises';
import {createServer} from 'node:net';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {setTimeout as delay} from 'node:timers/promises';

const root = await mkdtemp(join(tmpdir(), 'divan-browser-'));
const python = process.env.PYTHON || 'python3';
const chromeBinary = process.env.CHROME_BINARY || 'google-chrome';
const env = {
  ...process.env,
  DJANGO_SETTINGS_MODULE: 'config.settings_development',
  DJANGO_READ_DOTENV: 'false',
  DATABASE_URL: 'sqlite:///' + join(root, 'browser.sqlite3'),
  DEBUG: 'true',
  ALLOWED_HOSTS: '127.0.0.1',
  READER_HUMAN_CHECK_ENABLED: 'false',
};
let server;
let chrome;
let browserSocket;
const exceptions = [];

async function until(check, description) {
  for (let attempt = 0; attempt < 180; attempt++) {
    try {
      const result = await check();
      if (result) return result;
    } catch {
      // The browser or server may still be starting.
    }
    await delay(60);
  }
  throw new Error('Timed out: ' + description);
}

async function localPort() {
  const probe = createServer();
  await new Promise(resolve => probe.listen(0, '127.0.0.1', resolve));
  const {port} = probe.address();
  await new Promise(resolve => probe.close(resolve));
  return port;
}

function createProtocol(socket) {
  let sequence = 0;
  const pending = new Map();
  socket.addEventListener('message', ({data}) => {
    const message = JSON.parse(data);
    if (message.id) {
      const {resolve, reject} = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) reject(new Error(message.error.message));
      else resolve(message.result);
    } else if (message.method === 'Runtime.exceptionThrown') {
      exceptions.push(message.params.exceptionDetails.exception?.description || message.params.exceptionDetails.text);
    }
  });
  return (method, params = {}) => new Promise((resolve, reject) => {
    const id = ++sequence;
    pending.set(id, {resolve, reject});
    socket.send(JSON.stringify({id, method, params}));
  });
}

try {
  execFileSync(python, ['manage.py', 'migrate', '--noinput'], {env, stdio: 'pipe'});
  const source = await readFile(new URL('./browser_fixture.py', import.meta.url));
  const output = execFileSync(python, ['manage.py', 'shell', '-i', 'python'], {env, input: source}).toString();
  const fixture = JSON.parse(output.trim().split('\n').at(-1));
  execFileSync(python, ['manage.py', 'seed_public_treasury'], {env, stdio: 'pipe'});
  const port = await localPort();
  const base = 'http://127.0.0.1:' + port;
  server = spawn(python, ['manage.py', 'runserver', '127.0.0.1:' + port, '--noreload'], {env, stdio: 'ignore'});
  chrome = spawn(chromeBinary, ['--headless', '--no-sandbox', '--disable-dev-shm-usage', '--disable-extensions',
    '--remote-debugging-port=0', '--user-data-dir=' + join(root, 'chrome'), 'about:blank'], {stdio: 'ignore'});
  let startupError;
  for (const process of [server, chrome]) process.once('error', error => { startupError = error; });
  const devToolsPort = await until(async () => (await readFile(join(root, 'chrome', 'DevToolsActivePort'), 'utf8')).split('\n')[0], 'Chrome debugger');
  if (startupError) throw startupError;
  await until(async () => (await fetch(base + '/login/')).ok, 'Django server');
  const tabs = await (await fetch('http://127.0.0.1:' + devToolsPort + '/json/list')).json();
  browserSocket = new WebSocket(tabs.find(tab => tab.type === 'page').webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    browserSocket.addEventListener('open', resolve, {once: true});
    browserSocket.addEventListener('error', reject, {once: true});
  });
  const send = createProtocol(browserSocket);
  const evaluate = async expression => {
    const response = await send('Runtime.evaluate', {expression, returnByValue: true, awaitPromise: true});
    if (response.exceptionDetails) throw new Error(response.exceptionDetails.exception?.description || 'Evaluation failed');
    return response.result.value;
  };
  const open = async path => {
    await send('Page.navigate', {url: base + path});
    await until(() => evaluate('location.pathname + location.search === ' + JSON.stringify(path) +
      ' && document.readyState === "complete" && Boolean(document.querySelector("h1"))'), 'page ' + path);
  };
  const viewport = (width, height = 780) => send('Emulation.setDeviceMetricsOverride', {width, height, deviceScaleFactor: 1, mobile: false});
  await send('Page.enable');
  await send('Runtime.enable');
  await send('Network.enable');
  await send('Network.setCookie', {name: 'sessionid', value: fixture.session, url: base, httpOnly: true});

  const paths = ['/', '/poems/', '/poems/?archived=1', fixture.poem, fixture.free, fixture.long, '/poems/new/', '/topics/', '/favorites/',
    '/collections/', '/poems/transfer/', '/poems/edits/', '/treasury/', encodeURI('/treasury/works/?q=آزمایش'),
    '/review/', '/memorize/', '/memorize/stats/', '/discover/', '/explore/', '/guide/', '/guide/treasury/', '/settings/', '/design-system/'];
  for (const width of [320, 360, 390, 768, 1024, 1101, 1280, 1440]) {
    await viewport(width);
    for (const path of paths) {
      await open(path);
      assert.equal(await evaluate('document.documentElement.scrollWidth <= document.documentElement.clientWidth'), true, path + ' at ' + width);
    }
  }

  await viewport(320);
  await open('/');
  assert.equal(await evaluate("document.querySelector('.discovery-strip a').pathname"), '/explore/');
  assert.equal(await evaluate("document.querySelector('.header-tool[title]').pathname"), '/treasury/works/');
  assert.equal(await evaluate("document.querySelector('.header-help').pathname"), '/guide/');
  for (const theme of ['light', 'dark']) {
    await evaluate('document.documentElement.dataset.theme = ' + JSON.stringify(theme));
    const header = await evaluate(`(() => {
      const summary = document.querySelector('#header-theme summary').getBoundingClientRect();
      const visible = [...document.querySelectorAll('#header-theme summary svg')].filter(icon => icon.getClientRects().length);
      const icon = visible[0].getBoundingClientRect();
      return {
        count: visible.length,
        centered: Math.abs(summary.x + summary.width / 2 - icon.x - icon.width / 2) < 1 &&
                  Math.abs(summary.y + summary.height / 2 - icon.y - icon.height / 2) < 1,
        logoFilter: getComputedStyle(document.querySelector('.brand-logo')).filter,
      };
    })()`);
    assert.equal(header.count, 1);
    assert.equal(header.centered, true);
    assert.equal(header.logoFilter, theme === 'dark' ? 'brightness(0) invert(1)' : 'none');
  }
  await evaluate("document.querySelector('#header-theme summary').click()");
  assert.equal(await evaluate(`(() => {
    const popup = document.querySelector('.theme-options').getBoundingClientRect();
    return popup.left >= 0 && popup.right <= document.documentElement.clientWidth;
  })()`), true);
  await open('/guide/dashboard/');
  await evaluate("document.querySelector('.guide-navigation button').click()");
  await until(() => evaluate("location.pathname === '/guide/library/'"), 'next guide lesson');
  await open('/guide/');
  assert.equal(await evaluate("document.getElementById('guide-progress').value"), 1);

  const screenshots = process.env.DIVAN_BROWSER_ARTIFACTS;
  const screenshot = async name => {
    if (!screenshots) return;
    await mkdir(screenshots, {recursive: true});
    const capture = await send('Page.captureScreenshot');
    await writeFile(join(screenshots, name + '.png'), Buffer.from(capture.data, 'base64'));
  };

  for (const width of [360, 768, 1440]) {
    await viewport(width, 1000);
    for (const [name, path] of [['home', '/'], ['treasury', '/treasury/'], ['poem', fixture.poem], ['free', fixture.free], ['favorites', '/favorites/'], ['review', '/review/']]) {
      await open(path);
      await evaluate('document.fonts.ready');
      await screenshot(name + '-' + width);
    }
  }

  await viewport(390);
  await open('/settings/');
  const colors = await evaluate(`(() => {
    const root = document.documentElement;
    const original = {...root.dataset};
    const ratio = (left, right) => {
      const luminance = hex => {
        const [r, g, b] = hex.match(/[a-f0-9]{2}/gi).map(pair => parseInt(pair, 16) / 255)
          .map(channel => channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4);
        return r * 0.2126 + g * 0.7152 + b * 0.0722;
      };
      const values = [luminance(left), luminance(right)].sort((a, b) => b - a);
      return (values[0] + 0.05) / (values[1] + 0.05);
    };
    const checks = [];
    for (const palette of ['paper', 'ocean', 'forest', 'plum']) {
      for (const theme of ['light', 'dark']) {
        Object.assign(root.dataset, {palette, theme});
        const styles = getComputedStyle(root);
        const color = name => styles.getPropertyValue('--color-' + name).trim();
        checks.push({palette, theme,
          text: ratio(color('foreground'), color('surface')),
          secondary: ratio(color('muted-foreground'), color('surface')),
          action: ratio(color('on-primary'), color('primary')),
          focus: ratio(color('focus'), color('surface')),
          control: ratio(color('control-border'), color('surface')),
        });
      }
    }
    Object.assign(root.dataset, original);
    return checks;
  })()`);
  for (const pair of colors) {
    assert.ok(pair.text >= 4.5 && pair.secondary >= 4.5 && pair.action >= 4.5, JSON.stringify(pair));
    assert.ok(pair.focus >= 3 && pair.control >= 3, JSON.stringify(pair));
  }
  await evaluate('document.querySelector("#header-theme summary").click()');
  await evaluate('document.querySelector("#header-theme button[value=light]").click()');
  await until(() => evaluate('document.documentElement.dataset.theme === "light"'), 'light theme applied');
  await screenshot('settings-light-390');
  await viewport(1440, 1000);
  await open('/treasury/');
  await screenshot('treasury-light-1440');
  await open(fixture.long);
  await screenshot('poem-light-1440');
  await viewport(360, 1000);
  await open('/treasury/');
  await screenshot('treasury-light-360');
  await open('/');
  await evaluate('document.getElementById("nav-toggle").click()');
  assert.equal(await evaluate('document.activeElement.closest("#navigation-panel") !== null'), true);
  await send('Input.dispatchKeyEvent', {type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27});
  assert.equal(await evaluate('document.activeElement.id'), 'nav-toggle');

  await viewport(320);
  await send('Emulation.setCPUThrottlingRate', {rate: 4});
  await open(fixture.work);
  const reading = await evaluate(`document.fonts.ready.then(() => {
    const verse = document.querySelector('.treasury-text .hemistich');
    return {
      font: parseFloat(getComputedStyle(verse).fontSize),
      fits: verse.scrollWidth <= verse.clientWidth,
      firstVerseVisible: verse.getBoundingClientRect().top < innerHeight,
      rows: document.querySelectorAll('.treasury-stanza').length,
      nodes: document.getElementsByTagName('*').length,
      domReadyMs: performance.getEntriesByType('navigation')[0].domContentLoadedEventEnd,
    };
  })`);
  assert.equal(reading.rows, 500);
  assert.equal(reading.fits, true);
  assert.equal(reading.firstVerseVisible, true);
  assert.ok(reading.font >= 20, JSON.stringify(reading));
  console.log('320 px, 500 rows, Chrome CPU ×4:', reading);
  await screenshot('treasury-320');
  await evaluate('document.querySelector(".treasury-bookmark").click()');
  assert.equal(await evaluate('document.querySelector("#treasury-feedback").textContent.includes("۱")'), true);
  await evaluate('document.querySelector(".treasury-favorite").click()');
  await until(() => evaluate('document.querySelector(".treasury-favorite").getAttribute("aria-pressed") === "true"'), 'favorite saved');
  await send('Emulation.setCPUThrottlingRate', {rate: 1});
  await evaluate('document.querySelector(".treasury-text .verse[data-position=\\"5\\"]").scrollIntoView()');
  await delay(120);
  await open(fixture.work + '?resume-check=1');
  assert.equal(await evaluate('!document.querySelector(".resume-reading").hidden'), true);
  await evaluate('document.querySelector(".resume-reading").click()');
  assert.equal(await evaluate('document.activeElement.dataset.position'), '5');
  await open('/treasury/?letter=' + encodeURIComponent('ی'));
  assert.equal(await evaluate('document.getElementById("treasury-letter").value'), 'ی');

  await open(fixture.poem);
  await evaluate(`(() => {
    document.getElementById('study-range').open = true;
    const form = document.querySelector('.range-form');
    form.elements.end_verse_id.selectedIndex = 1;
    form.elements.end_verse_id.dispatchEvent(new Event('change'));
    form.querySelector('button').click();
  })()`);
  await until(() => evaluate('document.querySelectorAll("#poem-study-cards li").length === 2'), 'second card saved');
  assert.equal(await evaluate('Boolean(document.querySelector(".range-form"))'), true);

  // A bayt must never collapse to one character per line. This broke once when
  // the reading sheet became a size container inside a grid area and lost its
  // width, so the check covers the library poem page as well as the treasury.
  for (const width of [360, 1440]) {
    await viewport(width);
    for (const path of [fixture.poem, fixture.long, fixture.work]) {
      await open(path);
      const line = await evaluate(`(() => {
        const h = document.querySelector('.hemistich');
        const box = h.getBoundingClientRect();
        return {w: Math.round(box.width), h: Math.round(box.height), chars: h.textContent.trim().length};
      })()`);
      assert.ok(line.w > 80, `hemistich collapsed at ${width}: ${JSON.stringify(line)} on ${path}`);
      assert.ok(line.h < line.w, `hemistich taller than wide at ${width}: ${JSON.stringify(line)} on ${path}`);
    }
  }
  await viewport(1440);

  await open(fixture.poem);
  await evaluate('document.querySelector("[data-favorite] button").click()');
  await until(() => evaluate('document.querySelector("[data-favorite] button").getAttribute("aria-pressed") === "true"'), 'personal favorite saved');
  await open('/favorites/');
  assert.equal(await evaluate(`Boolean(document.querySelector('a[href="${fixture.poem}#verse-1"]'))`), true, 'favorite deep link');
  await evaluate(`document.querySelector('a[href="${fixture.poem}#verse-1"]').click()`);
  await until(() => evaluate('location.hash === "#verse-1" && Boolean(document.getElementById("verse-1"))'), 'return to precise verse');
  // Reach the star using Tab, then activate it with Enter.
  for (let i = 0; i < 80 && !await evaluate('document.activeElement === document.querySelector("[data-favorite] button")'); i++) {
    await send('Input.dispatchKeyEvent', {type: 'keyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9});
    await send('Input.dispatchKeyEvent', {type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9});
  }
  assert.equal(await evaluate('document.activeElement === document.querySelector("[data-favorite] button")'), true, 'keyboard reaches star');
  assert.notEqual(await evaluate('getComputedStyle(document.activeElement).outlineStyle'), 'none');
  await send('Input.dispatchKeyEvent', {type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13, text: '\r', unmodifiedText: '\r'});
  await send('Input.dispatchKeyEvent', {type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13});
  await until(() => evaluate('document.querySelector("[data-favorite] button").getAttribute("aria-pressed") === "false"'), 'keyboard removes saved star');
  await evaluate('document.querySelector("[data-poem-size]").value = "largest"; document.querySelector("[data-poem-size]").dispatchEvent(new Event("change"))');
  await open(fixture.poem + '?size-check=1');
  assert.equal(await evaluate('document.documentElement.dataset.readingSize'), 'largest');
  assert.equal(await evaluate('document.documentElement.scrollWidth <= document.documentElement.clientWidth'), true);
  await open('/settings/');
  await evaluate(`document.querySelector('[name=palette][value=ocean]').click(); document.querySelector('#appearance-form .primary').click()`);
  await until(() => evaluate('document.documentElement.dataset.palette === "ocean" && document.readyState === "complete"'), 'palette saved');
  await open('/settings/?palette-check=1');
  assert.equal(await evaluate('document.documentElement.dataset.palette'), 'ocean');
  await evaluate('document.getElementById("accent-color").value = "#ffffee"; document.getElementById("accent-color").dispatchEvent(new Event("input"))');
  assert.equal(await evaluate('!document.getElementById("accent-suggestion").hidden'), true);
  await evaluate('document.getElementById("accent-save").click()');
  const accent = await evaluate('getComputedStyle(document.documentElement).getPropertyValue("--color-primary").trim()');
  await open('/settings/?accent-check=1');
  assert.equal(await evaluate('getComputedStyle(document.documentElement).getPropertyValue("--color-primary").trim()'), accent);
  await screenshot('custom-accent-320');
  const customContrast = await evaluate(`(async () => {
    const root = document.documentElement, original = {...root.dataset};
    const lum = hex => hex.slice(1).match(/../g).map(x => parseInt(x, 16) / 255).map(x => x <= .04045 ? x / 12.92 : ((x + .055) / 1.055) ** 2.4).reduce((sum, v, i) => sum + v * [.2126, .7152, .0722][i], 0);
    const ratio = (a, b) => (Math.max(lum(a), lum(b)) + .05) / (Math.min(lum(a), lum(b)) + .05);
    const checks = [];
    for (const palette of ['paper', 'ocean', 'forest', 'plum']) for (const theme of ['light', 'dark']) {
      Object.assign(root.dataset, {palette, theme});
      await new Promise(requestAnimationFrame);
      const styles = getComputedStyle(root), c = name => styles.getPropertyValue('--color-' + name).trim();
      checks.push({palette, theme, text: ratio(c('primary'), c('surface')), selected: ratio(c('primary'), c('primary-soft')), button: ratio(c('on-primary'), c('primary')), hover: ratio(c('on-primary'), c('primary-hover'))});
    }
    Object.assign(root.dataset, original);
    await new Promise(requestAnimationFrame);
    return checks;
  })()`);
  for (const check of customContrast) assert.ok(Math.min(check.text, check.selected, check.button, check.hover) >= 4.5, JSON.stringify(check));
  await evaluate('document.getElementById("accent-reset").click()');
  await open('/settings/?reset-check=1');
  assert.equal(await evaluate('document.documentElement.style.getPropertyValue("--color-primary")'), '');

  await open('/poems/new/');
  await screenshot('editor-320');
  await evaluate(`(() => {
    document.getElementById('draft-controls').open = true;
    document.getElementById('draft-enabled').click();
    const title = document.getElementById('id_title');
    title.value = 'پیش‌نویس آزمون';
    title.dispatchEvent(new Event('input', {bubbles: true}));
  })()`);
  await until(() => evaluate('document.getElementById("draft-status").textContent.includes("ذخیره شد")'), 'draft saved');
  // A new document with the same browser profile exercises the recovery path without a user activation.
  await open('/poems/new/?restore-check=1');
  await evaluate('document.getElementById("restore-draft").click()');
  assert.equal(await evaluate('document.getElementById("id_title").value'), 'پیش‌نویس آزمون');

  await open('/review/?mode=blanks');
  assert.equal(await evaluate('document.querySelector("#rating-form button").disabled'), true);
  await evaluate('document.querySelector("#review-answer summary").click()');
  await until(() => evaluate('!document.querySelector("#rating-form button").disabled'), 'rating revealed');

  await send('Emulation.setEmulatedMedia', {features: [{name: 'prefers-reduced-motion', value: 'reduce'}]});
  assert.equal(await evaluate('getComputedStyle(document.querySelector(".review-verses")).animationName'), 'none');
  const oldRequest = await evaluate('document.querySelector("#rating-form [name=request_id]").value');
  await evaluate('document.querySelector("#rating-form button").click()');
  await until(() => evaluate('document.readyState === "complete" && (!document.querySelector("#rating-form") || document.querySelector("#rating-form [name=request_id]").value !== ' + JSON.stringify(oldRequest) + ')'), 'review rating submitted');
  await send('Emulation.setScriptExecutionDisabled', {value: true});
  await open('/poems/new/?mode=base');
  assert.equal(await evaluate('document.getElementById("add-verse").hidden && document.getElementById("preview-button").hidden'), true);
  await send('Emulation.setScriptExecutionDisabled', {value: false});
  await send('Network.deleteCookies', {name: 'sessionid', url: base});
  for (const guest of ['/login/', '/signup/', '/login/recover/', '/discover/', '/explore/', '/guide/']) {
    await open(guest);
    assert.equal(await evaluate('document.documentElement.scrollWidth <= document.documentElement.clientWidth'), true, guest);
  }
  assert.deepEqual(exceptions, []);
  console.log('Responsive pages, reading, favorite, second card, draft, practice and no-JS editor passed.');
} finally {
  browserSocket?.close();
  const waitForExit = process => {
    if (!process?.pid || process.exitCode !== null || process.signalCode !== null) return Promise.resolve();
    const exited = new Promise(resolve => process.once('exit', resolve));
    process.kill();
    return exited;
  };
  await Promise.all([waitForExit(server), waitForExit(chrome)]);
  await rm(root, {recursive: true, force: true, maxRetries: 3});
}
