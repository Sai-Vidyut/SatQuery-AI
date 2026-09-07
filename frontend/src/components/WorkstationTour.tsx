"use client";

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { HelpCircle } from "lucide-react";
import type { ComposerInputMode } from "@/components/QueryComposer";

export const TOUR_STORAGE_KEY = "satquery_tour_seen";

type StepDef = {
  id: string;
  title: string;
  body: string;
  resolveTargets: (inputMode: ComposerInputMode) => HTMLElement[];
};

type HighlightBox = {
  top: number;
  left: number;
  width: number;
  height: number;
};

type PopoverPosition = {
  top: number;
  left: number;
  placement: "above" | "below";
};

const PADDING = 8;
const GAP = 14;
const VIEWPORT_MARGIN = 16;
const POPOVER_WIDTH = 320;
const POPOVER_ESTIMATE_HEIGHT = 180;

const STEPS: StepDef[] = [
  {
    id: "query",
    title: "Ask your question",
    body: "Ask your question here, in plain language.",
    resolveTargets: () => {
      const el = document.querySelector<HTMLElement>('[data-tour="composer-query"]');
      return el ? [el] : [];
    },
  },
  {
    id: "modes",
    title: "Choose your analysis mode",
    body: "Draw an area, upload one image, compare two dates, or combine optical + SAR.",
    resolveTargets: () => {
      const el = document.querySelector<HTMLElement>('[data-tour="composer-mode-row"]');
      return el ? [el] : [];
    },
  },
  {
    id: "draw-aoi",
    title: "Draw your area",
    body: "Draw a box on the map to mark your area of interest.",
    resolveTargets: () => {
      const el = document.querySelector<HTMLElement>('[data-tour="rail-draw-aoi"]');
      return el ? [el] : [];
    },
  },
  {
    id: "upload",
    title: "Or upload your own imagery",
    body: "Upload a satellite image instead of drawing an area.",
    resolveTargets: (inputMode) => {
      if (inputMode === "catalog") return [];

      const selectors: Record<Exclude<ComposerInputMode, "catalog">, string[]> = {
        upload: ['[data-tour="composer-upload-single"]'],
        temporal_pair: [
          '[data-tour="composer-upload-earlier"]',
          '[data-tour="composer-upload-later"]',
        ],
        cross_modal: [
          '[data-tour="composer-upload-optical"]',
          '[data-tour="composer-upload-sar"]',
        ],
      };

      return selectors[inputMode]
        .map((sel) => document.querySelector<HTMLElement>(sel))
        .filter((el): el is HTMLElement => el != null);
    },
  },
  {
    id: "run",
    title: "Run it",
    body: "Run the analysis once you're set up.",
    resolveTargets: () => {
      const el = document.querySelector<HTMLElement>('[data-tour="composer-run"]');
      return el ? [el] : [];
    },
  },
  {
    id: "map-tools",
    title: "Zoom & layers",
    body: "Zoom, pan, and toggle map layers here.",
    resolveTargets: () => {
      const el = document.querySelector<HTMLElement>('[data-tour="map-tools"]');
      return el ? [el] : [];
    },
  },
  {
    id: "results",
    title: "Your results",
    body: "Your answer and supporting evidence will appear here.",
    resolveTargets: () => {
      const el = document.querySelector<HTMLElement>('[data-tour="inspector-slot"]');
      return el ? [el] : [];
    },
  },
];

function unionRect(elements: HTMLElement[]): DOMRect | null {
  if (elements.length === 0) return null;

  let top = Infinity;
  let left = Infinity;
  let right = -Infinity;
  let bottom = -Infinity;

  for (const el of elements) {
    const rect = el.getBoundingClientRect();
    top = Math.min(top, rect.top);
    left = Math.min(left, rect.left);
    right = Math.max(right, rect.right);
    bottom = Math.max(bottom, rect.bottom);
  }

  return new DOMRect(left, top, right - left, bottom - top);
}

function rectWithPadding(rect: DOMRect, pad: number): HighlightBox {
  return {
    top: rect.top - pad,
    left: rect.left - pad,
    width: rect.width + pad * 2,
    height: rect.height + pad * 2,
  };
}

function computePopoverPosition(
  box: HighlightBox,
  popoverHeight: number,
): PopoverPosition {
  const viewportW = window.innerWidth;
  const viewportH = window.innerHeight;
  const popoverWidth = Math.min(POPOVER_WIDTH, viewportW - VIEWPORT_MARGIN * 2);

  const targetCenterY = box.top + box.height / 2;
  const preferAbove = targetCenterY > viewportH / 2;

  let placement: "above" | "below" = preferAbove ? "above" : "below";
  let top =
    placement === "above"
      ? box.top - GAP - popoverHeight
      : box.top + box.height + GAP;

  const fitsAbove = top >= VIEWPORT_MARGIN;
  const fitsBelow =
    box.top + box.height + GAP + popoverHeight <= viewportH - VIEWPORT_MARGIN;

  if (placement === "above" && !fitsAbove && fitsBelow) {
    placement = "below";
    top = box.top + box.height + GAP;
  } else if (placement === "below" && !fitsBelow && fitsAbove) {
    placement = "above";
    top = box.top - GAP - popoverHeight;
  }

  top = Math.max(VIEWPORT_MARGIN, Math.min(top, viewportH - VIEWPORT_MARGIN - popoverHeight));

  let left = box.left + box.width / 2 - popoverWidth / 2;
  left = Math.max(VIEWPORT_MARGIN, Math.min(left, viewportW - popoverWidth - VIEWPORT_MARGIN));

  return { top, left, placement };
}

type Props = {
  inputMode: ComposerInputMode;
  onActiveChange?: (active: boolean) => void;
};

export function WorkstationTour({ inputMode, onActiveChange }: Props) {
  const popoverRef = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);
  const [highlight, setHighlight] = useState<HighlightBox | null>(null);
  const [popover, setPopover] = useState<PopoverPosition | null>(null);

  const applicableSteps = useMemo(() => {
    return STEPS.filter((step) => step.id !== "upload" || inputMode !== "catalog");
  }, [inputMode]);

  const totalSteps = applicableSteps.length;
  const currentStep = applicableSteps[stepIndex] ?? null;
  const isFirst = stepIndex === 0;
  const isLast = stepIndex === totalSteps - 1;

  const finishTour = useCallback(
    (markSeen: boolean) => {
      if (markSeen && typeof window !== "undefined") {
        localStorage.setItem(TOUR_STORAGE_KEY, "1");
      }
      setActive(false);
      setStepIndex(0);
      setHighlight(null);
      setPopover(null);
      onActiveChange?.(false);
    },
    [onActiveChange],
  );

  const startTour = useCallback(() => {
    setStepIndex(0);
    setHighlight(null);
    setPopover(null);
    setActive(true);
    onActiveChange?.(true);
  }, [onActiveChange]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (localStorage.getItem(TOUR_STORAGE_KEY)) return;

    const timer = window.setTimeout(() => {
      startTour();
    }, 600);

    return () => window.clearTimeout(timer);
  }, [startTour]);

  const measureStep = useCallback(() => {
    if (!currentStep) return;

    const targets = currentStep.resolveTargets(inputMode);
    const rect = unionRect(targets);
    if (!rect || rect.width <= 0 || rect.height <= 0) {
      setHighlight(null);
      setPopover(null);
      return;
    }

    const box = rectWithPadding(rect, PADDING);
    setHighlight(box);

    const popoverHeight = popoverRef.current?.offsetHeight ?? POPOVER_ESTIMATE_HEIGHT;
    setPopover(computePopoverPosition(box, popoverHeight));
  }, [currentStep, inputMode]);

  useLayoutEffect(() => {
    if (!active || !currentStep) return;

    measureStep();
    const frame = requestAnimationFrame(() => measureStep());

    return () => cancelAnimationFrame(frame);
  }, [active, currentStep, stepIndex, inputMode, measureStep]);

  useEffect(() => {
    if (!active || !popoverRef.current) return;

    const node = popoverRef.current;
    const observer = new ResizeObserver(() => measureStep());
    observer.observe(node);

    return () => observer.disconnect();
  }, [active, measureStep, stepIndex, currentStep?.id]);

  useEffect(() => {
    if (!active) return;

    const onLayout = () => measureStep();
    window.addEventListener("resize", onLayout);
    window.addEventListener("scroll", onLayout, true);

    return () => {
      window.removeEventListener("resize", onLayout);
      window.removeEventListener("scroll", onLayout, true);
    };
  }, [active, measureStep]);

  useEffect(() => {
    if (!active) return;
    setStepIndex((value) => Math.min(value, Math.max(totalSteps - 1, 0)));
  }, [active, totalSteps]);

  useEffect(() => {
    if (!active) return;

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      event.stopImmediatePropagation();
      finishTour(true);
    };

    window.addEventListener("keydown", onKeyDown, { capture: true });
    return () => window.removeEventListener("keydown", onKeyDown, { capture: true });
  }, [active, finishTour]);

  const goNext = () => {
    if (isLast) {
      finishTour(true);
      return;
    }
    setStepIndex((value) => Math.min(value + 1, totalSteps - 1));
  };

  const goBack = () => {
    setStepIndex((value) => Math.max(value - 1, 0));
  };

  return (
    <>
      {!active ? (
        <button
          type="button"
          className="workstation-tour-help glass"
          data-testid="tour-help-trigger"
          aria-label="Show workstation tour"
          title="Show tour"
          onClick={startTour}
        >
          <HelpCircle size={18} strokeWidth={2} aria-hidden="true" />
        </button>
      ) : null}

      {active && currentStep ? (
        <div
          className="workstation-tour"
          data-testid="workstation-tour"
          role="dialog"
          aria-modal="true"
          aria-labelledby="workstation-tour-title"
        >
          <div className="workstation-tour__backdrop" aria-hidden="true" onClick={() => finishTour(true)} />

          {highlight ? (
            <div
              className="workstation-tour__spotlight"
              style={{
                top: highlight.top,
                left: highlight.left,
                width: highlight.width,
                height: highlight.height,
              }}
              aria-hidden="true"
            />
          ) : null}

          <div
            ref={popoverRef}
            className={`workstation-tour__popover glass${
              popover ? ` workstation-tour__popover--${popover.placement}` : ""
            }`}
            style={
              popover
                ? { top: popover.top, left: popover.left, visibility: "visible" as const }
                : { top: -9999, left: -9999, visibility: "hidden" as const }
            }
          >
            <p className="workstation-tour__progress" aria-live="polite">
              Step {stepIndex + 1} of {totalSteps}
            </p>
            <h2 id="workstation-tour-title" className="workstation-tour__title">
              {currentStep.title}
            </h2>
            <p className="workstation-tour__body">{currentStep.body}</p>
            <div className="workstation-tour__actions">
              <button
                type="button"
                className="workstation-tour__btn workstation-tour__btn--ghost"
                onClick={() => finishTour(true)}
              >
                Skip
              </button>
              <div className="workstation-tour__actions-main">
                {!isFirst ? (
                  <button
                    type="button"
                    className="workstation-tour__btn workstation-tour__btn--secondary"
                    onClick={goBack}
                  >
                    Back
                  </button>
                ) : null}
                <button
                  type="button"
                  className="workstation-tour__btn workstation-tour__btn--primary"
                  onClick={goNext}
                >
                  {isLast ? "Done" : "Next"}
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}

export function InspectorTourSlot() {
  return (
    <div
      data-tour="inspector-slot"
      className="workstation-tour-inspector-slot"
      aria-hidden="true"
    />
  );
}
