import type { Metadata } from "next";
import { DM_Sans } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/context/ThemeContext";

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-dm-sans",
});

export const metadata: Metadata = {
  title: "Easy-Books — Financial Management System",
  description: "State-of-the-art multi-tenant financial management system",
};

// SECURITY NOTE: dangerouslySetInnerHTML is safe here because themeScript is a
// compile-time constant with no user input, no external data, and no dynamic
// interpolation. This is the standard Next.js pattern (used by next-themes,
// Chakra, Mantine) for applying theme tokens synchronously before first paint
// to prevent flash of wrong theme. Never interpolate user data into this string.
const themeScript = `
try {
  var t = localStorage.getItem('eb.theme') || 'light';
  var c = localStorage.getItem('eb.color') || 'gold';
  if (t === 'system') t = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', t);
  document.documentElement.setAttribute('data-color', c);
} catch(e) {}
`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${dmSans.variable} antialiased`} suppressHydrationWarning>
      <head>
        {/* Anti-flash: set data-theme/data-color before first paint */}
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-screen font-sans bg-[#f6f3ee] text-[#1a1814]" suppressHydrationWarning>
        <ThemeProvider>
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
