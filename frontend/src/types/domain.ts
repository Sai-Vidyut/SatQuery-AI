/** Domain contracts mirrored from backend Pydantic schemas. No business logic here. */

export type SensorType = "sentinel-2" | "sentinel-1";
export type DataMode = "development" | "earth_engine";
export type AnalysisStatus = "pending" | "running" | "completed" | "failed";
export type TraceStatus = "pending" | "running" | "completed" | "failed";

export interface GeoJSONGeometry {
  type: "Polygon" | "MultiPolygon" | "Point" | "LineString";
  coordinates: number[][][] | number[][] | number[];
}

export interface AOI {
  geometry: GeoJSONGeometry;
  name?: string | null;
  area_km2?: number | null;
}

export interface ImageryPreferences {
  cloud_cover_max?: number;
  prefer_least_cloud?: boolean;
}

export interface ImageryRequest {
  aoi: AOI;
  start_date: string;
  end_date: string;
  sensor?: SensorType;
  preferences?: ImageryPreferences;
}

export interface ImageryScene {
  scene_id: string;
  acquisition_date: string;
  cloud_cover_percent?: number | null;
  preview_url?: string | null;
}

export interface SpatialMetadata {
  crs?: string;
  bbox: number[];
  resolution_m?: number | null;
}

export interface ImageryResult {
  source: string;
  mode: DataMode;
  sensor: SensorType;
  scenes: ImageryScene[];
  spatial: SpatialMetadata;
  message?: string | null;
}

export interface QueryRequest {
  query: string;
  aoi?: AOI;
  earlier_date?: string;
  later_date?: string;
  sensor?: SensorType;
  preferences?: ImageryPreferences;
  image_id?: string;
  earlier_image_id?: string;
  later_image_id?: string;
  optical_image_id?: string;
  sar_image_id?: string;
  demo_mode?: boolean;
}

export type ImageModality = "optical" | "multispectral" | "sar";
export type ImageFormat = "geotiff" | "tiff" | "png" | "jpeg";

export interface ImageInput {
  id: string;
  modality: ImageModality;
  format: ImageFormat;
  filename: string;
  width: number;
  height: number;
  georeferenced: boolean;
  acquisition_datetime?: string | null;
  benchmark_dataset?: boolean;
  co_registered_benchmark?: boolean;
  benchmark_pair_id?: string | null;
  bounds?: number[] | null;
  crs?: string | null;
}

export interface UploadImageResponse {
  image: ImageInput;
}

export interface SingleImageVQAResult {
  task: "single_image_vqa";
  answer: string;
  model_name: string;
  model_version: string;
  provider: "development" | "geochat_service";
  provenance: string;
  confidence?: number | null;
  confidence_available: boolean;
  input_image_id: string;
  requested_modality: string;
  inference_metadata?: Record<string, unknown>;
}

export interface SingleImageCaptionResult {
  task: "single_image_caption";
  description: string;
  model_name: string;
  model_version: string;
  provider: "development" | "geochat_service";
  provenance: string;
  confidence?: number | null;
  confidence_available: boolean;
  input_image_id: string;
  requested_modality: string;
  inference_metadata?: Record<string, unknown>;
}

export interface CrossModalOpticalSARResult {
  task: "cross_modal_optical_sar";
  answer: string;
  question: string;
  optical_analysis: {
    modality: string;
    summary: string;
    analyzer: string;
    provider: string;
    confidence_available: boolean;
  };
  sar_analysis: {
    modality: string;
    summary: string;
    analyzer: string;
    provider: string;
    confidence_available: boolean;
  };
  fused_analysis: {
    summary: string;
    fusion_policy: string;
    fused_region_count: number;
    complementary_notes: string[];
  };
  co_registration_status: string;
  co_registration_provenance: string;
  optical_image_id: string;
  sar_image_id: string;
  provider: string;
  provenance: string;
  confidence?: number | null;
  confidence_available: boolean;
}

export interface BiTemporalSceneMetrics {
  changed_pixel_count?: number | null;
  total_pixel_count?: number | null;
  changed_percentage?: number | null;
  area_m2?: number | null;
  area_ha?: number | null;
  area_km2?: number | null;
  region_count?: number | null;
}

export interface BiTemporalDetectorSummary {
  detector: string;
  algorithm?: string | null;
  detector_version?: string | null;
  primary_index?: string | null;
  change_direction_hint?: string | null;
  histogram_confidence?: number | null;
  confidence_kind?: "histogram_separability" | null;
}

export interface BiTemporalImageProvenance {
  earlier_source_ref?: string | null;
  later_source_ref?: string | null;
  earlier_filename?: string | null;
  later_filename?: string | null;
  earlier_modality?: string | null;
  later_modality?: string | null;
  earlier_band_names?: string[] | null;
  later_band_names?: string[] | null;
  crs?: string | null;
  coregistration_performed?: boolean | null;
  positional_band_fallback_used?: boolean | null;
}

export interface BiTemporalChangeResult {
  task: "bi_temporal_change_vqa";
  change_summary: string;
  question: string;
  changed_region_count: number;
  change_map_available: boolean;
  detector: string;
  provider: "development" | "uploaded_cva";
  provenance: string;
  confidence?: number | null;
  confidence_available: boolean;
  confidence_kind?: "histogram_separability" | null;
  earlier_image_id: string;
  later_image_id: string;
  earlier_acquisition: string;
  later_acquisition: string;
  earlier_date: string;
  later_date: string;
  scene_metrics?: BiTemporalSceneMetrics | null;
  detector_summary?: BiTemporalDetectorSummary | null;
  image_provenance?: BiTemporalImageProvenance | null;
  inference_metadata?: Record<string, unknown>;
}

export interface BiTemporalRegionInterpretationResult {
  task: "bi_temporal_region_interpretation";
  answer: string;
  region_id: string;
  session_id: string;
  question: string;
  detector: string;
  region_confidence: number;
  confidence_kind?: "histogram_separability" | null;
  change_direction_hint?: string | null;
  model_name: string;
  model_version: string;
  provider: "development" | "geochat_service";
  provenance: string;
  confidence_available: boolean;
  inference_metadata?: Record<string, unknown>;
  earlier_image_id: string;
  later_image_id: string;
  preview_bbox_wgs84: string;
  evidence_inputs: "before_after_composite_crop";
}

export interface InterpretRegionData {
  interpretation: BiTemporalRegionInterpretationResult;
  trace_step: TraceStep;
}

export interface ConversationTurnRecord {
  turn_id: string;
  turn_index: number;
  user_message: string;
  assistant_answer: string;
  created_at: string;
  route?: "geo" | "general" | null;
  provider?: "development" | "geochat_service" | "groq" | null;
  scope?: "selected_region" | "general_assistant" | null;
}

export interface RegionConversationRecord {
  conversation_id: string;
  session_id: string;
  region_id: string;
  turns: ConversationTurnRecord[];
}

export interface BiTemporalRegionChatResult {
  task: "bi_temporal_region_chat";
  answer: string;
  session_id: string;
  region_id: string;
  conversation_id: string;
  turn_id: string;
  turn_index: number;
  message: string;
  detector: string;
  region_confidence: number;
  confidence_kind?: "histogram_separability" | null;
  change_direction_hint?: string | null;
  model_name: string;
  model_version: string;
  provider: "development" | "geochat_service" | "groq";
  provenance: string;
  confidence_available: boolean;
  inference_metadata?: Record<string, unknown>;
  route: "geo" | "general";
  classification: "geo" | "general" | "ambiguous";
  scope: "selected_region" | "general_assistant";
  preview_bbox_wgs84: string;
  evidence_inputs: "before_after_composite_crop" | "general_assistant_no_imagery";
  scope_limited: boolean;
  conversation: RegionConversationRecord;
}

export interface RegionChatData {
  chat: BiTemporalRegionChatResult;
  trace_step: TraceStep;
}

export interface Metric {
  name: string;
  value: number | string;
  unit?: string | null;
  source: string;
}

export interface EvidenceRegion {
  id: string;
  geometry: GeoJSONGeometry;
  type: string;
  confidence: number;
  metrics: Metric[];
  source: string;
  metadata: Record<string, unknown>;
}

export interface PlanQueryMetadata {
  planner?: string;
  intent?: string;
  required_tools?: string[];
  requested_modalities?: string[];
  planner_version?: string;
  fallback_used?: boolean;
  status?: string;
  duration_ms?: number;
}

export interface FetchImageryMetadata {
  imagery_strategy?: string;
  composite_method?: string;
  demonstration_data?: boolean;
  fallback_events?: Array<Record<string, unknown>>;
  fallback_policy?: string;
  t1?: {
    requested_date?: string;
    window_start?: string;
    window_end?: string;
    scene_count?: number;
    scene_dates?: string[];
    fallback?: Record<string, unknown>;
  };
  t2?: {
    requested_date?: string;
    window_start?: string;
    window_end?: string;
    scene_count?: number;
    scene_dates?: string[];
    fallback?: Record<string, unknown>;
  };
}

export interface TraceStep {
  id: string;
  tool_name: string;
  status: TraceStatus;
  started_at?: string | null;
  completed_at?: string | null;
  duration_ms?: number | null;
  summary?: string | null;
  error?: string | null;
  metadata?: PlanQueryMetadata | Record<string, unknown> | null;
}

export interface AnalysisResult {
  status: AnalysisStatus;
  session_id: string;
  answer: string;
  confidence: number;
  confidence_available?: boolean;
  metrics: Metric[];
  evidence: EvidenceRegion[];
  trace: TraceStep[];
  mode: DataMode;
  demonstration_data?: boolean;
  vqa?: SingleImageVQAResult | null;
  caption?: SingleImageCaptionResult | null;
  bi_temporal_change?: BiTemporalChangeResult | null;
  cross_modal?: CrossModalOpticalSARResult | null;
}

export interface ApiResponse<T> {
  success: boolean;
  data: T;
}

export interface SubmitQueryData {
  session_id: string;
  result: AnalysisResult;
}

export interface ErrorResponse {
  success: false;
  error: { code: string; message: string; user_message?: string | null; field?: string | null };
}

export class ApiError extends Error {
  code: string;
  userMessage: string;

  constructor(code: string, message: string, userMessage?: string | null) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.userMessage = userMessage ?? message;
  }
}
