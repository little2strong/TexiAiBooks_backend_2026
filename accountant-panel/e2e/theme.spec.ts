import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

async function chooseTheme(page: Page, name: "Light" | "Dark" | "System") {
  await page.getByRole("button", { name: /^Choose theme/ }).click();
  await page.getByRole("menuitem", { name, exact: true }).click();
}
async function checkAccessibility(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(
    results.violations.map((item) => ({
      id: item.id,
      nodes: item.nodes.map((node) => ({
        target: node.target,
        detail: node.failureSummary,
      })),
    })),
  ).toEqual([]);
}

test("light default, persisted appearance, and live system preference", async ({
  page,
}) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto("/login");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await checkAccessibility(page);
  await chooseTheme(page, "Dark");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await checkAccessibility(page);
  await chooseTheme(page, "System");
  await page.emulateMedia({ colorScheme: "light" });
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.emulateMedia({ colorScheme: "dark" });
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  expect(await page.evaluate(() => ({ ...localStorage }))).toEqual({
    "taxiaibooks:appearance:guest": "system",
  });
});

test("styleguide renders accessible light and dark components, modal and drawer", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/styleguide");
  await expect(
    page.getByRole("heading", { name: "One brand. Every detail." }),
  ).toBeVisible();
  await checkAccessibility(page);
  const light = page.getByLabel("light theme examples", { exact: true });
  const dark = page.getByLabel("dark theme examples", { exact: true });
  await light.getByRole("button", { name: "Open modal", exact: true }).click();
  await expect(
    page.getByRole("dialog", { name: "Review evidence" }),
  ).toBeVisible();
  await checkAccessibility(page);
  await page.getByRole("button", { name: "OK", exact: true }).click();
  await dark.getByRole("button", { name: "Open drawer", exact: true }).click();
  await expect(
    page.getByRole("dialog", { name: "Receipt review" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await light.getByRole("button", { name: "Preview toast & Undo" }).click();
  await expect(
    light.getByText("Ready To File", { exact: true }).last(),
  ).toBeVisible();
  await page.getByRole("button", { name: "Undo", exact: true }).click();
  await expect(light.locator("tbody .status-badge").first()).toHaveText(
    "In Review",
  );
  expect(errors).toEqual([]);
});

test("reduced motion and compact table density", async ({ page }) => {
  await page.goto("/styleguide");
  const light = page.getByLabel("light theme examples", { exact: true });
  await expect(light.locator(".motion-demo")).toHaveCSS(
    "animation-name",
    "none",
  );
  const row = light.locator("tbody td").first();
  const comfortable = (await row.boundingBox())!.height;
  await light.getByRole("switch", { name: "light compact rows" }).click();
  expect((await row.boundingBox())!.height).toBeLessThan(comfortable);
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await light.getByRole("button", { name: "Replay motion" }).click();
  await expect(light.locator(".motion-demo")).toHaveCSS(
    "animation-name",
    "page-enter, row-flash",
  );
});

test("mobile and tablet layouts stay within the viewport", async ({ page }) => {
  for (const path of ["/login", "/styleguide"]) {
    for (const width of [390, 820]) {
      await page.setViewportSize({ width, height: 900 });
      await page.goto(path);
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
    }
  }
});

// Synthetic API responses are scoped to this browser test, never shipped in the panel.
async function mockWorkspace(page: Page) {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const staff = {
      id: "appearance-test-staff",
      name: "Taylor Accountant",
      email: "test@example.invalid",
      role: "admin",
      team_id: null,
    };
    let body: unknown;
    if (path.endsWith("/auth/login"))
      body = { access_token: "test-only-token", expires_in: 900, staff };
    else if (path.endsWith("/staff/me")) body = staff;
    else if (path.endsWith("/config"))
      body = {
        tax_years: ["2026-27"],
        current_tax_year: "2026-27",
        idle_timeout_seconds: 900,
        categories: [
          { id: "fuel", code: "category.fuel", requires_vehicle: true },
        ],
        sources: [],
      };
    else if (path.endsWith("/dashboard"))
      body = {
        assigned_drivers: 48,
        pending_handoffs: 12,
        due_soon: 4,
        overdue: 2,
        year_not_supplied: 0,
        deadline: {
          due_on: "2028-01-31",
          days_remaining: 459,
          tax_year: "2026-27",
        },
        workload: [
          { id: "new", status: "new", count: 7 },
          { id: "review", status: "in_review", count: 5 },
        ],
        as_of: "2026-10-29T06:00:00Z",
      };
    else if (path.endsWith("/views/search")) body = { items: [] };
    else if (path.endsWith("/search"))
      body = { items: [], total: 0, page: 1, page_size: 25 };
    else return route.fulfill({ status: 204 });
    return route.fulfill({ json: body });
  });
  await page.goto("/login");
  await page.getByLabel("Work email").fill("test@example.invalid");
  await page
    .getByLabel("Password", { exact: true })
    .fill("Synthetic-password-only");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Welcome, Taylor" }),
  ).toBeVisible();
  await expect(page.getByLabel("Authentication code")).toHaveCount(0);
}

test("workspace shell, keyboard search and user-scoped theme", async ({
  page,
}) => {
  await mockWorkspace(page);
  await expect(page.locator(".sidebar")).toHaveCSS("width", "248px");
  await expect(page.locator(".topbar")).toHaveCSS("height", "56px");
  await checkAccessibility(page);
  await page.keyboard.press("Control+k");
  await expect(
    page.getByRole("searchbox", { name: "Global driver search" }),
  ).toBeFocused();
  await chooseTheme(page, "Dark");
  await checkAccessibility(page);
  expect(await page.evaluate(() => ({ ...localStorage }))).toEqual({
    "taxiaibooks:appearance:appearance-test-staff": "dark",
  });
  await page
    .getByRole("button", { name: "Collapse navigation", exact: true })
    .click();
  await expect(page.locator(".sidebar")).toHaveCSS("width", "72px");
  await page.setViewportSize({ width: 820, height: 1180 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await checkAccessibility(page);
});

test("receipt review uses confidence tokens, zoom and exact audited Undo", async ({
  page,
}) => {
  await mockWorkspace(page);
  const driverId = "12345678-1234-1234-1234-123456789012";
  let version = 1;
  let reviewStatus = "pending";
  const reversals: unknown[] = [];
  const receipt = () => ({
    id: "receipt-example",
    version,
    created_at: "2026-10-20T12:00:00Z",
    file_id: "file-example",
    scan_status: "clean",
    mime_type: "image/svg+xml",
    review_status: reviewStatus,
    claim_status: "claimable",
    transaction_id: null,
    mutation_id: reviewStatus === "confirmed" ? "exact-review-mutation" : null,
    merchant: "Example fuel receipt",
    occurred_on: "2026-10-20",
    amount_pence: 12000,
    vat_pence: 2000,
    category_id: "fuel",
    business_use_percent: "100",
    extraction: { confidence: 0.92 },
    warnings: [],
  });
  const driver = {
    id: driverId,
    name: "Example Driver",
    email: "driver@example.invalid",
    accountant_id: null,
    accountant_name: "Taylor Accountant",
    created_at: "2026-10-20T12:00:00Z",
  };
  await page.route("**/api/v1/staff/drivers/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/overview"))
      return route.fulfill({
        json: {
          ...driver,
          tax_year: "2026-27",
          utr_masked: null,
          ni_masked: null,
          driver_profile: {},
          subscription: { status: "active" },
          totals: {
            income_pence: 100000,
            deductible_expenses_pence: 12000,
            profit_pence: 88000,
            estimated_tax_pence: null,
            business_miles: "100",
            pending_receipts: 1,
            unresolved_issues: 0,
          },
        },
      });
    if (path.endsWith("/content"))
      return route.fulfill({
        contentType: "image/svg+xml",
        body: '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="900"><rect width="600" height="900" fill="white"/><text x="80" y="100" font-size="30">Example receipt</text></svg>',
      });
    if (path.endsWith("/review")) {
      version++;
      reviewStatus = "confirmed";
      return route.fulfill({
        json: { receipt: receipt(), mutation_id: "exact-review-mutation" },
      });
    }
    if (path.endsWith("/reversals")) {
      reversals.push(route.request().postDataJSON());
      version++;
      reviewStatus = "reversed";
      return route.fulfill({ json: { receipt: receipt() } });
    }
    if (path.endsWith("/receipts/receipt-example"))
      return route.fulfill({ json: receipt() });
    if (path.endsWith("/receipts/search"))
      return route.fulfill({
        json: { items: [receipt()], total: 1, page: 1, page_size: 25 },
      });
    return route.fulfill({
      json: {
        items: path.endsWith("/drivers/search") ? [driver] : [],
        total: path.endsWith("/drivers/search") ? 1 : 0,
        page: 1,
        page_size: 25,
      },
    });
  });
  await page
    .getByRole("link", { name: "Driver directory", exact: true })
    .click();
  await page.getByRole("link", { name: /Example Driver/ }).click();
  await page.getByRole("tab", { name: "Expenses", exact: true }).click();
  await page.getByRole("tab", { name: "Receipt review queue" }).click();
  await page
    .getByRole("button", { name: "Review receipt", exact: true })
    .click();
  await expect(
    page.getByRole("meter", { name: "AI extraction confidence" }),
  ).toHaveAttribute("aria-valuenow", "92");
  await expect(page.getByAltText("Uploaded receipt evidence")).toBeVisible();
  await page
    .getByRole("button", { name: "Zoom in receipt", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Reset receipt zoom", exact: true }),
  ).toHaveText("125%");
  await checkAccessibility(page);
  await page
    .getByLabel("Review / correction reason")
    .fill("Check synthetic receipt evidence");
  await page.getByRole("button", { name: "Approve", exact: true }).click();
  await expect(page.getByText("This receipt is already posted")).toBeVisible();
  await page.getByRole("button", { name: "Undo", exact: true }).click();
  await expect(
    page.getByText("Review undone. The exact confirmation was reversed."),
  ).toBeVisible();
  expect(reversals).toEqual([
    {
      expected_version: 2,
      mutation_id: "exact-review-mutation",
      reason: "Undo approve: Check synthetic receipt evidence",
    },
  ]);
});
