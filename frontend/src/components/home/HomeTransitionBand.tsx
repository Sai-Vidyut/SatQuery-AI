type HomeTransitionBandProps = {
  tagline?: string;
};

export function HomeTransitionBand({ tagline }: HomeTransitionBandProps) {
  return (
    <section
      className="home-bridge"
      aria-label={tagline ? "SatQuery tagline" : undefined}
      aria-hidden={!tagline}
    >
      {tagline ? <p className="home-bridge__tagline">{tagline}</p> : null}
    </section>
  );
}
