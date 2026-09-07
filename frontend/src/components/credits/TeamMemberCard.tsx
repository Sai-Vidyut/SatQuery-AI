import { Code, Terminal, type LucideIcon } from "lucide-react";

export type TeamMember = {
  name: string;
  role: string;
  education: string;
  tags: string[];
  BadgeIcon: LucideIcon;
  github: string;
  linkedin: string;
};

function GitHubIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
    >
      <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.205 0 1.59-.015 2.88-.015 3.285 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z" />
    </svg>
  );
}

function LinkedInIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-4 0v7h-4v-11h4v2" />
      <rect x="2" y="9" width="4" height="12" />
      <circle cx="4" cy="4" r="2" />
    </svg>
  );
}

export const TEAM_MEMBERS: TeamMember[] = [
  {
    name: "Sai Vidyut C",
    role: "Backend & AI Systems Lead",
    education: "B.Tech · SRMIST",
    tags: ["Python", "FastAPI", "AI/ML", "System Design"],
    BadgeIcon: Code,
    github: "https://github.com/placeholder",
    linkedin: "https://linkedin.com/in/placeholder",
  },
  {
    name: "Josh Jiby",
    role: "Frontend & Product Experience Lead",
    education: "B.Tech · SRMIST",
    tags: ["React", "Next.js", "TypeScript", "UI/UX"],
    BadgeIcon: Code,
    github: "https://github.com/placeholder",
    linkedin: "https://linkedin.com/in/placeholder",
  },
  {
    name: "Fathima Rinaya",
    role: "Product Strategy & Communication Lead",
    education: "B.Tech · SRMIST",
    tags: ["Product Strategy", "Research", "Communication"],
    BadgeIcon: Terminal,
    github: "https://github.com/placeholder",
    linkedin: "https://linkedin.com/in/placeholder",
  },
];

type TeamMemberCardProps = {
  member: TeamMember;
};

export function TeamMemberCard({ member }: TeamMemberCardProps) {
  const BadgeIcon = member.BadgeIcon;

  return (
    <article className="credits-card glass">
      <div className="credits-card__body">
        <div className="credits-card__identity">
          <h2 className="credits-card__name">
            <BadgeIcon
              size={15}
              strokeWidth={2}
              className="credits-card__badge"
              aria-hidden="true"
            />
            <span>{member.name}</span>
          </h2>
          <p className="credits-card__role">{member.role}</p>
          <p className="credits-card__education">{member.education}</p>
        </div>

        <ul className="credits-card__tags" aria-label={`${member.name} skills`}>
          {member.tags.map((tag) => (
            <li key={tag}>
              <span className="credits-card__tag">{tag}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="credits-card__links">
        <a
          href={member.github}
          className="credits-card__link"
          target="_blank"
          rel="noopener noreferrer"
          aria-label={`${member.name} on GitHub`}
        >
          <GitHubIcon />
          <span>GitHub</span>
        </a>
        <a
          href={member.linkedin}
          className="credits-card__link"
          target="_blank"
          rel="noopener noreferrer"
          aria-label={`${member.name} on LinkedIn`}
        >
          <LinkedInIcon />
          <span>LinkedIn</span>
        </a>
      </div>
    </article>
  );
}
