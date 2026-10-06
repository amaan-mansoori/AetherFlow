export function safeReturnPath(value: string | null): string | null {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.includes("\\")) {
    return null;
  }
  try {
    const destination = new URL(value, "https://aetherflow.invalid");
    if (destination.origin !== "https://aetherflow.invalid" || destination.pathname.startsWith("//")) {
      return null;
    }
    return `${destination.pathname}${destination.search}${destination.hash}`;
  } catch {
    return null;
  }
}
