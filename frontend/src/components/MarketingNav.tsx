import Image from "next/image";
import Link from "next/link";
import { HomeNav } from "@/components/home/HomeNav";

export function MarketingNav() {
  return (
    <>
      <Link href="/home" className="marketing-nav__logo" data-testid="site-nav-brand">
        <Image
          src="/LOGO.png"
          alt="SatQuery"
          width={1340}
          height={343}
          className="marketing-nav__logo-image"
          priority
        />
      </Link>
      <HomeNav />
    </>
  );
}
