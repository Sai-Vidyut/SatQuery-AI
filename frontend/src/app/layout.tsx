import type { Metadata } from "next";
import { Inter, Instrument_Serif } from "next/font/google";
import { GlobalNav } from "@/components/GlobalNav";
import { MarketingPageTransition } from "@/components/MarketingPageTransition";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-inter",
  display: "swap",
});

const instrumentSerif = Instrument_Serif({
  subsets: ["latin"],
  weight: ["400"],
  variable: "--font-instrument-serif",
  display: "swap",
});

export const metadata: Metadata = {
  title: "SatQuery AI",
  description: "Evidence-driven satellite intelligence workstation",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${instrumentSerif.variable}`}>
      <body>
        <GlobalNav />
        <MarketingPageTransition>{children}</MarketingPageTransition>
      </body>
    </html>
  );
}
