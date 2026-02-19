import type { Metadata } from "next";
import { Cinzel, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "../components/ThemeProvider";

const cinzel = Cinzel({
  variable: "--font-serif",
  subsets: ["latin"],
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Manas | Architecting Digital Realities",
  description: "Portfolio of Manas - Full Stack Developer & UI Architect",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning className={`${cinzel.variable} ${jetbrainsMono.variable}`}>
      <body className="antialiased bg-background text-foreground min-h-screen selection:bg-reiatsu/30 selection:text-white">
        <ThemeProvider
          attribute="class"
          defaultTheme="dark"
          forcedTheme="dark" /* Force dark mode for Aizen aesthetic */
          enableSystem={false}
          disableTransitionOnChange
        >
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
