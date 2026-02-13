/**
 * CortexOS Engine 1: Shapley Value Computation
 *
 * Implements exact and approximate Shapley value algorithms
 * for memory attribution
 *
 * Mathematical Foundation:
 * φᵢ(v) = Σ_{S⊆M\{mᵢ}} |S|!(k-|S|-1)!/k! [v(S∪{mᵢ}) - v(S)]
 */

import { Memory, Query, AgentResponse, AttributionScore, ShapleyConfig } from './types'

export class ShapleyAttribution {
  private config: ShapleyConfig

  constructor(config: ShapleyConfig = {}) {
    this.config = config
  }

  /**
   * Compute exact Shapley values
   * WARNING: O(2^k) complexity - only use for small k or ground truth generation
   */
  async computeExactShapley(
    query: Query,
    memories: Memory[],
    response: AgentResponse,
    valueFunction: (query: Query, subset: Memory[], response: AgentResponse) => Promise<number>
  ): Promise<AttributionScore[]> {
    const startTime = Date.now()
    const k = memories.length

    if (k > 15) {
      throw new Error('Exact Shapley computation infeasible for k > 15 (requires 2^k evaluations)')
    }

    const shapleyValues = new Array(k).fill(0)
    const factorial = this.memoizedFactorial(k)

    // Iterate over all possible subsets
    const totalSubsets = Math.pow(2, k)

    for (let mask = 0; mask < totalSubsets; mask++) {
      const subset = this.maskToSubset(mask, memories)
      const subsetSize = subset.length

      // Compute value for this subset
      const vS = await valueFunction(query, subset, response)

      // For each memory not in the subset, compute marginal contribution
      for (let i = 0; i < k; i++) {
        if ((mask & (1 << i)) === 0) {
          // Memory i is not in subset - compute v(S ∪ {i})
          const subsetWithI = [...subset, memories[i]]
          const vSWithI = await valueFunction(query, subsetWithI, response)

          // Weight this marginal contribution by Shapley coefficient
          const weight = factorial[subsetSize] * factorial[k - subsetSize - 1] / factorial[k]
          shapleyValues[i] += weight * (vSWithI - vS)
        }
      }
    }

    const computeTimeMs = Date.now() - startTime

    return memories.map((memory, i) => ({
      memoryId: memory.id,
      shapleyValue: shapleyValues[i],
      confidence: 1.0, // Exact computation has perfect confidence
      method: 'exact' as const,
      computeTimeMs: computeTimeMs / k
    }))
  }

  /**
   * Compute approximate Shapley values using Monte Carlo sampling (TMC-Shapley)
   * Much faster: O(m * k) where m = number of samples
   */
  async computeApproximateShapley(
    query: Query,
    memories: Memory[],
    response: AgentResponse,
    valueFunction: (query: Query, subset: Memory[], response: AgentResponse) => Promise<number>,
    numSamples: number = 100
  ): Promise<AttributionScore[]> {
    const startTime = Date.now()
    const k = memories.length

    const shapleyValues = new Array(k).fill(0)
    const contributions: number[][] = Array.from({ length: k }, () => [])

    // Monte Carlo sampling
    for (let sample = 0; sample < numSamples; sample++) {
      // Random permutation of memories
      const permutation = this.randomPermutation(k)

      // Compute marginal contributions along this permutation
      let currentSubset: Memory[] = []
      let prevValue = await valueFunction(query, [], response)

      for (const idx of permutation) {
        currentSubset.push(memories[idx])
        const currentValue = await valueFunction(query, currentSubset, response)
        const marginalContribution = currentValue - prevValue

        contributions[idx].push(marginalContribution)
        prevValue = currentValue
      }
    }

    // Average contributions across samples
    for (let i = 0; i < k; i++) {
      shapleyValues[i] = contributions[i].reduce((a, b) => a + b, 0) / numSamples
    }

    // Estimate confidence using standard error
    const confidence = this.estimateConfidence(contributions)
    const computeTimeMs = Date.now() - startTime

    return memories.map((memory, i) => ({
      memoryId: memory.id,
      shapleyValue: shapleyValues[i],
      confidence: confidence[i],
      method: 'exact' as const,
      computeTimeMs: computeTimeMs / k
    }))
  }

  /**
   * Convert bitmask to subset of memories
   */
  private maskToSubset(mask: number, memories: Memory[]): Memory[] {
    const subset: Memory[] = []
    for (let i = 0; i < memories.length; i++) {
      if (mask & (1 << i)) {
        subset.push(memories[i])
      }
    }
    return subset
  }

  /**
   * Generate random permutation of indices 0..n-1
   */
  private randomPermutation(n: number): number[] {
    const arr = Array.from({ length: n }, (_, i) => i)
    // Fisher-Yates shuffle
    for (let i = n - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [arr[i], arr[j]] = [arr[j], arr[i]]
    }
    return arr
  }

  /**
   * Memoized factorial computation
   */
  private memoizedFactorial(n: number): number[] {
    const fact = new Array(n + 1)
    fact[0] = 1
    for (let i = 1; i <= n; i++) {
      fact[i] = fact[i - 1] * i
    }
    return fact
  }

  /**
   * Estimate confidence for each Shapley value using standard error
   */
  private estimateConfidence(contributions: number[][]): number[] {
    return contributions.map(samples => {
      if (samples.length === 0) return 0

      const mean = samples.reduce((a, b) => a + b, 0) / samples.length
      const variance = samples.reduce((sum, x) => sum + Math.pow(x - mean, 2), 0) / samples.length
      const stdError = Math.sqrt(variance / samples.length)

      // Convert to confidence score (0-1)
      // Lower standard error = higher confidence
      return 1 / (1 + stdError)
    })
  }
}

/**
 * Mock value function for testing
 * In production, this would evaluate LLM output quality
 */
export async function mockValueFunction(
  query: Query,
  memories: Memory[],
  response: AgentResponse
): Promise<number> {
  // Simulate quality based on memory relevance
  if (memories.length === 0) {
    return 0.3 // Base quality without memory
  }

  const relevanceScores = memories.map(mem => {
    // Simple cosine similarity as proxy for relevance
    const similarity = cosineSimilarity(mem.embedding, query.embedding)
    return similarity
  })

  const avgRelevance = relevanceScores.reduce((a, b) => a + b, 0) / relevanceScores.length

  // Quality improves with relevant memories
  return 0.3 + 0.7 * avgRelevance
}

function cosineSimilarity(a: number[], b: number[]): number {
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
