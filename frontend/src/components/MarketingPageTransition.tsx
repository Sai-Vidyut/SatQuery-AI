"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { SolarLoader } from "@/components/ui/solar-loader";

const MARKETING_PATHS = new Set(["/", "/tutorial", "/credits"]);

/** Opacity-only fade — avoids translateY layout gaps. */
export const PAGE_TRANSITION_MS = 750;

type Props = {
  children: ReactNode;
};

export function MarketingPageTransition({ children }: Props) {
  const pathname = usePathname();
  const isMarketing = MARKETING_PATHS.has(pathname);
  const isWorkstation = pathname === "/workstation";
  const [showLoader, setShowLoader] = useState(false);
  const prevPathnameRef = useRef(pathname);
  const entryKeyRef = useRef(0);

  if (prevPathnameRef.current !== pathname) {
    entryKeyRef.current += 1;
  }

  useEffect(() => {
    prevPathnameRef.current = pathname;
  }, [pathname]);

  useEffect(() => {
    if (!isMarketing) return;
    setShowLoader(true);
    const timer = window.setTimeout(() => setShowLoader(false), PAGE_TRANSITION_MS);
    return () => window.clearTimeout(timer);
  }, [pathname, isMarketing]);

  if (!isMarketing && !isWorkstation) {
    return <>{children}</>;
  }

  const variant = isWorkstation ? "workstation" : "marketing";

  return (
    <>
      <div
        key={`${variant}-${entryKeyRef.current}`}
        className={`page-transition page-transition--${variant} page-transition--enter`}
      >
        {children}
      </div>

      {isMarketing && showLoader ? (
        <div
          className="marketing-transition-loader marketing-transition-loader--visible"
          aria-hidden="true"
        >
          <SolarLoader size={30} speed={2} />
        </div>
      ) : null}
    </>
  );
}
