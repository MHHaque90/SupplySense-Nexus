import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import { endpoints } from "../api/endpoints";
import { useApproval } from "./Copilot";

const APPROVAL_A = "app-test-alpha";
const APPROVAL_B = "app-test-beta";

function aDecisionSucceeds() {
  vi.spyOn(endpoints, "aiApproval").mockResolvedValue({
    data: {
      approval_id: APPROVAL_A,
      decision: "approve",
      status: "approved",
      decided_by: "user-test",
      decided_at: "2026-10-19T12:00:00Z",
      executed: false,
    },
    meta: { timestamp: "t", data_source_label: "derived" },
  });
}

function aDecisionFails() {
  vi.spyOn(endpoints, "aiApproval").mockRejectedValue(
    new ApiError(409, "CONFLICT", "Approval is already decided.", {
      details: { reason: "already approved" },
    })
  );
}

const statusOf = (pending: Map<string, "pending" | "approved" | "rejected">, id: string) =>
  pending.get(id);

describe("copilot approval state", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("approval appears as pending when returned by chat meta", () => {
    const { result } = renderHook(() => useApproval());
    act(() => {
      result.current.register([APPROVAL_A, APPROVAL_B]);
    });
    expect(statusOf(result.current.pending, APPROVAL_A)).toBe("pending");
    expect(statusOf(result.current.pending, APPROVAL_B)).toBe("pending");
    expect(result.current.pending.size).toBe(2);
  });

  it("approval state updates after a successful decision", async () => {
    aDecisionSucceeds();
    const { result } = renderHook(() => useApproval());
    act(() => {
      result.current.register([APPROVAL_A]);
    });
    await act(async () => {
      await result.current.decide(APPROVAL_A, "approve");
    });
    expect(endpoints.aiApproval).toHaveBeenCalledWith(APPROVAL_A, "approve");
    expect(statusOf(result.current.pending, APPROVAL_A)).toBe("approved");
    expect(result.current.error).toBeNull();
  });

  it("a rejected decision leaves every approval exactly as it was", async () => {
    aDecisionFails();
    const { result } = renderHook(() => useApproval());
    act(() => {
      result.current.register([APPROVAL_A]);
    });
    await act(async () => {
      await result.current.decide(APPROVAL_A, "reject");
    });
    expect(statusOf(result.current.pending, APPROVAL_A)).toBe("pending");
    expect(result.current.error).toContain("CONFLICT");
  });

  it("multiple approvals do not overwrite each other", () => {
    const { result } = renderHook(() => useApproval());
    act(() => {
      result.current.register([APPROVAL_A, APPROVAL_B]);
    });
    act(() => {
      result.current.register([APPROVAL_A, "app-test-gamma"]);
    });
    expect(statusOf(result.current.pending, APPROVAL_A)).toBe("pending");
    expect(statusOf(result.current.pending, APPROVAL_B)).toBe("pending");
    expect(statusOf(result.current.pending, "app-test-gamma")).toBe("pending");
    expect(result.current.pending.size).toBe(3);
  });

  it("a new chat response does not reset an already decided approval", async () => {
    aDecisionSucceeds();
    const { result } = renderHook(() => useApproval());
    act(() => {
      result.current.register([APPROVAL_A]);
    });
    await act(async () => {
      await result.current.decide(APPROVAL_A, "reject");
    });
    expect(statusOf(result.current.pending, APPROVAL_A)).toBe("rejected");
    act(() => {
      result.current.register([APPROVAL_A]);
    });
    expect(statusOf(result.current.pending, APPROVAL_A)).toBe("rejected");
  });

  it("updates approval chip status dynamically from pending to approved upon decision", async () => {
    aDecisionSucceeds();
    const { result } = renderHook(() => useApproval());
    act(() => {
      result.current.register([APPROVAL_A]);
    });
    expect(result.current.pending.get(APPROVAL_A)).toBe("pending");
    await act(async () => {
      await result.current.decide(APPROVAL_A, "approve");
    });
    expect(result.current.pending.get(APPROVAL_A)).toBe("approved");
  });
});

