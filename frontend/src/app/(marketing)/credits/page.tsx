import { TEAM_MEMBERS, TeamMemberCard } from "@/components/credits/TeamMemberCard";

export default function CreditsPage() {
  return (
    <main className="credits-page">
      <section className="credits-page__section credits-page__section--intro">
        <div className="credits-page__container">
          <p className="credits-page__eyebrow">SatQuery</p>
          <h1 className="credits-page__title">Built by Team SatQuery</h1>
          <p className="credits-page__intro">
            SatQuery AI is an evidence-driven satellite intelligence platform built by a
            three-person team from SRMIST.
          </p>
          <p className="credits-page__status">
            SatQuery AI is under active development. Some features run in clearly labeled
            demonstration mode when live providers are not configured.
          </p>
        </div>
      </section>

      <section className="credits-page__section credits-page__section--team" aria-label="Team">
        <div className="credits-page__container">
          <ul className="credits-page__grid">
            {TEAM_MEMBERS.map((member) => (
              <li key={member.name}>
                <TeamMemberCard member={member} />
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="credits-page__section credits-page__section--about">
        <div className="credits-page__container credits-page__about">
          <h2 className="credits-page__about-title">About this project</h2>
          <p className="credits-page__about-body">
            SatQuery is a map-first workstation where you draw an area, ask a question in plain
            language, and read evidence-backed answers on the map — with a transparent analysis
            trace alongside the view.
          </p>
          <p className="credits-page__disclaimer">
            SatQuery AI is an independent student project and is not officially affiliated with or
            endorsed by SRMIST.
          </p>
        </div>
      </section>
    </main>
  );
}
