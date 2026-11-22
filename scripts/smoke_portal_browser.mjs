// Local browser smoke test for the pharmacist/admin PWA after image mirroring.
import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import fs from 'node:fs/promises';

const server = spawn('python3', ['-m', 'http.server', '8765', '--bind', '127.0.0.1'], { stdio: 'ignore' });
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));
const report = { checkedAt: new Date().toISOString(), pages: [], fatalErrors: [] };
const bounded = async (work, timeoutMs = 12000) => {
  let timer;
  try {
    return await Promise.race([work, new Promise((_, reject) => {
      timer = setTimeout(() => reject(new Error('UI thread did not respond within ' + timeoutMs + ' ms')), timeoutMs);
    })]);
  } finally {
    clearTimeout(timer);
  }
};

let browser;
try {
  await sleep(1200);
  browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  for (const device of [
    { label: 'desktop', viewport: { width: 1365, height: 768 }, mobile: false },
    { label: 'mobile', viewport: { width: 390, height: 844 }, mobile: true },
  ]) {
    const context = await browser.newContext({ viewport: device.viewport, isMobile: device.mobile });
    const page = await context.newPage();
    page.setDefaultTimeout(15000);
    const errors = [];
    page.on('pageerror', error => errors.push(String(error?.stack || error?.message || error).slice(0, 1200)));
    await page.goto('http://127.0.0.1:8765/index.html', { waitUntil: 'domcontentloaded', timeout: 45000 });
    await page.waitForTimeout(2000);
    const result = await bounded(page.evaluate(async () => {
      const ready = document.readyState;
      const buttons = document.querySelectorAll('button').length;
      const links = document.querySelectorAll('a').length;
      const imageNodes = document.querySelectorAll('img').length;
      await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      return { ready, buttons, links, imageNodes, responsive: true, title: document.title };
    }), 12000);
    // Exercise a visible login entry button without submitting credentials.
    const loginButtons = page.locator('button').filter({ hasText: /تسجيل الدخول|دخول|login/i });
    result.loginButtonsFound = await loginButtons.count();
    result.loginButtonClicked = false;
    for (let i = 0; i < Math.min(3, result.loginButtonsFound); i++) {
      const btn = loginButtons.nth(i);
      if (await btn.isVisible() && await btn.isEnabled()) {
        await bounded(btn.click({timeout: 5000}), 6500);
        await bounded(page.evaluate(() => new Promise(resolve => requestAnimationFrame(resolve))), 5000);
        result.loginButtonClicked = true;
        break;
      }
    }
    await page.screenshot({ path: 'portal-smoke-' + device.label + '.png', fullPage: false });
    report.pages.push({ device: device.label, ...result, javascriptErrors: errors });
    if (result.buttons === 0 || !result.responsive) {
      report.fatalErrors.push(device.label + ': no interactive buttons or unresponsive render');
    }
    for (const error of errors) {
      if (/SyntaxError|Identifier .* already been declared|Unexpected token|Unexpected end of input/i.test(error))
        report.fatalErrors.push(device.label + ': ' + error);
    }
    await context.close();
  }
} catch (error) {
  report.fatalErrors.push('Browser smoke failed: ' + String(error?.stack || error));
} finally {
  if (browser) await browser.close();
  server.kill('SIGTERM');
  await fs.writeFile('portal-smoke-report.json', JSON.stringify(report, null, 2) + '\n', 'utf8');
}
console.log(JSON.stringify(report, null, 2));
if (report.fatalErrors.length) process.exit(1);
