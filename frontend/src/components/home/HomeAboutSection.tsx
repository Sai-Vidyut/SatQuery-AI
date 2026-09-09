import Link from "next/link";
import { ImagePlaceholder } from "@/components/home/ImagePlaceholder";

const INTRO_IMAGE = {
  src: "/home-workstation.png",
  alt: "SatQuery workstation with map, query composer, and results panel",
} as const;

const USE_CASES = [
  {
    slug: "agriculture",
    src: "/home-use-case-agriculture.jpg",
    title: "Agriculture & land monitoring",
    description:
      "Track crop health, seasonal land cover shifts, and field-level changes across growing cycles — without building a custom GIS workflow for every question.",
  },
  {
    slug: "disaster-response",
    src: "/home-use-case-disaster-response.jpg",
    title: "Disaster response",
    description:
      "Quickly assess damage, flooding, or displacement from before-and-after imagery when speed matters and manual analysis would take too long.",
  },
  {
    slug: "infrastructure",
    src: "/home-use-case-infrastructure.jpg",
    title: "Infrastructure & urban monitoring",
    description:
      "Monitor construction, encroachment, and infrastructure changes over time to spot what changed between acquisitions.",
  },
  {
    slug: "research",
    src: "/home-use-case-research.jpg",
    title: "Research & analysis",
    description:
      "Ask exploratory questions about any region and follow the evidence on the map — useful when you need insight, not another desktop GIS session.",
  },
] as const;

export function HomeAboutSection() {
  return (
    <div className="home-about" id="about">
      <section className="home-about__section home-about__section--intro" aria-labelledby="home-intro-heading">
        <div className="home-about__container home-about__intro">
          <div className="home-about__intro-copy">
            <p className="home-about__eyebrow">Why SatQuery</p>
            <h2 id="home-intro-heading" className="home-about__title">
              Satellite intelligence, without the GIS overhead
            </h2>
            <p className="home-about__lead">
              SatQuery is a map-first workstation where you draw an area, ask a question in plain
              English, and read evidence-backed answers on the map — with a transparent results
              panel and analysis trace alongside the view.
            </p>
            <p className="home-about__body">
              Demo mode is clearly labeled when live satellite catalog data is not connected, so
              you always know whether you are viewing real observations or demonstration fixtures.
            </p>
          </div>
          <ImagePlaceholder
            src={INTRO_IMAGE.src}
            alt={INTRO_IMAGE.alt}
            variant="hero"
            className="home-about__intro-visual"
          />
        </div>
      </section>

      <section
        className="home-about__section home-about__section--use-cases"
        aria-labelledby="home-use-cases-heading"
      >
        <div className="home-about__container">
          <div className="home-about__section-header">
            <p className="home-about__eyebrow">Who it&apos;s for</p>
            <h2 id="home-use-cases-heading" className="home-about__title home-about__title--section">
              Built for real-world questions
            </h2>
          </div>
          <div className="home-about__use-cases">
            {USE_CASES.map(({ slug, src, title, description }, index) => (
              <article
                key={slug}
                className={`home-use-case${index % 2 === 1 ? " home-use-case--reverse" : ""}`}
              >
                <ImagePlaceholder
                  src={src}
                  alt={title}
                  variant="default"
                  className="home-use-case__visual"
                />
                <div className="home-use-case__body">
                  <h3 className="home-use-case__title">{title}</h3>
                  <p className="home-use-case__copy">{description}</p>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="home-about__section home-about__section--cta" aria-labelledby="home-cta-heading">
        <div className="home-about__container home-about__cta">
          <h2 id="home-cta-heading" className="home-about__title home-about__title--section">
            Try it yourself
          </h2>
          <p className="home-about__cta-copy">
            Open the workstation, upload or select imagery, and ask your first question in plain
            English.
          </p>
          <Link href="/workstation" className="responsive-hero-banner__cta home-about__cta-button">
            ENTER WORKSTATION
          </Link>
        </div>
      </section>
    </div>
  );
}
