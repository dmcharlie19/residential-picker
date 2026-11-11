import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { chromium } from '@playwright/test';

const demo = process.env.DEMO_URL || 'http://127.0.0.1:8081';
const real = process.env.REAL_URL || 'http://127.0.0.1:8080';
const evidence = new URL('../../../docs/evidence/', import.meta.url);
await mkdir(evidence, { recursive: true });
const browser = await chromium.launch({
  headless: true,
  ...(process.env.BROWSER_EXECUTABLE_PATH ? { executablePath: process.env.BROWSER_EXECUTABLE_PATH } : {}),
});
const passed = [];
const failures = [];
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await context.newPage();
page.on('pageerror', e => failures.push(e.message));
async function submit() {
  await page.getByRole('button', { name: 'Подобрать' }).click();
}
async function noOverflow() {
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
}
try {
  await page.goto(demo);
  await page.getByRole('heading', { level: 1 }).waitFor();
  await page.screenshot({path:new URL('desktop-initial.png',evidence).pathname.replace(/^\/([A-Za-z]:)/,'$1'),fullPage:true});
  await page.getByLabel('Бюджет, ₽').fill('0');
  await submit();
  await page.getByText('Введите сумму больше нуля', {exact:false}).waitFor();
  passed.push('invalid form');
  await page.getByLabel('Бюджет, ₽').fill('20 000 000');
  await submit();
  await page.getByRole('heading', {name:'Подходящие варианты · 3'}).waitFor();
  assert.equal(await page.locator('article').count(),3);
  assert.equal(await page.getByRole('note').count(),1);
  const data=await (await page.request.get(demo+'/api/v1/search?city='+encodeURIComponent('Сочи')+'&budget=20000000&area=50')).json();
  assert.equal(data.demo_mode,true);
  assert.equal(new Set(data.results.map(r=>r.complex.id)).size,3);
  assert(data.results.every(r=>Number(r.estimated_price_rub)<=20000000 && r.lot.is_demo));
  await noOverflow();
  await page.screenshot({path:new URL('desktop-results.png',evidence).pathname.replace(/^\/([A-Za-z]:)/,'$1'),fullPage:true});
  passed.push('three distinct demo complexes within budget');
  for(const city of ['Москва','Санкт-Петербург']){
    await page.getByLabel('Город',{exact:true}).selectOption(city);
    await submit();
    await page.getByRole('heading',{name:'Подходящие варианты · 3'}).waitFor();
    assert.equal(await page.locator('article').count(),3);
  }
  passed.push('all three cities');
  await page.setViewportSize({width:360,height:800});
  await noOverflow();
  await page.screenshot({path:new URL('mobile-results.png',evidence).pathname.replace(/^\/([A-Za-z]:)/,'$1'),fullPage:true});
  passed.push('mobile 360px no horizontal overflow');
  await page.getByLabel('Бюджет, ₽').fill('1');
  await submit();
  await page.getByRole('heading',{name:'Подходящих вариантов пока нет'}).waitFor();
  assert.equal(await page.locator('article').count(),0);
  passed.push('empty results');

  await page.route('**/api/v1/search?**',route=>route.fulfill({
    status:503,contentType:'application/json',
    body:JSON.stringify({error:{code:'DATABASE_UNAVAILABLE',message:'Сервис временно недоступен. Попробуйте позже.',fields:{}}})
  }));
  await page.getByLabel('Бюджет, ₽').fill('20000000');
  await submit();
  await page.getByRole('alert').waitFor();
  assert.equal(await page.getByRole('heading',{name:'Поиск не завершён'}).count(),1);
  passed.push('server failure is distinct from no results');
  await page.unroute('**/api/v1/search?**');
  await page.goto(real);
  await submit();
  await page.getByRole('heading',{name:'Подходящих вариантов пока нет'}).waitFor();
  assert.equal(await page.getByRole('note').count(),0);
  const realData=await (await page.request.get(real+'/api/v1/search?city='+encodeURIComponent('Сочи')+'&budget=20000000&area=50')).json();
  assert.equal(realData.demo_mode,false);
  assert.equal(realData.count,0);
  passed.push('real catalog has no synthetic apartments');
  assert.deepEqual(failures,[]);
  await writeFile(new URL('browser-results.json',evidence),JSON.stringify({passed,pageErrors:failures},null,2));
  console.log(JSON.stringify({passed:passed.length,checks:passed,pageErrors:failures}));
} finally {
  await context.close();
  await browser.close();
}
