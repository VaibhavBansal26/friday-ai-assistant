import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("Friday API client", () => {
  it("loads typed tasks from the local gateway", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => ({ session: { id: "session-1" }, token: "token-1" }) })
      .mockResolvedValueOnce({ ok: true, json: async () => [{ id: "task-1", title: "Verify Friday", status: "inbox" }] });
    vi.stubGlobal("fetch", fetchMock);
    const tasks = await api.listTasks();
    expect(tasks[0].title).toBe("Verify Friday");
    expect(fetchMock).toHaveBeenLastCalledWith(
      "http://127.0.0.1:8000/v1/tasks",
      expect.objectContaining({ headers: expect.objectContaining({ "content-type": "application/json" }) }),
    );
  });

  it("sends only the requested task fields", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ id: "task-1" }) });
    vi.stubGlobal("fetch", fetchMock);
    await api.updateTask("task-1", { status: "completed" });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/v1/tasks/task-1",
      expect.objectContaining({ method: "PATCH", body: JSON.stringify({ status: "completed" }) }),
    );
  });

  it("returns a safe error without copying provider response bodies", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 503 }));
    await expect(api.listTasks()).rejects.toThrow("Friday API request failed (503)");
  });
});
