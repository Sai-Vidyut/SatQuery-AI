import { HomeAboutSection } from "@/components/home/HomeAboutSection";
import { HomeFooter } from "@/components/home/HomeFooter";
import { HomeNav } from "@/components/home/HomeNav";
import { HomeTransitionBand } from "@/components/home/HomeTransitionBand";
import { ResponsiveHeroBanner } from "@/components/ui/responsive-hero-banner";

export default function HomePage() {
  return (
    <>
      <HomeNav />
      <ResponsiveHeroBanner />
      <HomeTransitionBand />
      <HomeAboutSection />
      <HomeFooter />
    </>
  );
}
