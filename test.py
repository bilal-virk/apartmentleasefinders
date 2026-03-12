from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    print("Connected to existing Chrome instance on port 9222")

    context = browser.contexts[0]
    page = context.pages[0]

    # Access iframe
    frame = page.frame_locator('//iframe[@frameborder="0"]')
    element_contains_number = frame.locator('//*[contains(text(), "[number]")]').first
    text = element_contains_number.inner_text()
    new_text = text.replace("[number]", "20")
    element_contains_number.evaluate("(el, value) => el.innerText = value", new_text)
    print("Updated text:", new_text)