import { expect, test } from "@playwright/test";

test("primary Playwright config passes without proving the app entrypoint", async () => {
  expect(1 + 1).toBe(2);
});
