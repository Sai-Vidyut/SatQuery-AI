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
  aoi: AOI;
  earlier_date: string;
  later_date: string;
  sensor?: SensorType;
  preferences?: ImageryPreferences;
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
  metrics: Metric[];
  evidence: EvidenceRegion[];
  trace: TraceStep[];
  mode: DataMode;
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
