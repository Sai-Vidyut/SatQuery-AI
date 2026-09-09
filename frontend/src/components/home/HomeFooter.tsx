import Link from "next/link";

const REPO_URL = "https://github.com/Sai-Vidyut/SatQuery-AI";

function GitHubIcon() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
    >
      <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.205 0 1.59-.015 2.88-.015 3.285 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z" />
    </svg>
  );
}

export function HomeFooter() {
  return (
    <footer className="home-footer">
      <div className="home-footer__inner">
        <div className="home-footer__columns">
          <div className="home-footer__column">
            <p className="home-footer__heading">Product</p>
            <ul className="home-footer__links">
              <li>
                <Link href="/workstation">Workstation</Link>
              </li>
              <li>
                <Link href="/tutorial">Tutorial</Link>
              </li>
              <li>
                <Link href="#about">About</Link>
              </li>
            </ul>
          </div>

          <div className="home-footer__column">
            <p className="home-footer__heading">Team</p>
            <ul className="home-footer__links">
              <li>
                <Link href="/credits">Credits</Link>
              </li>
              <li>
                <a href={REPO_URL} target="_blank" rel="noopener noreferrer">
                  GitHub repo
                </a>
              </li>
            </ul>
          </div>

          <div className="home-footer__column home-footer__column--about">
            <p className="home-footer__heading">About the project</p>
            <p className="home-footer__about">
              SatQuery AI — a functional prototype for interactive Earth observation intelligence.
            </p>
          </div>
        </div>

        <div className="home-footer__bar">
          <p className="home-footer__copy">© 2026 Team SatQuery</p>
          <a
            href={REPO_URL}
            className="home-footer__github"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="SatQuery AI on GitHub"
          >
            <GitHubIcon />
          </a>
        </div>
      </div>
    </footer>
  );
}
