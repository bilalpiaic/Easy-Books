import type { Metadata } from "next";
import { DM_Sans } from "next/font/google";
import "./globals.css";

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-dm-sans",
});

export const metadata: Metadata = {
  title: "Easy-Books — Financial Management System",
  description: "State-of-the-art multi-tenant financial management system",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${dmSans.variable} antialiased`}>
      {/* `min-h-full` + no `overflow-hidden` lets the document scroll on
          login/signup. The dashboard layout has its own internal scroll
          container (`<main className="overflow-y-auto">`), so the global
          flow doesn't affect it. */}
      <body className="min-h-screen font-sans bg-[#f6f3ee] text-[#1a1814]">
        {children}
      </body>
    </html>
  );
}
