"use client";

import { useEffect, useRef, useState } from "react";
import type { AnalysisResult, EvidenceRegion } from "@/types/domain";
import { api } from "@/lib/api";
import { normalizeAnalysisError } from "@/lib/errors";
import {
  beforeAfterImageIds,
  formatPreviewBbox,
  paddedBboxFromGeometry,
  shouldShowBeforeAfterEvidence,
} from "@/lib/regionPreview";

type PreviewState = {
  loading: boolean;
  error: string | null;
  beforeUrl: string | null;
  afterUrl: string | null;
};

const EMPTY_STATE: PreviewState = {
  loading: false,
  error: null,
  beforeUrl: null,
  afterUrl: null,
};

type Props = {
  result: AnalysisResult;
  selectedRegion: EvidenceRegion;
};

function revokeIfPresent(url: string | null) {
  if (url) URL.revokeObjectURL(url);
}

export function BeforeAfterEvidenceViewer({ result, selectedRegion }: Props) {
  const [state, setState] = useState<PreviewState>(EMPTY_STATE);
  const urlsRef = useRef<{ before: string | null; after: string | null }>({
    before: null,
    after: null,
  });

  useEffect(() => {
    if (!shouldShowBeforeAfterEvidence(result, selectedRegion)) {
      revokeIfPresent(urlsRef.current.before);
      revokeIfPresent(urlsRef.current.after);
      urlsRef.current = { before: null, after: null };
      setState(EMPTY_STATE);
      return;
    }

    const ids = beforeAfterImageIds(result);
    const bbox = paddedBboxFromGeometry(selectedRegion.geometry);
    if (!ids || !bbox) {
      setState({
        loading: false,
        error: "Could not derive a preview area for this region.",
        beforeUrl: null,
        afterUrl: null,
      });
      return;
    }

    let cancelled = false;
    revokeIfPresent(urlsRef.current.before);
    revokeIfPresent(urlsRef.current.after);
    urlsRef.current = { before: null, after: null };
    setState({ loading: true, error: null, beforeUrl: null, afterUrl: null });

    const bboxParam = formatPreviewBbox(bbox);
    void (async () => {
      try {
        const [beforeUrl, afterUrl] = await Promise.all([
          api.fetchImageryPreview(ids.earlierImageId, bboxParam),
          api.fetchImageryPreview(ids.laterImageId, bboxParam),
        ]);
        if (cancelled) {
          revokeIfPresent(beforeUrl);
          revokeIfPresent(afterUrl);
          return;
        }
        urlsRef.current = { before: beforeUrl, after: afterUrl };
        setState({ loading: false, error: null, beforeUrl, afterUrl });
      } catch (err) {
        if (cancelled) return;
        setState({
          loading: false,
          error: normalizeAnalysisError(err),
          beforeUrl: null,
          afterUrl: null,
        });
      }
    })();

    return () => {
      cancelled = true;
      revokeIfPresent(urlsRef.current.before);
      revokeIfPresent(urlsRef.current.after);
      urlsRef.current = { before: null, after: null };
    };
  }, [
    result.session_id,
    result.bi_temporal_change?.earlier_image_id,
    result.bi_temporal_change?.later_image_id,
    selectedRegion.id,
    selectedRegion.geometry,
  ]);

  if (!shouldShowBeforeAfterEvidence(result, selectedRegion)) {
    return null;
  }

  return (
    <div className="inspector-section" data-testid="before-after-evidence">
      <p className="inspector-section__label">Before / After Evidence</p>
      <p className="inspector-note mb-2">
        Cropped from uploaded imagery for region {selectedRegion.id}.
      </p>

      {state.loading ? (
        <p className="inspector-note" data-testid="before-after-loading">
          Loading before/after previews…
        </p>
      ) : null}

      {state.error ? (
        <p className="inspector-note inspector-note--error" data-testid="before-after-error">
          {state.error}
        </p>
      ) : null}

      {!state.loading && !state.error && state.beforeUrl && state.afterUrl ? (
        <div className="before-after-grid">
          <figure className="before-after-card">
            <figcaption className="before-after-card__label">Before</figcaption>
            <img
              src={state.beforeUrl}
              alt={`Before satellite crop for region ${selectedRegion.id}`}
              data-testid="before-after-preview-before"
              className="before-after-card__image"
            />
          </figure>
          <figure className="before-after-card">
            <figcaption className="before-after-card__label">After</figcaption>
            <img
              src={state.afterUrl}
              alt={`After satellite crop for region ${selectedRegion.id}`}
              data-testid="before-after-preview-after"
              className="before-after-card__image"
            />
          </figure>
        </div>
      ) : null}
    </div>
  );
}
