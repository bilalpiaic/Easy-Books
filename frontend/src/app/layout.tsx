import type { Metadata, Viewport } from "next";
import { DM_Sans, Noto_Nastaliq_Urdu } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/context/ThemeContext";
import { LocaleProvider } from "@/context/LocaleContext";
import { SerwistProvider } from "@/components/SerwistProvider";

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-dm-sans",
});

const nastaliqUrdu = Noto_Nastaliq_Urdu({
  subsets: ["arabic"],
  weight: ["400", "700"],
  variable: "--font-nastaliq",
  display: "swap",
});

export const metadata: Metadata = {
  applicationName: "Easy-Books",
  title: "Easy-Books — Financial Management System",
  description: "State-of-the-art multi-tenant financial management system",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "Easy-Books",
  },
  formatDetection: {
    telephone: false,
  },
  icons: {
    apple: "/icons/apple-touch-icon.png",
  },
};

export const viewport: Viewport = {
  themeColor: "#b8943f",
};

// SECURITY NOTE: dangerouslySetInnerHTML is safe here because this script is a
// compile-time constant with no user input, no external data, and no dynamic
// interpolation. This is the standard Next.js pattern (used by next-themes,
// Chakra, Mantine) for applying tokens synchronously before first paint to
// prevent flash of wrong theme/direction. Never interpolate user data here.
const antiFlashScript = `
try {
  var t = localStorage.getItem('eb.theme') || 'light';
  var c = localStorage.getItem('eb.color') || 'gold';
  var l = localStorage.getItem('eb.lang')  || 'en';
  if (t === 'system') t = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', t);
  document.documentElement.setAttribute('data-color', c);
  document.documentElement.lang = l;
  document.documentElement.dir  = l === 'ur' ? 'rtl' : 'ltr';
} catch(e) {}
`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${dmSans.variable} ${nastaliqUrdu.variable} antialiased`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: antiFlashScript }} />
      </head>
      <body className="min-h-screen font-sans bg-[#f6f3ee] text-[#1a1814]" suppressHydrationWarning>
        <SerwistProvider swUrl="/serwist/sw.js">
          <ThemeProvider>
            <LocaleProvider>
              {children}
            </LocaleProvider>
          </ThemeProvider>
        </SerwistProvider>
      </body>
    </html>
  );
}
