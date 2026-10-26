import { afterEach, describe, expect, it, vi } from "vitest";
import type { FridayNotification } from "./api";
import { deliverGrantedNotifications, notificationPermission } from "./notifications";

const item = (id: string): FridayNotification => ({
  id,
  title: "Friday update",
  body: "A task is ready",
  severity: "info",
  category: "task",
  target_path: null,
  read: false,
  dismissed: false,
  created_at: new Date().toISOString(),
});

afterEach(() => vi.unstubAllGlobals());

describe("desktop notifications", () => {
  it("does not request permission or deliver when permission is not granted", () => {
    const NotificationMock = vi.fn();
    Object.assign(NotificationMock, { permission: "default" });
    vi.stubGlobal("Notification", NotificationMock);
    expect(deliverGrantedNotifications([item("permission-test")])).toBe(0);
    expect(NotificationMock).not.toHaveBeenCalled();
  });

  it("delivers a granted notification only once", () => {
    const NotificationMock = vi.fn();
    Object.assign(NotificationMock, { permission: "granted" });
    vi.stubGlobal("Notification", NotificationMock);
    const notification = item("dedupe-test");
    expect(deliverGrantedNotifications([notification])).toBe(1);
    expect(deliverGrantedNotifications([notification])).toBe(0);
    expect(NotificationMock).toHaveBeenCalledTimes(1);
  });

  it("reports unsupported environments", () => {
    vi.stubGlobal("Notification", undefined);
    expect(notificationPermission()).toBe("unsupported");
  });
});

