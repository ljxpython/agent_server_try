import type { Metadata } from "next";
import "./globals.css";
import { IBM_Plex_Sans } from "next/font/google";
import React from "react";
import { NuqsAdapter } from "nuqs/adapters/next/app";

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
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${ibmPlexSans.variable} font-sans`}>
        <NuqsAdapter>{children}</NuqsAdapter>
      </body>
    </html>
  );
}
