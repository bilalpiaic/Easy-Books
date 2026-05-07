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
    <html lang="en" className={`${dmSans.variable} h-full antialiased`}>
      <body className="h-full font-sans bg-[#f6f3ee] text-[#1a1814] overflow-hidden">
        {children}
      </body>
    </html>
  );
}
