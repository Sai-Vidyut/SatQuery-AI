import { HomeAboutSection } from "@/components/home/HomeAboutSection";
import { HomeFooter } from "@/components/home/HomeFooter";
import { HomeTransitionBand } from "@/components/home/HomeTransitionBand";
import { MarketingNav } from "@/components/MarketingNav";
import { ResponsiveHeroBanner } from "@/components/ui/responsive-hero-banner";

export default function HomePage() {
  return (
    <>
      <MarketingNav />
      <ResponsiveHeroBanner />
      <HomeTransitionBand />
      <HomeAboutSection />
      <HomeFooter />
    </>
  );
}
