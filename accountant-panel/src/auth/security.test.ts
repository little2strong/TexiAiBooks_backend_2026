// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { can } from "./permissions";
import { session } from "./session";
import { request } from "../api/client";
import { authProvider } from "../api/providers";
import type { StaffLoginResult } from "../api/types";

const identity: StaffLoginResult = {
  access_token: "synthetic-test-token",
  expires_in: 60,
  staff: {
    id: "synthetic",
    name: "Synthetic accountant",
    email: "synthetic@example.invalid",
    role: "accountant",
    team_id: null,
  },
};
afterEach(() => {
  session.end();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("staff credential boundary", () => {
  it("starts a staff session directly from email/password without a verification request", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        new Response(JSON.stringify(identity), { status: 200 }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const store = vi.spyOn(Storage.prototype, "setItem");
    expect(
      await authProvider.login({
        email: identity.staff.email,
        password: "synthetic-password",
      }),
    ).toMatchObject({ success: true });
    expect(session.token()).toBe(identity.access_token);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/staff\/auth\/login$/);
    expect(JSON.parse(options.body)).toEqual({
      email: identity.staff.email,
      password: "synthetic-password",
    });
    expect(options.headers.has("Authorization")).toBe(false);
    expect(store).not.toHaveBeenCalled();
  });
  it("keeps an invalid email/password response signed out", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("{}", { status: 401 })),
    );
    expect(
      await authProvider.login({
        email: identity.staff.email,
        password: "incorrect-password",
      }),
    ).toMatchObject({ success: false });
    expect(session.get()).toBeNull();
  });
  it("expires credentials in memory without writing either browser store", () => {
    vi.useFakeTimers();
    const store = vi.spyOn(Storage.prototype, "setItem");
    session.start(identity);
    expect(session.token()).toBe("synthetic-test-token");
    vi.advanceTimersByTime(60001);
    expect(session.token()).toBeNull();
    expect(session.get()).toBeNull();
    expect(store).not.toHaveBeenCalled();
  });
  it("clears the session on server rejection and does not retry writes", async () => {
    session.start(identity);
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response("{}", { status: 401 }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(
      request("/staff/handoffs/assign", { method: "POST", body: {} }),
    ).rejects.toMatchObject({ statusCode: 401 });
    expect(session.get()).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
  it("sends identifier searches in a body, and public recovery without a bearer", async () => {
    session.start(identity);
    const fetchMock = vi
      .fn()
      .mockImplementation(() =>
        Promise.resolve(new Response("{}", { status: 200 })),
      );
    vi.stubGlobal("fetch", fetchMock);
    await request("/staff/drivers/search", {
      method: "POST",
      body: { search: "1234567890" },
    });
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).not.toContain("1234567890");
    expect(options.body).toContain("1234567890");
    await request("/auth/forgot-password", {
      method: "POST",
      public: true,
      body: { email: "test@example.invalid" },
    });
    expect(fetchMock.mock.calls[1][1].headers.has("Authorization")).toBe(false);
  });
  it("denies support financial mutations and permits internal support notes", () => {
    for (const action of [
      "edit",
      "assign",
      "reveal",
      "message",
      "export",
      "admin",
      "approve_submission",
    ] as const)
      expect(can("support", action)).toBe(false);
    expect(can("support", "note")).toBe(true);
    expect(can(undefined, "read")).toBe(false);
    expect(can("accountant", "approve_submission")).toBe(false);
    expect(can("senior_accountant", "approve_submission")).toBe(true);
  });
});
