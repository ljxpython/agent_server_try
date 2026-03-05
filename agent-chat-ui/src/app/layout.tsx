import type { Metadata } from "next";
import { IBM_Plex_Sans } from "next/font/google";
import { NuqsAdapter } from "nuqs/adapters/next/app";
import type { ReactNode } from "react";
import { Suspense } from "react";

import "./globals.css";

import { GlobalAuthGuard } from "@/components/platform/global-auth-guard";

const ibmPlexSans = IBM_Plex_Sans({
  subsets: ["latin"],
  preload: true,
  display: "swap",
  variable: "--font-sans",
});

export const metadata: Metadata = {
  title: "Agent Chat",
  description: "Agent Chat UX by LangChain",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${ibmPlexSans.variable} font-sans`}>
        <NuqsAdapter>
          <Suspense fallback={<div className="p-6">Loading...</div>}>
            <GlobalAuthGuard>{children}</GlobalAuthGuard>
          </Suspense>
        </NuqsAdapter>
      </body>
    </html>
  );
}
