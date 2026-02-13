/**
 * CortexOS Metrics Calculator
 *
 * Implements all Bloomberg Terminal-style metrics:
 * - Token Economics ($)
 * - Accuracy Impact (%)
 * - Risk Exposure (!)
 * - Operational Actions (→)
 */

import { Memory, AttributionResult, MemoryROI, TokenEconomics, AccuracyImpact } from '../attribution/types'

export interface MetricsConfig {
  inputTokenCost: number // Cost per input token (e.g., $0.00001 for GPT-4)
  outputTokenCost: number
  retrievalCount: number // Default k (memories per query)
  queriesPerDay: number
}

export class MetricsCalculator {
  private config: MetricsConfig

  constructor(config: MetricsConfig) {
    this.config = config
  }

  /**
   * METRIC 1: Memory Token Cost (MTC)
   * Total token cost attributable to memory retrieval
   */
  calculateMemoryTokenCost(memories: Memory[]): number {
    const totalTokens = memories.reduce((sum, mem) => sum + mem.tokens, 0)
    return totalTokens * this.config.inputTokenCost * this.config.queriesPerDay
  }

  /**
   * METRIC 2: Token Waste Rate (TWR)
   * Percentage of memory tokens with zero causal influence
   */
  calculateTokenWasteRate(
    memories: Memory[],
    attributionResults: AttributionResult[]
  ): { wasteRate: number; wasteCostPerDay: number } {
    if (attributionResults.length === 0) {
      return { wasteRate: 0, wasteCostPerDay: 0 }
    }

    let totalTokens = 0
    let wastedTokens = 0

    for (const result of attributionResults) {
      for (const score of result.scores) {
        const memory = memories.find(m => m.id === score.memoryId)
        if (memory) {
          totalTokens += memory.tokens
          // Consider tokens wasted if Shapley value < 0.01
          if (Math.abs(score.shapleyValue) < 0.01) {
            wastedTokens += memory.tokens
          }
        }
      }
    }

    const wasteRate = totalTokens > 0 ? (wastedTokens / totalTokens) * 100 : 0
    const wasteCostPerDay = wastedTokens * this.config.inputTokenCost * this.config.queriesPerDay

    return { wasteRate, wasteCostPerDay }
  }

  /**
   * METRIC 3: Memory ROI
   * Attribution contribution per dollar spent on tokens
   */
  calculateMemoryROI(
    memories: Memory[],
    attributionResults: AttributionResult[],
    timeWindowDays: number = 30
  ): MemoryROI[] {
    // Aggregate attribution scores per memory
    const memoryStats = new Map<string, {
      totalAttribution: number
      retrievalCount: number
      tokens: number
    }>()

    for (const result of attributionResults) {
      for (const score of result.scores) {
        const stats = memoryStats.get(score.memoryId) || {
          totalAttribution: 0,
          retrievalCount: 0,
          tokens: 0
        }

        stats.totalAttribution += score.shapleyValue
        stats.retrievalCount += 1

        const memory = memories.find(m => m.id === score.memoryId)
        if (memory) {
          stats.tokens = memory.tokens
        }

        memoryStats.set(score.memoryId, stats)
      }
    }

    // Calculate ROI for each memory
    const roiList: MemoryROI[] = []

    for (const [memoryId, stats] of memoryStats.entries()) {
      const avgAttribution = stats.totalAttribution / stats.retrievalCount
      const tokenCostPerMonth = stats.tokens * this.config.inputTokenCost *
        stats.retrievalCount * (30 / timeWindowDays)

      // ROI = (avg attribution / cost) * 100
      // Multiply by 1000 to make percentages more readable
      const roi = tokenCostPerMonth > 0
        ? (avgAttribution / tokenCostPerMonth) * 1000
        : 0

      roiList.push({
        memoryId,
        tokenCost: tokenCostPerMonth,
        attributionScore: avgAttribution,
        retrievalFrequency: stats.retrievalCount,
        roi,
        trend: 'stable',
        trendPercent: 0
      })
    }

    return roiList.sort((a, b) => b.roi - a.roi)
  }

  /**
   * METRIC 4: Redundancy Tax
   * Cost of storing/retrieving overlapping memories
   */
  calculateRedundancyTax(memories: Memory[], similarityThreshold: number = 0.92): number {
    let redundantPairs = 0
    let redundantTokens = 0

    for (let i = 0; i < memories.length; i++) {
      for (let j = i + 1; j < memories.length; j++) {
        const similarity = this.cosineSimilarity(
          memories[i].embedding,
          memories[j].embedding
        )

        if (similarity > similarityThreshold) {
          redundantPairs++
          redundantTokens += Math.min(memories[i].tokens, memories[j].tokens)
        }
      }
    }

    // Assume redundant pairs are co-retrieved 30% of the time
    const coRetrievalRate = 0.3
    const monthlyCost = redundantTokens * this.config.inputTokenCost *
      this.config.queriesPerDay * 30 * coRetrievalRate

    return monthlyCost
  }

  /**
   * METRIC 6: Response Accuracy Delta
   * Quality improvement from using memory
   */
  calculateAccuracyDelta(
    withMemoryScores: number[],
    withoutMemoryScores: number[]
  ): number {
    if (withMemoryScores.length === 0 || withoutMemoryScores.length === 0) {
      return 0
    }

    const avgWith = withMemoryScores.reduce((a, b) => a + b, 0) / withMemoryScores.length
    const avgWithout = withoutMemoryScores.reduce((a, b) => a + b, 0) / withoutMemoryScores.length

    return ((avgWith - avgWithout) / avgWithout) * 100
  }

  /**
   * METRIC 7: Attribution Concentration (Gini Coefficient)
   * How evenly distributed is attribution across memories?
   */
  calculateGiniCoefficient(attributionScores: number[]): number {
    if (attributionScores.length === 0) return 0

    const n = attributionScores.length
    const sorted = [...attributionScores].sort((a, b) => a - b)

    let sum = 0
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        sum += Math.abs(sorted[i] - sorted[j])
      }
    }

    const mean = sorted.reduce((a, b) => a + b, 0) / n
    return sum / (2 * n * n * mean)
  }

  /**
   * METRIC 8: Memory Signal-to-Noise Ratio
   * Ratio of useful content to noise
   */
  calculateSNR(attributionScores: number[]): number {
    const signal = attributionScores
      .filter(s => s > 0)
      .reduce((sum, s) => sum + s * s, 0)

    const noise = attributionScores
      .filter(s => s <= 0)
      .reduce((sum, s) => sum + s * s, 0) + 1e-10 // Avoid division by zero

    return 10 * Math.log10(signal / noise)
  }

  /**
   * METRIC 11: Contradiction Risk Score
   * Probability of contradictory information in retrieved set
   */
  calculateContradictionRisk(contradictionProbabilities: number[]): number {
    if (contradictionProbabilities.length === 0) return 0

    // CRS = 1 - Π(1 - p_ij)
    let product = 1
    for (const prob of contradictionProbabilities) {
      product *= (1 - prob)
    }

    return 1 - product
  }

  /**
   * METRIC 12: Staleness Index
   * Fraction of frequently-retrieved memories that are stale
   */
  calculateStalenessIndex(
    memories: Memory[],
    frequencyThreshold: number,
    staleDays: number = 90
  ): number {
    const now = new Date()
    const staleThreshold = now.getTime() - staleDays * 24 * 60 * 60 * 1000

    // For this calculation, we'd need actual retrieval frequencies
    // Simplified: use lastAccessed as proxy
    const frequentMemories = memories.filter(m => {
      const daysSinceAccess = (now.getTime() - m.lastAccessed.getTime()) / (24 * 60 * 60 * 1000)
      return daysSinceAccess < 30 // Accessed in last 30 days = frequent
    })

    if (frequentMemories.length === 0) return 0

    const staleFrequentMemories = frequentMemories.filter(m =>
      m.createdAt.getTime() < staleThreshold
    )

    return (staleFrequentMemories.length / frequentMemories.length) * 100
  }

  /**
   * Complete Token Economics Summary
   */
  calculateTokenEconomics(
    memories: Memory[],
    attributionResults: AttributionResult[]
  ): TokenEconomics {
    const totalTokenCost = this.calculateMemoryTokenCost(memories)
    const { wasteRate, wasteCostPerDay } = this.calculateTokenWasteRate(memories, attributionResults)
    const redundancyTax = this.calculateRedundancyTax(memories)

    // Consolidation savings = waste + redundancy
    const consolidationSavings = (wasteCostPerDay * 30) + redundancyTax

    return {
      totalTokenCost,
      wasteRate,
      wasteCostPerDay,
      redundancyTax,
      consolidationSavings
    }
  }

  /**
   * Complete Accuracy Impact Summary
   */
  calculateAccuracyImpact(
    attributionResults: AttributionResult[],
    withMemoryScores: number[],
    withoutMemoryScores: number[]
  ): AccuracyImpact {
    const allScores = attributionResults.flatMap(r => r.scores.map(s => s.shapleyValue))

    return {
      accuracyDelta: this.calculateAccuracyDelta(withMemoryScores, withoutMemoryScores),
      giniCoefficient: this.calculateGiniCoefficient(allScores),
      snr: this.calculateSNR(allScores),
      hallucinationsPerDay: 0 // Would come from separate hallucination detection system
    }
  }

  /**
   * Utility: Cosine Similarity
   */
  private cosineSimilarity(a: number[], b: number[]): number {
    if (a.length !== b.length) return 0

    let dotProduct = 0
    let normA = 0
    let normB = 0

    for (let i = 0; i < a.length; i++) {
      dotProduct += a[i] * b[i]
      normA += a[i] * a[i]
      normB += b[i] * b[i]
    }

    const denom = Math.sqrt(normA) * Math.sqrt(normB)
    return denom === 0 ? 0 : dotProduct / denom
  }
}

/**
 * Generate random embedding for testing
 */
export function generateRandomEmbedding(dim: number = 768): number[] {
  const embedding = new Array(dim)
  let norm = 0

  for (let i = 0; i < dim; i++) {
    embedding[i] = Math.random() - 0.5
    norm += embedding[i] * embedding[i]
  }

  // Normalize
  norm = Math.sqrt(norm)
  for (let i = 0; i < dim; i++) {
    embedding[i] /= norm
  }

  return embedding
}
