import asyncio
from pyppeteer import launch

async def main():
    browser = await launch(executablePath='/usr/bin/google-chrome-stable', headless=True, args=['--no-sandbox']headless=True, args=['--no-sandbox'])
    page = await browser.newPage()
    await page.goto('https://example.com')
    await page.screenshot({'path': './archive/example.png'})
    await browser.close()

asyncio.get_event_loop().run_until_complete(main())
