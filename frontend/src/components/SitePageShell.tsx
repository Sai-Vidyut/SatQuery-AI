type Props = {
  title: string;
};

export function SitePageShell({ title }: Props) {
  return (
    <main className="site-page">
      <h1 className="site-page__title">{title}</h1>
    </main>
  );
}
