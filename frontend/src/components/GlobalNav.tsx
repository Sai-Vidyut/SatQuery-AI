"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import {
  BookOpen,
  Heart,
  Home,
  Info,
  Map as MapIcon,
  Menu,
} from "lucide-react";

const NAV_ITEMS = [
  { href: "/home", label: "Home", Icon: Home, testId: "site-nav-link-home" },
  { href: "/", label: "Workstation", Icon: MapIcon, testId: "site-nav-link-workstation" },
  { href: "/tutorial", label: "Tutorial", Icon: BookOpen, testId: "site-nav-link-tutorial" },
  { href: "/about", label: "About", Icon: Info, testId: "site-nav-link-about" },
  { href: "/credits", label: "Credits", Icon: Heart, testId: "site-nav-link-credits" },
] as const;

function isActivePath(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function GlobalNav() {
  const pathname = usePathname();
  const menuId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [overDarkHero, setOverDarkHero] = useState(false);

  const close = useCallback(() => setOpen(false), []);
  const toggle = useCallback(() => setOpen((value) => !value), []);

  useEffect(() => {
    close();
  }, [pathname, close]);

  useEffect(() => {
    if (pathname !== "/home") {
      setOverDarkHero(false);
      return;
    }

    const hero = document.getElementById("home-hero");
    if (!hero) {
      setOverDarkHero(false);
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        setOverDarkHero(entry.isIntersecting && entry.intersectionRatio > 0.35);
      },
      {
        threshold: [0, 0.35, 0.6],
        rootMargin: "-72px 0px 0px 0px",
      },
    );

    observer.observe(hero);
    return () => observer.disconnect();
  }, [pathname]);

  useEffect(() => {
    if (!open) return;

    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as Node;
      if (rootRef.current?.contains(target)) return;
      close();
    };

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
    };

    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open, close]);

  const isWorkstation = pathname === "/";

  const navMenu = (
    <>
      <button
        type="button"
        className="site-nav__trigger"
        data-testid="site-nav-trigger"
        aria-label={open ? "Close menu" : "Open menu"}
        aria-expanded={open}
        aria-controls={menuId}
        onClick={toggle}
      >
        <Menu size={20} strokeWidth={2} aria-hidden="true" />
      </button>

      <div
        id={menuId}
        className={`site-nav__menu${open ? " site-nav__menu--open" : ""}`}
        data-testid="site-nav-menu"
        aria-hidden={!open}
        inert={!open}
      >
        <nav aria-label="Site">
          <ul className="site-nav__list">
            {NAV_ITEMS.map(({ href, label, Icon, testId }) => {
              const active = isActivePath(pathname, href);
              return (
                <li key={href} className="site-nav__item">
                  <Link
                    href={href}
                    data-testid={testId}
                    className={`site-nav__link${active ? " site-nav__link--active" : ""}`}
                    aria-current={active ? "page" : undefined}
                    tabIndex={open ? 0 : -1}
                    onClick={close}
                  >
                    <span className="site-nav__icon" aria-hidden="true">
                      <Icon size={16} strokeWidth={2} />
                    </span>
                    <span className="site-nav__label">{label}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
      </div>
    </>
  );

  if (isWorkstation) {
    return (
      <div ref={rootRef} className="site-nav site-nav--standalone">
        {navMenu}
      </div>
    );
  }

  return (
    <header
      className={`site-nav-bar${overDarkHero ? " site-nav-bar--inverse" : ""}`}
    >
      <div className="site-nav-bar__pill">
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

        <div ref={rootRef} className="site-nav">
          {navMenu}
        </div>
      </div>
    </header>
  );
}
