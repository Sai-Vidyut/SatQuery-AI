import { Playfair_Display } from "next/font/google";

const playfairDisplay = Playfair_Display({
  subsets: ["latin"],
  weight: ["400"],
  variable: "--font-home-display",
  display: "swap",
});

export default function HomeLayout({ children }: { children: React.ReactNode }) {
  return <div className={`home-route ${playfairDisplay.variable}`}>{children}</div>;
}
