import type { Metadata } from "next";
import { Inter, Roboto_Mono, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/providers/AuthProvider";
import { SWRProvider } from "@/lib/providers/SWRProvider";
import { WebSocketProvider } from "@/lib/providers/WebSocketProvider";
import { ToastProvider } from "@/components/primitives/Toast";
import { WebSocketToastBridge } from "@/components/WebSocketToastBridge";
import { DashboardShell } from "@/components/dashboard/DashboardShell";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const robotoMono = Roboto_Mono({
  subsets: ["latin"],
  variable: "--font-roboto-mono",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Cortexa - Memory Observability",
  description:
    "The only memory infrastructure that can tell you which memory caused your agent's last mistake",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} ${robotoMono.variable} ${jetbrainsMono.variable}`}>
      <body className="font-sans antialiased grain">
        <AuthProvider>
          <SWRProvider>
            <ToastProvider>
              <WebSocketProvider>
                <WebSocketToastBridge />
                <DashboardShell>{children}</DashboardShell>
              </WebSocketProvider>
            </ToastProvider>
          </SWRProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
