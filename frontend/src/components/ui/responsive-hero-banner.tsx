import Link from "next/link";
import { cn } from "@/lib/utils";

export type ResponsiveHeroBannerProps = {
  backgroundImageUrl?: string;
  badgeLabel?: string;
  badgeText?: string;
  title?: string;
  titleLine2?: string;
  description?: string;
  primaryButtonText?: string;
  primaryButtonHref?: string;
  scrollHint?: string;
  className?: string;
};

const DEFAULTS = {
  backgroundImageUrl: "/hero-earth.jpg",
  badgeLabel: "New",
  badgeText: "Earth Observation Intelligence",
  title: "SATQUERY",
  titleLine2: "Interactive Vision-Language Intelligence",
  description: "For Earth Observation",
  primaryButtonText: "ENTER WORKSTATION",
  primaryButtonHref: "/",
  scrollHint: "SCROLL TO EXPLORE",
} as const;

export function ResponsiveHeroBanner({
  backgroundImageUrl = DEFAULTS.backgroundImageUrl,
  badgeLabel = DEFAULTS.badgeLabel,
  badgeText = DEFAULTS.badgeText,
  title = DEFAULTS.title,
  titleLine2 = DEFAULTS.titleLine2,
  description = DEFAULTS.description,
  primaryButtonText = DEFAULTS.primaryButtonText,
  primaryButtonHref = DEFAULTS.primaryButtonHref,
  scrollHint = DEFAULTS.scrollHint,
  className,
}: ResponsiveHeroBannerProps) {
  return (
    <section
      id="home-hero"
      className={cn("responsive-hero-banner", className)}
      aria-label="SatQuery AI hero"
    >
      <div
        className="responsive-hero-banner__bg"
        style={{ backgroundImage: `url("${backgroundImageUrl}")` }}
        aria-hidden="true"
      />
      <div className="responsive-hero-banner__overlay" aria-hidden="true" />

      <div className="responsive-hero-banner__content">
        {badgeText ? (
          <div className="responsive-hero-banner__badge hero-animate hero-animate--1">
            {badgeLabel ? (
              <span className="responsive-hero-banner__badge-label">{badgeLabel}</span>
            ) : null}
            <span>{badgeText}</span>
          </div>
        ) : null}

        <h1 className="responsive-hero-banner__title hero-animate hero-animate--2">
          <span className="responsive-hero-banner__title-line">{title}</span>
        </h1>

        {titleLine2 ? (
          <p className="responsive-hero-banner__subtitle hero-animate hero-animate--3">
            {titleLine2}
          </p>
        ) : null}

        {description ? (
          <p className="responsive-hero-banner__tagline hero-animate hero-animate--4">
            {description}
          </p>
        ) : null}

        <div className="responsive-hero-banner__actions hero-animate hero-animate--5">
          <Link
            href={primaryButtonHref}
            className="btn-primary responsive-hero-banner__cta"
          >
            {primaryButtonText}
          </Link>
        </div>
      </div>

      {scrollHint ? (
        <p className="responsive-hero-banner__scroll hero-animate hero-animate--6">{scrollHint}</p>
      ) : null}
    </section>
  );
}
