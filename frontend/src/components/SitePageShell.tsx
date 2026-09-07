import type { ReactNode } from "react";

type Props = {
  title: string;
  eyebrow?: string;
  lead?: string;
  children?: ReactNode;
};

export function SitePageShell({ title, eyebrow, lead, children }: Props) {
  return (
    <main className="site-page">
      <section className="site-page__section site-page__section--primary">
        <div className="site-page__container">
          {eyebrow ? <p className="site-page__eyebrow">{eyebrow}</p> : null}
          <h1 className="site-page__title">{title}</h1>
          {lead ? <p className="site-page__lead">{lead}</p> : null}
          {children ? <div className="site-page__panel glass">{children}</div> : null}
        </div>
      </section>
    </main>
  );
}
