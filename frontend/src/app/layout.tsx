import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { GlobalNav } from "@/components/GlobalNav";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "SatQuery AI",
  description: "Evidence-driven satellite intelligence workstation",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body>
        <GlobalNav />
        {children}
      </body>
    </html>
  );
}
