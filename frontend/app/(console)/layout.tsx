import type { ReactNode } from "react";
import { ProtectedLayout } from "@/components/layout/app-shell";

export default function ConsoleLayout({ children }: { children: ReactNode }) {
  return <ProtectedLayout>{children}</ProtectedLayout>;
}
