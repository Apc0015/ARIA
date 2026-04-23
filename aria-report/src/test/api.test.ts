import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { api } from "@/lib/api";

const mockFetch = vi.fn();
beforeEach(() => { vi.stubGlobal("fetch", mockFetch); });
afterEach(() => { vi.restoreAllMocks(); });

function mockOk(body: unknown) {
  mockFetch.mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(body),
  });
}

function mockError(status: number, text: string) {
  mockFetch.mockResolvedValue({
    ok: false,
    status,
    statusText: text,
    text: () => Promise.resolve(text),
  });
}

describe("api.runs.list", () => {
  it("fetches GET /api/runs", async () => {
    mockOk({ runs: [], total: 0 });
    const result = await api.runs.list();
    expect(mockFetch).toHaveBeenCalledWith("/api/runs", expect.objectContaining({}));
    expect(result.total).toBe(0);
  });

  it("throws on non-ok response", async () => {
    mockError(500, "Internal Server Error");
    await expect(api.runs.list()).rejects.toThrow("500");
  });
});

describe("api.runs.start", () => {
  it("posts to /api/runs with JSON body", async () => {
    mockOk({ run_id: "abc", status: "pending", stage: "", message: "", created_at: "", updated_at: "" });
    await api.runs.start({ topic: "AI Safety" });
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/runs",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ topic: "AI Safety" }) })
    );
  });
});

describe("api.credentials.save", () => {
  it("posts credentials as JSON", async () => {
    mockOk({ status: "saved" });
    await api.credentials.save({ REDDIT_CLIENT_ID: "abc" });
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/credentials",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ REDDIT_CLIENT_ID: "abc" }) })
    );
  });
});

describe("api.exports", () => {
  it("returns correct markdown URL", () => {
    expect(api.exports.markdown("run-123")).toBe("/api/runs/run-123/export/markdown");
  });
  it("returns correct json URL", () => {
    expect(api.exports.json("run-123")).toBe("/api/runs/run-123/export/clean/json");
  });
});
