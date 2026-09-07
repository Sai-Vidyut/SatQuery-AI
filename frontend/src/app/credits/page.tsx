const TEAM = ["Sai Vidyut C", "Josh Jiby", "Fathima Rinaya"] as const;

export default function CreditsPage() {
  return (
    <main className="credits-page">
      <h1 className="credits-page__title">Credits</h1>
      <ul className="credits-page__list">
        {TEAM.map((name) => (
          <li key={name}>{name}</li>
        ))}
      </ul>
    </main>
  );
}
