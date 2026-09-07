import Link from "next/link";
import { SitePageShell } from "@/components/SitePageShell";

const STEPS = [
  "Choose a mode: AOI + dates, single upload, temporal pair, or cross-modal optical + SAR.",
  "Draw an area on the map or upload imagery, then write your question in plain language.",
  "Run analysis and read the answer, evidence regions, and execution trace in the Results panel.",
] as const;

export default function TutorialPage() {
  return (
    <SitePageShell
      title="Tutorial"
      eyebrow="Getting started"
      lead="A quick walkthrough of the SatQuery workstation workflow."
    >
      <ol className="site-page__steps">
        {STEPS.map((step) => (
          <li key={step}>{step}</li>
        ))}
      </ol>
      <p>
        On your first visit to the workstation, an guided tour highlights the query bar, analysis
        modes, map tools, and results panel. Use the <strong>?</strong> button bottom-left to replay
        it anytime.
      </p>
      <p className="site-page__cta-row">
        <Link href="/" className="site-page__cta">
          Open workstation
        </Link>
      </p>
    </SitePageShell>
  );
}
