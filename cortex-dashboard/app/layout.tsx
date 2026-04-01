import type { Metadata } from "next";
import { Inter, Roboto_Mono } from "next/font/google";
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

export const metadata: Metadata = {
  metadataBase: new URL("https://cortexadev.com"),
  title: {
    default: "Cortexa – Memory Observability for AI Agents",
    template: "%s | Cortexa",
  },
  description:
    "The only memory infrastructure that tells you which memory caused your AI agent's last mistake. Real-time attribution, GDPR compliance, hallucination detection, and memory lifecycle management.",
  keywords: [
    "AI agent memory",
    "memory observability",
    "LLM memory management",
    "agent attribution",
    "hallucination detection",
    "GDPR AI compliance",
    "Shapley values",
    "ContextCite",
    "AI infrastructure",
    "memory lifecycle",
  ],
  authors: [{ name: "Cortexa", url: "https://cortexadev.com" }],
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true },
  },
  openGraph: {
    type: "website",
    url: "https://cortexadev.com",
    title: "Cortexa – Memory Observability for AI Agents",
    description:
      "The only memory infrastructure that tells you which memory caused your AI agent's last mistake.",
    siteName: "Cortexa",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "Cortexa – Memory Observability for AI Agents",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Cortexa – Memory Observability for AI Agents",
    description:
      "Real-time attribution, hallucination detection, and memory lifecycle management for AI agents.",
    images: ["/og-image.png"],
  },
  alternates: {
    canonical: "https://cortexadev.com",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} ${robotoMono.variable}`}>
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
