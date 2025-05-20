const fs = require('fs');
const puppeteer = require('puppeteer');

;(async () => {
  const browser = await puppeteer.launch({
    executablePath: '/usr/bin/chromium-browser',
    args: ['--no-sandbox','--disable-setuid-sandbox']
  });
  const page = await browser.newPage();
  await page.goto('https://www.zubaidafoundation.com/', {
    waitUntil: 'networkidle0'
  });

  const data = await page.evaluate(() => {
    const rows = Array.from(
      document.querySelectorAll('#schedule-table tbody tr')
    );
    return rows.map(tr => {
      const [date, first, second] = Array.from(
        tr.querySelectorAll('td')
      ).map(td => td.textContent.trim());
      return { date, first, second };
    });
  });

  // filter out past dates
  const today = new Date();
  today.setHours(0,0,0,0);
  const upcoming = data.filter(({ date }) => {
    const d = new Date(date);
    d.setHours(0,0,0,0);
    return d >= today;
  }).slice(0,1);

  await browser.close();

  fs.writeFileSync(
    'jummah_schedule.json',
    JSON.stringify(upcoming, null, 2),
    'utf8'
  );
})();
