import { get, post } from "./client";
import type {
  AiTool,
  ApprovalResponse,
  AuthIdentity,
  ChatResponse,
  DashboardOverview,
  ForecastQuery,
  ForecastRow,
  InventoryHealthRow,
  InventoryOverview,
  InventoryPositionRow,
  OpenOrderRow,
  OptimizationReport,
  OptimizationRunRequest,
  Paginated,
  ProcurementOverview,
  ProcurementRiskRow,
  ReplayDecisionMeta,
  ReplayReport,
  ReplayRunRequest,
  RiskQuery,
  RiskRecordRow,
  SimulationEventMeta,
  SimulationReport,
  SimulationRunRequest,
  SupplierPerformanceRow,
  SupplierRow,
  InboundCoverageRow,
} from "./types";

/**
 * Typed endpoint functions for the implemented Phase 12A + Phase 11 API.
 *
 * Only endpoints that exist in `backend/app` (verified against OpenAPI) are
 * included. No calls are made to documented-but-nonexistent paths.
 */

export const endpoints = {
  /* health (public) */
  health: () => get<{ status: string; service: string; version: string }>("/health"),

  /* auth */
  me: () => get<AuthIdentity>("/auth/me"),

  /* dashboard */
  dashboardOverview: (horizonDays?: number, analysisDate?: string) =>
    get<DashboardOverview>("/dashboard/overview", {
      horizon_days: horizonDays,
      analysis_date: analysisDate,
    }),

  /* forecast */
  forecasts: (query: ForecastQuery) => get<Paginated<ForecastRow>>("/forecast", query as never),

  /* inventory */
  inventoryOverview: (analysisDate?: string) =>
    get<InventoryOverview>("/inventory/overview", { analysis_date: analysisDate }),
  inventoryPositions: (query: { product_id?: string; warehouse_id?: string; analysis_date?: string; page?: number; page_size?: number }) =>
    get<Paginated<InventoryPositionRow>>("/inventory/positions", query),
  inventoryHealth: (query: { product_id?: string; warehouse_id?: string; analysis_date?: string; page?: number; page_size?: number }) =>
    get<Paginated<InventoryHealthRow>>("/inventory/health", query),

  /* suppliers */
  suppliers: (page = 1, pageSize = 50) =>
    get<Paginated<SupplierRow>>("/suppliers", { page, page_size: pageSize }),
  supplierPerformance: (query: { supplier_id?: string; analysis_date?: string; page?: number; page_size?: number }) =>
    get<Paginated<SupplierPerformanceRow>>("/suppliers/performance", query),

  /* procurement */
  procurementOverview: (analysisDate?: string) =>
    get<ProcurementOverview>("/procurement/overview", { analysis_date: analysisDate }),
  openOrders: (query: { supplier_id?: string; analysis_date?: string; page?: number; page_size?: number }) =>
    get<Paginated<OpenOrderRow>>("/procurement/open-orders", query),
  inboundCoverage: (query: { product_id?: string; warehouse_id?: string; horizon_days?: number; analysis_date?: string; page?: number; page_size?: number }) =>
    get<Paginated<InboundCoverageRow>>("/procurement/inbound", query),
  procurementRisk: (query: { supplier_id?: string; analysis_date?: string; page?: number; page_size?: number }) =>
    get<Paginated<ProcurementRiskRow>>("/procurement/risk", query),

  /* risk */
  riskRegister: (query: RiskQuery) => get<Paginated<RiskRecordRow>>("/risk", query as never),

  /* simulation */
  simulationEvents: () => get<SimulationEventMeta>("/simulation/events"),
  simulationRun: (body: SimulationRunRequest) => post<SimulationReport>("/simulation/run", body),

  /* replay */
  replayDecisions: () => get<ReplayDecisionMeta>("/replay/decisions"),
  replayRun: (body: ReplayRunRequest) => post<ReplayReport>("/replay/run", body),

  /* optimization */
  optimizationRun: (body: OptimizationRunRequest) => post<OptimizationReport>("/optimization/run", body),

  /* ai copilot (Phase 11; mock provider when no LLM key is configured) */
  aiChat: (message: string, conversationId?: string | null, sessionId?: string | null) =>
    post<ChatResponse>("/ai/chat", { message, conversation_id: conversationId ?? null, session_id: sessionId ?? null }),
  aiTools: () => get<{ tools: AiTool[]; count: number }>("/ai/tools"),
  aiApproval: (approvalId: string, decision: "approve" | "reject", comment?: string) =>
    post<ApprovalResponse>("/ai/approval", { approval_id: approvalId, decision, comment: comment ?? null }),
};
