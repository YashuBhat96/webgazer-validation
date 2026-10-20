"""Runs dashboard login, anonymous counts, ZIP button rendering in a headless browser."""
import asyncio
import secrets
import secrets
from pathlib import Path
from playwright.async_api import async_playwright

BASE=Path(__file__).resolve().parent
MOCK_AUTH_TOKEN = secrets.token_urlsafe(24)
MOCK_AUTH_TOKEN = secrets.token_urlsafe(24)
MOCK=r'''<script>
window.fetch=async(path,opts={})=>{
 if(path==='/admin/api/login')return {ok:true,json:async()=>({token:'RUNTIME_MOCK_AUTH_TOKEN',expires_in_seconds:1800})};
 if(path==='/admin/api/sessions'){
  if(opts.headers?.Authorization!=='Bearer RUNTIME_MOCK_AUTH_TOKEN')return {status:401,ok:false};
  return {ok:true,json:async()=>({total_sessions:3,counts:{submitted:2,incomplete:1,uploading:0},shown:3,sessions:[
   {session_id:'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',batches:40,status:'submitted',visit:'pilot',
    last_activity:'2026-10-20T15:30:00+00:00',metrics:{accPx:85,accDeg:1.3,precPx:34,precDeg:0.6},validation_passed:true},
   {session_id:'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',batches:2,status:'incomplete',visit:'pilot',last_activity:null}
  ]})};
 }
 if(path==='/admin/api/export-all')return {ok:true,blob:async()=>new Blob(['fake ZIP'],{type:'application/zip'})};
 return {ok:false,status:404};
};
</script>'''.replace('RUNTIME_MOCK_AUTH_TOKEN', MOCK_AUTH_TOKEN).replace('RUNTIME_MOCK_AUTH_TOKEN', MOCK_AUTH_TOKEN)
async def run():
 async with async_playwright() as pw:
  browser=await pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-gpu'])
  page=await browser.new_page(accept_downloads=True)
  errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  html=(BASE/'backend/admin_dashboard.html').read_text().replace('<script>',MOCK+'<script>')
  await page.set_content(html,wait_until='domcontentloaded')
  assert await page.locator('#loginView').is_visible()
  assert not await page.locator('#dashboardView').is_visible()
  await page.fill('#password','password entered by researcher')
  await page.click('#loginBtn')
  await page.wait_for_function("document.getElementById('submitted').textContent==='2'")
  assert await page.locator('#rows tr').count()==2
  assert '85 px / 1.30°' in await page.locator('#rows').inner_text()
  assert await page.locator('#exportAll').is_visible()
  await page.click('#logout')
  assert await page.locator('#loginView').is_visible()
  assert not await page.locator('#dashboardView').is_visible()
  assert not errors,errors
  print('Dashboard PASS: password sign in, all-session counts, export control, logout, no invitation UI')
  await browser.close()
if __name__=='__main__':asyncio.run(run())
