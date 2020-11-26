import asyncio
from pyppeteer import launch

async def main():
    browser = await launch(options={'args': ['--no-sandbox']})
    page = await browser.newPage()
    await page.goto('https://example.com')
    await page.screenshot({'path': './archive/example.png'})
    await browser.close()

asyncio.get_event_loop().run_until_complete(main())
