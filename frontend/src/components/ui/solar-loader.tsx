"use client";

import React from "react";
import { cn } from "@/lib/utils";

export interface SolarLoaderProps {
  size?: number;
  speed?: number;
  className?: string;
}

const PLANETS = [
  { color: "from-gray-300 to-gray-600", orbit: 2.5, size: 0.3, duration: 2, ring: false },
  { color: "from-yellow-200 to-yellow-500", orbit: 3.5, size: 0.4, duration: 3, ring: false },
  { color: "from-sky-300 to-blue-700", orbit: 4.5, size: 0.45, duration: 4, ring: false },
  { color: "from-red-300 to-red-700", orbit: 5.5, size: 0.4, duration: 5, ring: false },
  { color: "from-amber-300 to-amber-700", orbit: 7, size: 0.8, duration: 6, ring: false },
  { color: "from-orange-300 to-orange-700", orbit: 8, size: 0.7, duration: 7, ring: true },
  { color: "from-teal-200 to-cyan-600", orbit: 9, size: 0.6, duration: 8, ring: false },
  { color: "from-blue-400 to-indigo-700", orbit: 10, size: 0.6, duration: 9, ring: false },
] as const;

export function SolarLoader({ size = 40, speed = 1, className }: SolarLoaderProps) {
  return (
    <div
      className={cn("relative mx-auto flex items-center justify-center", className)}
      style={{
        width: `${size * 10}px`,
        height: `${size * 10}px`,
        perspective: "1200px",
      }}
      role="status"
      aria-label="Loading"
    >
      <div
        className="solar-loader__tilt relative [transform-style:preserve-3d]"
        style={{ width: "100%", height: "100%" }}
      >
        <div
          className="absolute left-1/2 top-40 bg-gradient-to-r from-neutral-500/60 to-neutral-300/60"
          style={{
            width: `${size * 10}px`,
            height: "1.5px",
            transform: "translate(-50%, -50%) rotate(38deg)",
            boxShadow: "0 0 8px rgba(255,255,255,0.3)",
            zIndex: 0,
          }}
        />

        <div
          className="absolute flex items-center justify-center rounded-full bg-gradient-to-br from-yellow-200 to-orange-400"
          style={{
            width: `${size}px`,
            height: `${size}px`,
            boxShadow:
              "0 0 40px rgba(255, 200, 0, 0.7), inset 0 0 15px rgba(255,255,255,0.5)",
            transform: "translateZ(30px)",
            zIndex: 10,
          }}
        />

        {PLANETS.map((planet, i) => (
          <div
            key={i}
            className="solar-loader__orbit absolute rounded-full border border-neutral-700"
            style={{
              width: `${planet.orbit * size}px`,
              height: `${planet.orbit * size}px`,
              animationDuration: `${planet.duration / speed}s`,
              transformStyle: "preserve-3d",
              transform: `rotateX(20deg) translateZ(${(i % 2 === 0 ? 1 : -1) * 25}px)`,
            }}
          >
            <div
              className={cn(
                "absolute rounded-full bg-gradient-to-br shadow-inner",
                planet.color,
              )}
              style={{
                width: `${planet.size * size}px`,
                height: `${planet.size * size}px`,
                top: "50%",
                left: "100%",
                transform: "translate(-50%, -50%) rotateX(15deg)",
                boxShadow:
                  "inset -6px -6px 12px rgba(0,0,0,0.6), inset 4px 4px 8px rgba(255,255,255,0.2)",
              }}
            >
              <div
                className="absolute rounded-full bg-white/40 blur-[2px]"
                style={{
                  width: `${planet.size * size * 0.3}px`,
                  height: `${planet.size * size * 0.3}px`,
                  top: "25%",
                  left: "25%",
                  opacity: 0.6,
                }}
              />

              {planet.ring ? (
                <div
                  className="absolute bg-gradient-to-r from-neutral-400 to-neutral-200 opacity-80"
                  style={{
                    width: `${planet.size * size * 2}px`,
                    height: "1.5px",
                    top: "50%",
                    left: "50%",
                    transform: "translate(-50%, -50%) rotate(25deg)",
                  }}
                />
              ) : null}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default SolarLoader;
