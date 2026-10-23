import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ErrorBoundary } from "@/components/shared/ErrorBoundary";

afterEach(() => { vi.restoreAllMocks(); });

let shouldThrow = true;
function Flaky() {
  if (shouldThrow) throw new Error("chunk failed to load");
  return <p>Page content</p>;
}

describe("ErrorBoundary", () => {
  it("shows a recovery card instead of a blank page, and recovers on retry", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    shouldThrow = true;
    render(
      <ErrorBoundary context="Monitor">
        <Flaky />
      </ErrorBoundary>
    );

    expect(screen.getByRole("alert")).toBeTruthy();
    expect(screen.getByText("Something went wrong in Monitor")).toBeTruthy();
    expect(screen.getByText("chunk failed to load")).toBeTruthy();

    shouldThrow = false;
    fireEvent.click(screen.getByText("Try again"));
    expect(screen.getByText("Page content")).toBeTruthy();
  });
});
