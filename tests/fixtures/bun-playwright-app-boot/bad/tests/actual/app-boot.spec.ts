import { writeFile } from "node:fs/promises";
import { expect, test } from "@playwright/test";

test("actual app boot exposes the browser-visible sentinel", async ({ page }) => {
  await page.goto("/");

  const sentinel = page.getByTestId("actual-app-boot-sentinel");
  await expect(sentinel).toHaveText("actual-app-boot-ok");

  await writeFile("actual-app-boot-observed.txt", await sentinel.textContent() ?? "");
});
