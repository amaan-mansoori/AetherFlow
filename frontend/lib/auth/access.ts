import type { User } from "@/types/api";

export function canAccessAdmin(user: User | null): boolean {
  return Boolean(user?.roles.includes("ADMIN") && !user.roles.includes("DEMO"));
}

export function isDemoUser(user: User | null): boolean {
  return user?.roles.includes("DEMO") ?? false;
}
