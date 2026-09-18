const { chromium } = require('playwright');
const path = require('path');

const SHOT_DIR = path.resolve(__dirname, 'shots');
const fs = require('fs');
if (!fs.existsSync(SHOT_DIR)) fs.mkdirSync(SHOT_DIR, { recursive: true });

const URL = 'http://localhost:5187/';

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const logs = [];
  page.on('console', msg => logs.push(`[console.${msg.type()}] ${msg.text()}`));
  page.on('pageerror', err => logs.push(`[pageerror] ${err.message}`));

  await page.goto(URL, { waitUntil: 'networkidle' });
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(SHOT_DIR, '01_overview_1280.png'), fullPage: true });

  // Inspect tab bar & tour button
  const tabBarHtml = await page.evaluate(() => {
    const el = document.querySelector('[class*="tabBar"], [class*="Tabs"], nav');
    return el ? el.outerHTML.slice(0, 2000) : 'NOT FOUND';
  });
  fs.writeFileSync(path.join(SHOT_DIR, 'tabbar.html'), tabBarHtml);

  // click tour button
  const tourBtn = await page.$('button:has-text("tour"), button:has-text("Tour")');
  if (tourBtn) {
    await tourBtn.click();
    await page.waitForTimeout(600);
    await page.screenshot({ path: path.join(SHOT_DIR, '02_tour_step1.png'), fullPage: true });
    // click through tour steps if "Next" button exists
    for (let i = 0; i < 12; i++) {
      const nextBtn = await page.$('button:has-text("Next")');
      if (!nextBtn) break;
      await nextBtn.click();
      await page.waitForTimeout(500);
      await page.screenshot({ path: path.join(SHOT_DIR, `02_tour_step${i+2}.png`), fullPage: true });
    }
    // try to close/finish
    const finishBtn = await page.$('button:has-text("Finish"), button:has-text("Done"), button:has-text("Close"), button:has-text("Skip")');
    if (finishBtn) { await finishBtn.click(); await page.waitForTimeout(400); }
  }
  await page.screenshot({ path: path.join(SHOT_DIR, '03_after_tour.png'), fullPage: true });

  // enumerate tabs
  const tabButtons = await page.$$('[class*="tab"] button, [role="tab"], button[class*="Tab"]');
  logs.push(`Found ${tabButtons.length} tab-like buttons`);

  const tabTexts = await page.$$eval('button', btns => btns.map(b => b.textContent.trim()).filter(Boolean));
  fs.writeFileSync(path.join(SHOT_DIR, 'all_buttons.json'), JSON.stringify(tabTexts, null, 2));

  await browser.close();
  fs.writeFileSync(path.join(SHOT_DIR, 'log.txt'), logs.join('\n'));
  console.log('DONE');
})();
