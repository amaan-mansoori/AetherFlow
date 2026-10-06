import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { Providers } from "@/app/providers";
import "@fontsource-variable/inter/wght.css";
import "@fontsource/ibm-plex-mono/latin-400.css";
import "@fontsource/ibm-plex-mono/latin-500.css";
import "./product.css";

export const metadata: Metadata = {
  title: {
    default: "AetherFlow — Operations",
    template: "%s · AetherFlow",
  },
  description: "A production operations console for asynchronous AI workloads.",
  applicationName: "AetherFlow",
};

export const viewport: Viewport = {
  themeColor: "#090b0d",
  colorScheme: "dark",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
