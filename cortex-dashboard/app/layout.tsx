import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { SWRProvider } from "@/lib/providers/SWRProvider";
import { WebSocketProvider } from "@/lib/providers/WebSocketProvider";
import { ToastProvider } from "@/components/primitives/Toast";
import { Navigation } from "@/components/Navigation";
import { WebSocketToastBridge } from "@/components/WebSocketToastBridge";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "CortexOS - Memory Observability",
  description:
    "The only memory infrastructure that can tell you which memory caused your agent's last mistake",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable}`}>
      <body className="font-sans antialiased grain">
        <SWRProvider>
          <ToastProvider>
            <WebSocketProvider>
              <WebSocketToastBridge />
              <div className="flex min-h-screen">
                <Navigation />
                <main className="flex-1 ml-[var(--sidebar-width)] overflow-y-auto min-h-screen">
                  <div className="page-container">{children}</div>
                </main>
              </div>
            </WebSocketProvider>
          </ToastProvider>
        </SWRProvider>
      </body>
    </html>
  );
}
