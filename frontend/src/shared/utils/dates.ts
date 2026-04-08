/**
 * Date formatting utilities — all output in the browser's local timezone.
 * Backend timestamps are UTC; these helpers ensure consistent local display.
 */

/** Parse a backend date string (UTC) into a Date object. */
export function parseUTC(raw: string): Date {
  // Backend formats: "yyyy-MM-dd", "yyyy-MM-dd HH:00", "yyyy-MM-dd HH:mm"
  // Frontend dateKey formats: "yyyy-MM-ddTHH" (hour granularity), "yyyy-MM-ddTHH:mm" (5-min)
  // Normalize to ISO 8601 with Z suffix so JS treats it as UTC
  if (raw.length === 10) return new Date(raw + "T00:00:00Z");
  // "YYYY-MM-DDTHH" (13 chars, hour granularity from dateKey) → pad with :00:00Z
  if (raw.length === 13 && raw[10] === "T") return new Date(raw + ":00:00Z");
  if (raw.includes("T")) return new Date(raw.endsWith("Z") ? raw : raw + "Z");
  // "yyyy-MM-dd HH:mm" → "yyyy-MM-ddTHH:mmZ"
  return new Date(raw.replace(" ", "T") + "Z");
}

/** Format a UTC date string as a short axis label in local time. */
export function formatAxisLabel(raw: string): string {
  const d = parseUTC(raw);
  if (raw.length <= 10) {
    // Daily: "Mar 2"
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: undefined });
  }
  // Hourly / 5-min: "3:30 PM" or "15:00"
  return d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
}

/** Format a UTC date string as a full local timestamp. */
export function formatTimestamp(raw: string): string {
  return parseUTC(raw).toLocaleString("en-US", {
    month: "short", day: "numeric",
    hour: "numeric", minute: "2-digit",
  });
}

/** Format a UTC date string as a short local date. */
export function formatDate(raw: string): string {
  return parseUTC(raw).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

/** Format a UTC date string as local time only. */
export function formatTime(raw: string): string {
  return parseUTC(raw).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", second: "2-digit" });
}
