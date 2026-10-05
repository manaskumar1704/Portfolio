import type { Metadata } from "next";
import { JetBrains_Mono } from "next/font/google";
import { AgentPanel } from "@/features/agent/agent-panel";
import { BootOverlay } from "@/features/shell/boot-overlay";
import { CrtOverlay } from "@/features/shell/crt-overlay";
import { Statusbar } from "@/features/shell/statusbar";
import { Topbar } from "@/features/shell/topbar";
import "./globals.css";

const jetbrains = JetBrains_Mono({
  variable: "--font-jetbrains",
  weight: ["400", "500", "700"],
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Manas — GenAI & Full-Stack Engineer",
  description:
    "Manas, GenAI & Full-Stack Engineer — talk to his agent in a terminal-style console.",
};

/**
 * The chrome and the console live here, not in each page.
 *
 * AgentPanel holds the composer, and the layout does not unmount on a route
 * change, so `cd ..` swaps the page underneath without throwing away the
 * conversation. Moving it into the pages would destroy it on every navigation.
 */
export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${jetbrains.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        <CrtOverlay />
        <BootOverlay />
        <Topbar />
        <main>
          <AgentPanel />
          {children}
        </main>
        <Statusbar />
      </body>
    </html>
  );
}