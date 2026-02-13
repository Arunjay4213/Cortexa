/**
 * CortexOS Engine 1: Memory Attribution
 * Type definitions for attribution system
 */

export interface Memory {
  id: string
  content: string
  embedding: number[]
  tokens: number
  createdAt: Date
  lastAccessed: Date
  metadata: {
    source?: string
    agent?: string
    criticality?: number
  }
}

export interface Query {
  id: string
  text: string
  embedding: number[]
  timestamp: Date
}

export interface AgentResponse {
  id: string
  queryId: string
  text: string
  embedding: number[]
  tokens: number
  model: string
  timestamp: Date
}

export interface AttributionScore {
  memoryId: string
  shapleyValue: number
  confidence: number
  method: 'exact' | 'contextcite' | 'amortized'
  computeTimeMs: number
}

export interface AttributionResult {
  queryId: string
  responseId: string
  scores: AttributionScore[]
  totalComputeTimeMs: number
  lds?: number // Linear Datamodeling Score
  metadata: {
    retrievedMemoryCount: number
    avgShapleyValue: number
    maxShapleyValue: number
    method: 'exact' | 'contextcite' | 'amortized'
  }
}

export interface AblationMask {
  mask: boolean[]
  logProb: number
}

export interface ContextCiteConfig {
  numSamples: number // typically 64-128
  lassoLambda: number // regularization parameter
  minConfidence: number
}

export interface AmortizedModelConfig {
  embeddingDim: number
  hiddenDim: number
  modelFamily: string // 'gpt-4', 'claude-3', etc.
}

export interface ShapleyConfig {
  maxSubsets?: number // for exact computation
  approximationMethod?: 'tmc' | 'kernel' | 'contextcite'
}

// Metrics for Bloomberg Terminal view
export interface MemoryROI {
  memoryId: string
  tokenCost: number // monthly cost in dollars
  attributionScore: number // average Shapley value
  retrievalFrequency: number
  roi: number // (attribution / cost) * 100
  trend: 'up' | 'down' | 'stable'
  trendPercent: number
}

export interface TokenEconomics {
  totalTokenCost: number // per day
  wasteRate: number // percentage
  wasteCostPerDay: number
  redundancyTax: number
  consolidationSavings: number
}

export interface AccuracyImpact {
  accuracyDelta: number // percentage improvement with memory
  giniCoefficient: number // attribution concentration
  snr: number // signal-to-noise ratio in dB
  hallucinationsPerDay: number
}
