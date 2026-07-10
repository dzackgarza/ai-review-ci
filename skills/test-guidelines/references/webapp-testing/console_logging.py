from playwright.sync_api import ConsoleMessage, sync_playwright

# Example: Capturing console logs during browser automation

url = "http://localhost:5173"  # Replace with your URL

console_logs: list[str] = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1920, "height": 1080})

    def handle_console_message(msg: ConsoleMessage) -> None:
        console_logs.append(f"[{msg.type}] {msg.text}")
        print(f"Console: [{msg.type}] {msg.text}")

    page.on("console", handle_console_message)

    # Navigate to page
    page.goto(url)
    page.wait_for_load_state("networkidle")

    # Interact with the page (triggers console logs)
    page.click("text=Dashboard")
    page.wait_for_timeout(1000)

    browser.close()

# Save console logs to file
# Note: Path modified for local environment if needed, using /tmp as a safe default
with open("/tmp/console.log", "w", encoding="utf-8") as f:
    f.write("\n".join(console_logs))

print(f"\nCaptured {len(console_logs)} console messages")
print("Logs saved to: /tmp/console.log")
