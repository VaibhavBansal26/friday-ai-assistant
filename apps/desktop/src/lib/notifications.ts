import type { FridayNotification } from "./api";

const delivered = new Set<string>();

export function deliverGrantedNotifications(items: FridayNotification[]): number {
  if (typeof Notification === "undefined" || Notification.permission !== "granted") return 0;
  let count = 0;
  for (const item of items) {
    if (item.read || item.dismissed || delivered.has(item.id)) continue;
    new Notification(item.title, { body: item.body, tag: item.id });
    delivered.add(item.id);
    count += 1;
  }
  return count;
}

export function notificationPermission(): NotificationPermission | "unsupported" {
  return typeof Notification === "undefined" ? "unsupported" : Notification.permission;
}

