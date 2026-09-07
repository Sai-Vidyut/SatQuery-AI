import { ResponsiveHeroBanner } from "@/components/ui/responsive-hero-banner";

/**
 * Optional reference demo — not wired into the app router.
 * Uses SatQuery defaults; nav/wordmark live in GlobalNav (root layout).
 */
export default function HeroDemo() {
  return (
    <ResponsiveHeroBanner
      badgeText="Earth Observation Intelligence"
      title="SATQUERY"
      titleLine2="Interactive Vision-Language Intelligence"
      description="For Earth Observation"
      primaryButtonText="ENTER WORKSTATION"
      primaryButtonHref="/"
    />
  );
}
