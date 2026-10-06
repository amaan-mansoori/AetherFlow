export function formatDate(value: string | null | undefined, options?: Intl.DateTimeFormatOptions): string {
  if (!value) return "—";
  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) return "Unknown time";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
    ...options,
  }).format(timestamp);
}

export function compactId(value: string, size = 8): string {
  return value.length > size ? value.slice(0, size) : value;
}

export function safeJson(value: unknown, maxChars = 12000): string {
  const serialized = JSON.stringify(value, null, 2);
  return serialized.length > maxChars
    ? `${serialized.slice(0, maxChars)}\n… output clipped in the console`
    : serialized;
}
