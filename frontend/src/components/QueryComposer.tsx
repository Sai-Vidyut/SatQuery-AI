"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowRight, ChevronRight, UploadCloud } from "lucide-react";
import { SolarLoader } from "@/components/ui/solar-loader";
import type { ImageInput } from "@/types/domain";

export type ComposerInputMode = "catalog" | "upload" | "temporal_pair" | "cross_modal";

type Props = {
  inputMode: ComposerInputMode;
  aoiLabel: string;
  uploadedImage: ImageInput | null;
  uploadStatus: string | null;
  uploadedEarlierImage: ImageInput | null;
  uploadedLaterImage: ImageInput | null;
  uploadedOpticalImage: ImageInput | null;
  uploadedSarImage: ImageInput | null;
  earlierUploadStatus: string | null;
  laterUploadStatus: string | null;
  opticalUploadStatus: string | null;
  sarUploadStatus: string | null;
  pairValidationStatus: string | null;
  earlierDate: string;
  laterDate: string;
  query: string;
  running: boolean;
  validationError: string | null;
  statusLine: string | null;
  onInputModeChange: (mode: ComposerInputMode) => void;
  onFileSelect: (file: File) => void;
  onEarlierFileSelect: (file: File) => void;
  onLaterFileSelect: (file: File) => void;
  onOpticalFileSelect: (file: File) => void;
  onSarFileSelect: (file: File) => void;
  onEarlierChange: (v: string) => void;
  onLaterChange: (v: string) => void;
  onQueryChange: (v: string) => void;
  onRun: () => void;
  onBboxSubmit: (bbox: string) => void;
  demoMode: boolean;
  onDemoModeChange: (enabled: boolean) => void;
  inspectorOpen?: boolean;
};

export function QueryComposer({
  inputMode,
  aoiLabel,
  uploadedImage,
  uploadStatus,
  uploadedEarlierImage,
  uploadedLaterImage,
  uploadedOpticalImage,
  uploadedSarImage,
  earlierUploadStatus,
  laterUploadStatus,
  opticalUploadStatus,
  sarUploadStatus,
  pairValidationStatus,
  earlierDate,
  laterDate,
  query,
  running,
  validationError,
  statusLine,
  onInputModeChange,
  onFileSelect,
  onEarlierFileSelect,
  onLaterFileSelect,
  onOpticalFileSelect,
  onSarFileSelect,
  onEarlierChange,
  onLaterChange,
  onQueryChange,
  onRun,
  onBboxSubmit,
  demoMode,
  onDemoModeChange,
  inspectorOpen = false,
}: Props) {
  const [showBbox, setShowBbox] = useState(false);
  const [bboxText, setBboxText] = useState("");
  const [queryFocused, setQueryFocused] = useState(false);
  const [dateFocusedId, setDateFocusedId] = useState<string | null>(null);
  const [composerExpanded, setComposerExpanded] = useState(true);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const earlierFileRef = useRef<HTMLInputElement>(null);
  const laterFileRef = useRef<HTMLInputElement>(null);
  const opticalFileRef = useRef<HTMLInputElement>(null);
  const sarFileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (inspectorOpen) {
      setComposerExpanded(false);
    } else {
      setComposerExpanded(true);
    }
  }, [inspectorOpen]);

  const isUpload = inputMode === "upload";
  const isTemporalPair = inputMode === "temporal_pair";
  const isCrossModal = inputMode === "cross_modal";

  const uploadPlaceholder = "Upload GeoTIFF or TIFF";

  const queryPlaceholder = isCrossModal
    ? "Use the optical and SAR images together to identify built-up and water-covered regions."
    : isTemporalPair
      ? "What changed between these two dates, and where did the change occur?"
      : isUpload
        ? "Describe the land-cover and major objects visible…"
        : "Ask a question about this area…";

  const dateInputClass = (id: string) =>
    `input-field input-field--date${dateFocusedId !== id ? " input-field--settled" : ""}`;

  const composerSlidOff = inspectorOpen && !composerExpanded;
  const composerConstrained = inspectorOpen && composerExpanded;

  return (
    <>
      {composerSlidOff ? (
        <button
          type="button"
          className="composer-pull-tab"
          data-testid="composer-pull-tab"
          aria-label="Show query composer"
          onClick={() => {
            setComposerExpanded(true);
            onQueryChange("");
          }}
        >
          <ChevronRight size={20} strokeWidth={2.5} aria-hidden="true" />
        </button>
      ) : null}

      <div
        className={`composer-wrap${composerSlidOff ? " composer-wrap--slid-off" : ""}${
          composerConstrained ? " composer-wrap--inspector-open" : ""
        }`}
      >
      {statusLine ? <p className="composer-status">{statusLine}</p> : null}

      <div data-testid="composer" className="glass-light composer-shell">
        <div className="composer-stack">
        <form
          className="composer-query-bar"
          onSubmit={(e) => {
            e.preventDefault();
            onRun();
          }}
        >
          <input
            id="composer-query"
            data-testid="composer-query"
            data-tour="composer-query"
            type="text"
            className={`composer-query-input${!queryFocused ? " composer-query-input--settled" : ""}`}
            placeholder={queryPlaceholder}
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            onFocus={() => setQueryFocused(true)}
            onBlur={() => setQueryFocused(false)}
            spellCheck={false}
            autoComplete="off"
            required
          />
          <button
            type="submit"
            data-testid="composer-run"
            data-tour="composer-run"
            className="composer-query-send"
            disabled={running}
            aria-busy={running}
            aria-label={running ? "Running analysis" : "Run analysis"}
          >
            {running ? (
              <span className="solar-loader-host solar-loader-host--button" aria-hidden="true">
                <SolarLoader size={20} speed={2} />
              </span>
            ) : (
              <ArrowRight size={18} strokeWidth={2} aria-hidden />
            )}
          </button>
        </form>

        <div className="composer-mode-row" data-tour="composer-mode-row">
          <button
            type="button"
            className={`btn-secondary ${inputMode === "catalog" ? "btn-secondary--active" : ""}`}
            data-testid="composer-mode-catalog"
            onClick={() => onInputModeChange("catalog")}
          >
            AOI + dates
          </button>
          <button
            type="button"
            className={`btn-secondary ${isUpload ? "btn-secondary--active" : ""}`}
            data-testid="composer-mode-upload"
            onClick={() => onInputModeChange("upload")}
          >
            Upload image
          </button>
          <button
            type="button"
            className={`btn-secondary ${isTemporalPair ? "btn-secondary--active" : ""}`}
            data-testid="composer-mode-temporal-pair"
            onClick={() => onInputModeChange("temporal_pair")}
          >
            Temporal pair
          </button>
          <button
            type="button"
            className={`btn-secondary ${isCrossModal ? "btn-secondary--active" : ""}`}
            data-testid="composer-mode-cross-modal"
            onClick={() => onInputModeChange("cross_modal")}
          >
            Cross-modal
          </button>
        </div>

        <form
          className="composer-row"
          onSubmit={(e) => {
            e.preventDefault();
            onRun();
          }}
        >
          {isCrossModal ? (
            <>
              <div className="composer-segment">
                <span className="composer-label">Optical</span>
                <input
                  ref={opticalFileRef}
                  type="file"
                  data-testid="composer-upload-optical"
                  className="sr-only"
                  accept=".tif,.tiff,.geotiff,.png,.jpg,.jpeg"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) onOpticalFileSelect(file);
                  }}
                />
                <button
                  type="button"
                  className="composer-upload-btn"
                  data-testid="composer-upload-optical-trigger"
                  data-tour="composer-upload-optical"
                  onClick={() => opticalFileRef.current?.click()}
                >
                  <UploadCloud size={16} strokeWidth={1.75} aria-hidden />
                  <span>
                    {uploadedOpticalImage
                      ? `${uploadedOpticalImage.filename} · ${uploadedOpticalImage.modality}`
                      : uploadPlaceholder}
                  </span>
                </button>
                {opticalUploadStatus ? (
                  <p className="composer-upload-status" data-testid="composer-optical-upload-status">
                    {opticalUploadStatus}
                  </p>
                ) : null}
              </div>
              <div className="composer-segment">
                <span className="composer-label">SAR</span>
                <input
                  ref={sarFileRef}
                  type="file"
                  data-testid="composer-upload-sar"
                  className="sr-only"
                  accept=".tif,.tiff,.geotiff,.png,.jpg,.jpeg"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) onSarFileSelect(file);
                  }}
                />
                <button
                  type="button"
                  className="composer-upload-btn"
                  data-testid="composer-upload-sar-trigger"
                  data-tour="composer-upload-sar"
                  onClick={() => sarFileRef.current?.click()}
                >
                  <UploadCloud size={16} strokeWidth={1.75} aria-hidden />
                  <span>
                    {uploadedSarImage
                      ? `${uploadedSarImage.filename} · ${uploadedSarImage.modality}`
                      : uploadPlaceholder}
                  </span>
                </button>
                {sarUploadStatus ? (
                  <p className="composer-upload-status" data-testid="composer-sar-upload-status">
                    {sarUploadStatus}
                  </p>
                ) : null}
              </div>
              {pairValidationStatus ? (
                <p className="composer-upload-status" data-testid="composer-cross-modal-validation-status">
                  {pairValidationStatus}
                </p>
              ) : null}
            </>
          ) : isTemporalPair ? (
            <>
              <div className="composer-segment">
                <span className="composer-label">Before</span>
                <input
                  ref={earlierFileRef}
                  type="file"
                  data-testid="composer-upload-earlier"
                  className="sr-only"
                  accept=".tif,.tiff,.geotiff,.png,.jpg,.jpeg"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) onEarlierFileSelect(file);
                  }}
                />
                <button
                  type="button"
                  className="composer-upload-btn"
                  data-testid="composer-upload-earlier-trigger"
                  data-tour="composer-upload-earlier"
                  onClick={() => earlierFileRef.current?.click()}
                >
                  <UploadCloud size={16} strokeWidth={1.75} aria-hidden />
                  <span>
                    {uploadedEarlierImage
                      ? `${uploadedEarlierImage.filename} · ${uploadedEarlierImage.acquisition_datetime?.slice(0, 10) ?? "no date"}`
                      : uploadPlaceholder}
                  </span>
                </button>
                {earlierUploadStatus ? (
                  <p className="composer-upload-status" data-testid="composer-earlier-upload-status">
                    {earlierUploadStatus}
                  </p>
                ) : null}
              </div>
              <div className="composer-segment">
                <span className="composer-label">After</span>
                <input
                  ref={laterFileRef}
                  type="file"
                  data-testid="composer-upload-later"
                  className="sr-only"
                  accept=".tif,.tiff,.geotiff,.png,.jpg,.jpeg"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) onLaterFileSelect(file);
                  }}
                />
                <button
                  type="button"
                  className="composer-upload-btn"
                  data-testid="composer-upload-later-trigger"
                  data-tour="composer-upload-later"
                  onClick={() => laterFileRef.current?.click()}
                >
                  <UploadCloud size={16} strokeWidth={1.75} aria-hidden />
                  <span>
                    {uploadedLaterImage
                      ? `${uploadedLaterImage.filename} · ${uploadedLaterImage.acquisition_datetime?.slice(0, 10) ?? "no date"}`
                      : uploadPlaceholder}
                  </span>
                </button>
                {laterUploadStatus ? (
                  <p className="composer-upload-status" data-testid="composer-later-upload-status">
                    {laterUploadStatus}
                  </p>
                ) : null}
              </div>
              {pairValidationStatus ? (
                <p className="composer-upload-status" data-testid="composer-pair-validation-status">
                  {pairValidationStatus}
                </p>
              ) : null}
              <div className="composer-segment">
                <label htmlFor="composer-pair-date-from" className="composer-label">
                  Before date
                </label>
                <input
                  id="composer-pair-date-from"
                  data-testid="composer-pair-date-from"
                  type="date"
                  className={dateInputClass("composer-pair-date-from")}
                  value={earlierDate}
                  onChange={(e) => onEarlierChange(e.target.value)}
                  onFocus={() => setDateFocusedId("composer-pair-date-from")}
                  onBlur={() => setDateFocusedId(null)}
                  required
                />
              </div>
              <div className="composer-segment">
                <label htmlFor="composer-pair-date-to" className="composer-label">
                  After date
                </label>
                <input
                  id="composer-pair-date-to"
                  data-testid="composer-pair-date-to"
                  type="date"
                  className={dateInputClass("composer-pair-date-to")}
                  value={laterDate}
                  onChange={(e) => onLaterChange(e.target.value)}
                  onFocus={() => setDateFocusedId("composer-pair-date-to")}
                  onBlur={() => setDateFocusedId(null)}
                  required
                />
              </div>
            </>
          ) : isUpload ? (
            <div className="composer-segment">
              <span className="composer-label">Image</span>
              <input
                ref={fileInputRef}
                type="file"
                data-testid="composer-upload"
                className="sr-only"
                accept=".tif,.tiff,.geotiff,.png,.jpg,.jpeg"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) onFileSelect(file);
                }}
              />
              <button
                type="button"
                className="composer-upload-btn"
                data-testid="composer-upload-trigger"
                data-tour="composer-upload-single"
                onClick={() => fileInputRef.current?.click()}
              >
                <UploadCloud size={16} strokeWidth={1.75} aria-hidden />
                <span>{uploadedImage ? uploadedImage.filename : uploadPlaceholder}</span>
              </button>
              {uploadStatus ? (
                <p className="composer-upload-status" data-testid="composer-upload-status">
                  {uploadStatus}
                </p>
              ) : null}
            </div>
          ) : (
            <div className="composer-segment">
              <span className="composer-label">AOI</span>
              <button
                type="button"
                id="aoi-status"
                data-testid="aoi-status"
                className="composer-aoi-btn tabular-nums"
                onClick={() => setShowBbox((v) => !v)}
                aria-expanded={showBbox}
              >
                {aoiLabel}
              </button>
            </div>
          )}

          {inputMode === "catalog" ? (
            <>
              <div className="composer-segment">
                <label htmlFor="composer-date-from" className="composer-label">
                  Earlier
                </label>
                <input
                  id="composer-date-from"
                  data-testid="composer-date-from"
                  type="date"
                  className={dateInputClass("composer-date-from")}
                  value={earlierDate}
                  onChange={(e) => onEarlierChange(e.target.value)}
                  onFocus={() => setDateFocusedId("composer-date-from")}
                  onBlur={() => setDateFocusedId(null)}
                  required
                />
              </div>

              <div className="composer-segment">
                <label htmlFor="composer-date-to" className="composer-label">
                  Later
                </label>
                <input
                  id="composer-date-to"
                  data-testid="composer-date-to"
                  type="date"
                  className={dateInputClass("composer-date-to")}
                  value={laterDate}
                  onChange={(e) => onLaterChange(e.target.value)}
                  onFocus={() => setDateFocusedId("composer-date-to")}
                  onBlur={() => setDateFocusedId(null)}
                  required
                />
              </div>
              <div className="composer-segment composer-segment--demo">
                <label className="composer-label flex items-center gap-2">
                  <input
                    type="checkbox"
                    data-testid="composer-demo-mode"
                    checked={demoMode}
                    onChange={(e) => onDemoModeChange(e.target.checked)}
                  />
                  Demo mode
                </label>
                <p className="composer-demo-note">
                  When checked, uses deterministic demonstration fixtures instead of live Earth Engine.
                </p>
              </div>
            </>
          ) : null}
        </form>

        {inputMode === "catalog" && showBbox ? (
          <div className="composer-bbox-row">
            <div className="flex min-w-[260px] flex-1 flex-col gap-1">
              <label htmlFor="aoi-bbox" className="composer-label">
                Bounding box (minLon, minLat, maxLon, maxLat)
              </label>
              <input
                id="aoi-bbox"
                data-testid="aoi-bbox"
                type="text"
                className="input-field input-field--mono w-full"
                placeholder="77.56, 12.94, 77.60, 12.98"
                value={bboxText}
                onChange={(e) => setBboxText(e.target.value)}
                spellCheck={false}
                autoComplete="off"
              />
            </div>
            <button type="button" className="btn-secondary" onClick={() => onBboxSubmit(bboxText)}>
              Set AOI
            </button>
          </div>
        ) : null}

        {validationError ? (
          <p className="composer-error" role="alert" data-testid="composer-validation-error">
            {validationError}
          </p>
        ) : null}
        </div>
      </div>
    </div>
    </>
  );
}
