"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import {
  BookOpen,
  Heart,
  Home,
  Map as MapIcon,
  Menu,
} from "lucide-react";

const NAV_ITEMS = [
  { href: "/", label: "Home", Icon: Home, testId: "site-nav-link-home" },
  { href: "/workstation", label: "Workstation", Icon: MapIcon, testId: "site-nav-link-workstation" },
  { href: "/tutorial", label: "Tutorial", Icon: BookOpen, testId: "site-nav-link-tutorial" },
  { href: "/credits", label: "Credits", Icon: Heart, testId: "site-nav-link-credits" },
] as const;

function isActivePath(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/" || pathname === "/home";
  if (href === "/workstation") return pathname === "/workstation";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export type SiteMenuVariant = "standalone" | "toolbar" | "pill";

type SiteMenuProps = {
  variant?: SiteMenuVariant;
  theme?: "light" | "dark";
};

export function SiteMenu({ variant = "standalone", theme = "light" }: SiteMenuProps) {
  const pathname = usePathname();
  const menuId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);

  const close = useCallback(() => setOpen(false), []);
  const toggle = useCallback(() => setOpen((value) => !value), []);

  useEffect(() => {
    close();
  }, [pathname, close]);

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

  const surfaceClass = theme === "dark" ? "glass" : "glass-light";

  const menuPanel = (
    <div
      id={menuId}
      className={`site-nav__menu ${surfaceClass}${open ? " site-nav__menu--open" : ""}`}
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
  );

  if (variant === "toolbar") {
    return (
      <div ref={rootRef} className="site-nav site-nav--toolbar site-nav--toolbar-end">
        <button
          type="button"
          className="map-tool-btn site-nav__trigger site-nav__trigger--toolbar"
          data-testid="site-nav-trigger"
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          aria-controls={menuId}
          onClick={toggle}
        >
          <Menu size={20} strokeWidth={2} aria-hidden="true" />
        </button>
        {menuPanel}
      </div>
    );
  }

  if (variant === "pill") {
    return (
      <div ref={rootRef} className="site-nav">
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
        {menuPanel}
      </div>
    );
  }

  return (
    <div ref={rootRef} className="site-nav site-nav--standalone">
      <button
        type="button"
        className="site-nav__trigger glass-light"
        data-testid="site-nav-trigger"
        aria-label={open ? "Close menu" : "Open menu"}
        aria-expanded={open}
        aria-controls={menuId}
        onClick={toggle}
      >
        <Menu size={20} strokeWidth={2} aria-hidden="true" />
      </button>
      {menuPanel}
    </div>
  );
}
