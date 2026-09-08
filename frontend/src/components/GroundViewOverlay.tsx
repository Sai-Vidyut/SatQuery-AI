"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { GroundViewPoint } from "@/lib/aoiGroundView";
import {
  GROUND_VIEW_DISCLOSURE,
  GROUND_VIEW_PANORAMA_HINT,
  formatGroundViewCoordinates,
  formatGroundViewHeading,
  headingFromPan,
  initialPanPercent,
  panoramaTranslatePercent,
} from "@/lib/aoiGroundView";

type Props = {
  point: GroundViewPoint;
  onClose: () => void;
};

export function GroundViewOverlay({ point, onClose }: Props) {
  const [pan, setPan] = useState(() => initialPanPercent(point.heading));
  const dragRef = useRef<{ startX: number; startPan: number; pointerId: number } | null>(null);
  const stageRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setPan(initialPanPercent(point.heading));
  }, [point.id, point.heading]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
    };

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [onClose]);

  const updatePanFromDelta = useCallback((deltaX: number) => {
    const stage = stageRef.current;
    if (!stage || !dragRef.current) return;
    const deltaPan = deltaX / stage.clientWidth;
    const next = Math.min(1, Math.max(0, dragRef.current.startPan - deltaPan));
    setPan(next);
  }, []);

  const onPointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!point.panorama360) return;
    dragRef.current = {
      startX: event.clientX,
      startPan: pan,
      pointerId: event.pointerId,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const onPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!dragRef.current || dragRef.current.pointerId !== event.pointerId) return;
    updatePanFromDelta(event.clientX - dragRef.current.startX);
  };

  const onPointerUp = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!dragRef.current || dragRef.current.pointerId !== event.pointerId) return;
    dragRef.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  };

  const displayHeading = headingFromPan(point.heading, pan);
  const translatePercent = point.panorama360
    ? panoramaTranslatePercent(pan, point.panoramaSpan)
    : 0;

  return (
    <div
      className="ground-view-overlay"
      data-testid="ground-view-overlay"
      role="dialog"
      aria-modal="true"
      aria-label={`Ground View: ${point.title}`}
    >
      <button
        type="button"
        className="ground-view-overlay__close"
        data-testid="ground-view-close"
        onClick={onClose}
        aria-label="Close Ground View"
      >
        ×
      </button>

      <div
        ref={stageRef}
        className={`ground-view-overlay__stage${point.panorama360 ? " ground-view-overlay__stage--panorama" : ""}`}
        data-testid="ground-view-stage"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      >
        <div
          className="ground-view-overlay__frame"
          style={
            point.panorama360
              ? {
                  width: `${point.panoramaSpan * 100}%`,
                  transform: `translateX(${translatePercent}%)`,
                }
              : undefined
          }
        >
          <img
            src={point.imageUrl}
            alt={point.imageAlt}
            className="ground-view-overlay__image"
            data-testid="ground-view-image"
            draggable={false}
          />
        </div>
        <div className="ground-view-overlay__vignette" aria-hidden="true" />
        {point.panorama360 ? (
          <p className="ground-view-overlay__pan-hint" data-testid="ground-view-panorama-hint">
            {GROUND_VIEW_PANORAMA_HINT}
          </p>
        ) : null}
      </div>

      <div className="ground-view-overlay__meta">
        <p className="ground-view-overlay__eyebrow">Ground View</p>
        <span className="ground-view-overlay__badge" data-testid="ground-view-demo-badge">
          DEMO DATA
        </span>
        {point.panorama360 ? (
          <span className="ground-view-overlay__badge ground-view-overlay__badge--muted">
            Mock 360°
          </span>
        ) : null}
        <h2 className="ground-view-overlay__title" data-testid="ground-view-title">
          {point.title}
        </h2>
        <p className="ground-view-overlay__description" data-testid="ground-view-description">
          {point.description}
        </p>
        <dl className="ground-view-overlay__details">
          <div>
            <dt>Coordinates</dt>
            <dd data-testid="ground-view-coordinates">
              {formatGroundViewCoordinates(point.latitude, point.longitude)}
            </dd>
          </div>
          <div>
            <dt>Heading</dt>
            <dd data-testid="ground-view-heading">{formatGroundViewHeading(displayHeading)}</dd>
          </div>
          <div>
            <dt>Capture date</dt>
            <dd data-testid="ground-view-capture-date">{point.captureDate}</dd>
          </div>
        </dl>
        <p className="ground-view-overlay__disclosure" data-testid="ground-view-disclosure">
          {GROUND_VIEW_DISCLOSURE}
        </p>
      </div>
    </div>
  );
}
