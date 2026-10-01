/* Run node browser_audit.cjs /absolute/path/to/prototype with local Playwright installed. */
const path=require('node:path'),fs=require('node:fs');
const source=path.resolve(process.argv[2]);
const {chromium}=require(path.join(source,'frontend/node_modules/playwright'));
const AxeBuilder=require(path.join(source,'frontend/node_modules/@axe-core/playwright')).default;
const out=path.join(__dirname,'evidence');
(async()=>{
 const browser=await chromium.launch({headless:true});
 const context=await browser.newContext({viewport:{width:1280,height:900},locale:'ar-SA'});
 const page=await context.newPage();
 const logs=[],dialogs=[];
 page.on('pageerror',e=>logs.push(e.message));
 page.on('dialog',async d=>{dialogs.push(d.message());await d.dismiss();});
 const rows=JSON.parse(fs.readFileSync(path.join(out,'cases_actual.json'),'utf8'));
 // Literal user-supplied fixture, no image model and no generated religious content.
 await page.setContent('<html lang="ar" dir="rtl"><body style="background:white;font:36px Noto Naskh Arabic;padding:50px"><div id="fixture"></div></body></html>');
 await page.locator('#fixture').textContent();
 await page.locator('#fixture').evaluate((el,t)=>el.textContent=t,rows[27].input);
 await page.screenshot({path:path.join(out,'case28.png')});
 await page.goto('http://127.0.0.1:8000/');
 await page.waitForSelector('#text');
 await page.getByText('جاهز',{exact:true}).waitFor({timeout:30000});
 const results={};
 for(const id of [30,16,12,20]){
  await page.locator('#text').fill(rows[id-1].input);
  const responsePromise=page.waitForResponse(r=>r.url().endsWith('/v1/check')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'افحص',exact:true}).click();
  await responsePromise;await page.waitForTimeout(300);
  results[id]={badges:await page.getByRole('status').allTextContents(),
    injectedImages:await page.locator('img[src="x"]').count(),
    grades:await page.locator('.grade').allTextContents(),
    sources:await page.getByTestId('source-text').allTextContents()};
  await page.screenshot({path:path.join(out,`browser-case${id}.png`),fullPage:true});
 }
 const axe=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze();
 results.axe={violations:axe.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.length})),incomplete:axe.incomplete.map(v=>v.id)};
 await page.getByRole('button',{name:'English',exact:true}).click();
 results.englishDir=await page.locator('html').getAttribute('dir');
 await page.setViewportSize({width:390,height:844});
 results.mobile=await page.evaluate(()=>({scrollWidth:document.documentElement.scrollWidth,innerWidth}));
 results.dialogs=dialogs;results.pageErrors=logs;
 fs.writeFileSync(path.join(out,'browser_results.json'),JSON.stringify(results,null,2));
 console.log(JSON.stringify(results,null,2));
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1);});
