import Image from "next/image";
import Link from "next/link";

export function HomeHeroLogo() {
  return (
    <Link href="/home" className="home-hero-logo" data-testid="site-nav-brand">
      <Image
        src="/LOGO.png"
        alt="SatQuery"
        width={1340}
        height={343}
        className="home-hero-logo__image"
        priority
      />
    </Link>
  );
}
