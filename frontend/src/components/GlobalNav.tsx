"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { SiteMenu } from "@/components/SiteMenu";

export function GlobalNav() {
  const pathname = usePathname();
  const isWorkstation = pathname === "/";
  const isHome = pathname === "/home";

  if (isHome || isWorkstation) {
    return null;
  }

  return (
    <header className="site-nav-bar">
      <div className="site-nav-bar__pill glass-light">
        <Link href="/home" className="site-nav-bar__brand" data-testid="site-nav-brand">
          <Image
            src="/LOGO.png"
            alt="SatQuery"
            width={1340}
            height={343}
            className="site-nav-bar__logo"
            priority
          />
        </Link>

        <SiteMenu variant="pill" />
      </div>
    </header>
  );
}
