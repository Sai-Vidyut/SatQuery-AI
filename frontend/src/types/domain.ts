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
  earlier_image_id: string;
  later_image_id: string;
  earlier_acquisition: string;
  later_acquisition: string;
  earlier_date: string;
  later_date: string;
  inference_metadata?: Record<string, unknown>;
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
  error: { code: string; message: string; field?: string | null };
}
