import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement } from "react";
import { useRuns } from "@/hooks/useRuns";
import { useRun } from "@/hooks/useRun";

const mockFetch = vi.fn();
beforeEach(() => { vi.stubGlobal("fetch", mockFetch); });
afterEach(() => { vi.restoreAllMocks(); });

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return createElement(QueryClientProvider, { client: qc }, children);
}

describe("useRuns", () => {
  it("returns runs list from API", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ runs: [{ run_id: "r1", status: "completed", stage: "done", message: "", created_at: "", updated_at: "" }], total: 1 }),
    });
    const { result } = renderHook(() => useRuns(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.total).toBe(1);
    expect(result.current.data?.runs[0].run_id).toBe("r1");
  });
});

describe("useRun", () => {
  it("is disabled when runId is empty", () => {
    const { result } = renderHook(() => useRun(""), { wrapper });
    expect(result.current.fetchStatus).toBe("idle");
  });

  it("fetches single run by id", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ run_id: "r1", status: "running", stage: "collecting", message: "...", created_at: "", updated_at: "" }),
    });
    const { result } = renderHook(() => useRun("r1"), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.run_id).toBe("r1");
  });
});
