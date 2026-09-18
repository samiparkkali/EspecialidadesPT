import { chromium } from 'playwright';
const URL = 'http://localhost:5181/';

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const consoleErrors = [];
  page.on('console', (msg) => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
  page.on('pageerror', (err) => consoleErrors.push('pageerror: ' + err.message));

  await page.goto(URL, { waitUntil: 'networkidle' });
  await page.waitForTimeout(600);
  const noThanks = page.getByRole('button', { name: /no thanks/i });
  if (await noThanks.isVisible().catch(() => false)) await noThanks.click();
  await page.waitForTimeout(200);

  await page.getByRole('button', { name: /take a tour/i }).click();
  await page.waitForTimeout(500);

  for (let i = 0; i < 12; i++) {
    const tooltip = page.locator('p').filter({ hasText: /./ }).locator('..').first();
    const counter = await page.locator('text=/\d+ \/ \d+/').first().textContent().catch(() => 'N/A');
    const title = await page.locator('h3').first().textContent().catch(() => 'N/A');
    const text = await page.locator('h3').first().locator('xpath=following-sibling::p[1]').textContent().catch(() => 'N/A');
    const spotlight = await page.locator('[class*="spotlight"]').boundingBox().catch(() => null);
    const viewport = page.viewportSize();
    const inBounds = spotlight ? (spotlight.x >= -5 && spotlight.y >= -5 && spotlight.x + spotlight.width <= viewport.width + 5) : 'no-spotlight';
    console.log(`Step ${counter}: "${title}" spotlight=${JSON.stringify(spotlight)} inBounds=${inBounds}`);
    console.log(`   text: ${text?.slice(0, 150)}`);

    const finishBtn = page.getByRole('button', { name: 'Finish' });
    const nextBtn = page.getByRole('button', { name: 'Next' });
    if (await finishBtn.isVisible().catch(() => false)) {
      await finishBtn.click();
      console.log('Clicked Finish, tour done.');
      break;
    } else if (await nextBtn.isVisible().catch(() => false)) {
      await nextBtn.click();
      await page.waitForTimeout(900);
    } else {
      console.log('No Next/Finish visible, stopping.');
      break;
    }
  }

  await page.waitForTimeout(300);
  // inspect ranking state left by demo
  const rankItems = await page.locator('[data-tour="rank-list"] li').allTextContents().catch(() => []);
  console.log('Rank list state after tour:', rankItems);
  const numVal = await page.locator('[data-tour="rank-number"] input[type="number"]').first().inputValue().catch(() => null);
  console.log('Number input after tour:', numVal);
  const searchVal = await page.locator('[data-tour="rank-filters"] label:has-text("Search") input').inputValue().catch(() => null);
  console.log('Search box value after tour:', searchVal);

  console.log('Console errors during tour run:', consoleErrors);
  await browser.close();
})();
