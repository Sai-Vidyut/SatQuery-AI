import { Playfair_Display } from "next/font/google";
import { MarketingNav } from "@/components/MarketingNav";

const playfairDisplay = Playfair_Display({
  subsets: ["latin"],
  weight: ["400"],
  variable: "--font-home-display",
  display: "swap",
});

export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className={`marketing-route ${playfairDisplay.variable}`}>
      <MarketingNav />
      {children}
    </div>
  );
}