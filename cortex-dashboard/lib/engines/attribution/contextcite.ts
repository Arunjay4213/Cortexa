/**
 * CortexOS Engine 1: ContextCite Implementation
 *
 * ContextCite: Sparse linear surrogate model for memory attribution
 * Based on ablation sensitivity analysis with LASSO regression
 *
 * Reference: "Which Examples Should I Annotate?" (contextcite paper)
 */

import { Memory, Query, AgentResponse, AblationMask, AttributionScore, ContextCiteConfig } from './types'

export class ContextCite {
  private config: ContextCiteConfig

  constructor(config: ContextCiteConfig = {
    numSamples: 64,
    lassoLambda: 0.1,
    minConfidence: 0.8
  }) {
    this.config = config
  }

  /**
   * Compute attribution scores using ContextCite algorithm
   *
   * Algorithm:
   * 1. Generate ablation masks (which memories to include/exclude)
   * 2. Compute log-prob for each mask configuration
   * 3. Fit LASSO regression to learn attribution weights
   * 4. Return sparse attribution vector
   */
  async computeAttribution(
    query: Query,
    retrievedMemories: Memory[],
    response: AgentResponse,
    getLlmLogProb: (query: Query, memories: Memory[], response: AgentResponse) => Promise<number>
  ): Promise<AttributionScore[]> {
    // Validate inputs
    if (retrievedMemories.length === 0) {
      throw new Error('Cannot compute attribution for empty memory set')
    }

    const startTime = Date.now()
    const k = retrievedMemories.length

    // Step 1: Generate ablation masks
    const masks = this.generateAblationMasks(k)

    // Step 2: Compute log-probs for each mask (batched for efficiency)
    const logProbs = await this.computeLogProbs(
      query,
      retrievedMemories,
      response,
      masks,
      getLlmLogProb
    )

    // Step 3: Fit LASSO regression
    const weights = this.fitLasso(masks.map(m => m.mask), logProbs)

    // Step 4: Compute LDS (Linear Datamodeling Score) for quality assessment
    const lds = this.computeLDS(masks.map(m => m.mask), logProbs, weights)

    const computeTimeMs = Date.now() - startTime

    // Step 5: Convert weights to attribution scores
    return retrievedMemories.map((memory, i) => ({
      memoryId: memory.id,
      shapleyValue: weights[i],
      confidence: lds,
      method: 'contextcite' as const,
      computeTimeMs: computeTimeMs / k
    }))
  }

  /**
   * Generate random ablation masks
   * Each mask is a binary vector indicating which memories to include
   */
  private generateAblationMasks(k: number): AblationMask[] {
    const masks: AblationMask[] = []

    // Always include all-zeros and all-ones for baseline
    masks.push({ mask: new Array(k).fill(false), logProb: 0 })
    masks.push({ mask: new Array(k).fill(true), logProb: 0 })

    // Generate random masks using Bernoulli(0.5)
    for (let i = 0; i < this.config.numSamples - 2; i++) {
      const mask = new Array(k).fill(0).map(() => Math.random() > 0.5)
      masks.push({ mask, logProb: 0 })
    }

    return masks
  }

  /**
   * Compute log-probabilities for each ablation mask
   * This is the expensive part - requires LLM forward passes
   */
  private async computeLogProbs(
    query: Query,
    allMemories: Memory[],
    response: AgentResponse,
    masks: AblationMask[],
    getLlmLogProb: (query: Query, memories: Memory[], response: AgentResponse) => Promise<number>
  ): Promise<number[]> {
    const logProbs: number[] = []

    // In production, this would be batched for efficiency
    for (const maskObj of masks) {
      const selectedMemories = allMemories.filter((_, i) => maskObj.mask[i])
      const logProb = await getLlmLogProb(query, selectedMemories, response)
      logProbs.push(logProb)
    }

    return logProbs
  }

  /**
   * Fit LASSO regression to learn attribution weights
   *
   * Objective: minimize ||y - Zw||^2 + lambda * ||w||_1
   * where Z is the matrix of masks, y are the log-probs, w are weights
   */
  private fitLasso(masks: boolean[][], logProbs: number[]): number[] {
    const n = masks.length
    const k = masks[0].length

    // Convert masks to numerical matrix
    const Z = masks.map(mask => mask.map(b => b ? 1 : 0))

    // Use log-probs directly (they're already in the right space)
    const y = logProbs

    // Coordinate descent for LASSO
    // Initialize weights to zero
    let w = new Array(k).fill(0)
    const maxIterations = 1000
    const tolerance = 1e-6

    for (let iter = 0; iter < maxIterations; iter++) {
      const wOld = [...w]

      // Update each weight coordinate
      for (let j = 0; j < k; j++) {
        // Compute partial residual (excluding feature j)
        const residual = y.map((yi, i) => {
          const prediction = Z[i].reduce((sum, zij, jj) =>
            jj === j ? sum : sum + zij * w[jj], 0
          )
          return yi - prediction
        })

        // Compute unnormalized weight update
        const rho = residual.reduce((sum, r, i) => sum + r * Z[i][j], 0)

        // Compute feature normalization (sum of squares)
        const zzj = Z.reduce((sum, zi) => sum + zi[j] * zi[j], 0)

        // Soft thresholding operator
        const threshold = this.config.lassoLambda * n
        if (zzj === 0) {
          w[j] = 0
        } else if (rho > threshold) {
          w[j] = (rho - threshold) / zzj
        } else if (rho < -threshold) {
          w[j] = (rho + threshold) / zzj
        } else {
          w[j] = 0
        }
      }

      // Check convergence
      const change = w.reduce((sum, wi, i) => sum + Math.abs(wi - wOld[i]), 0)
      if (change < tolerance) break
    }

    return w
  }

  /**
   * Compute Linear Datamodeling Score (LDS)
   * Measures how well the linear surrogate fits the true model
   * LDS = Pearson correlation between predictions and true log-probs
   */
  private computeLDS(masks: boolean[][], logProbs: number[], weights: number[]): number {
    const Z = masks.map(mask => mask.map(b => b ? 1 : 0))
    const predictions = Z.map(row =>
      row.reduce((sum, zij, j) => sum + zij * weights[j], 0)
    )

    return this.pearsonCorrelation(predictions, logProbs)
  }

  /**
   * Logit function: inverse of sigmoid
   */
  private logit(p: number): number {
    // Clamp to avoid numerical issues
    p = Math.max(1e-10, Math.min(1 - 1e-10, p))
    return Math.log(p / (1 - p))
  }

  /**
   * Pearson correlation coefficient
   */
  private pearsonCorrelation(x: number[], y: number[]): number {
    const n = x.length
    const meanX = x.reduce((a, b) => a + b, 0) / n
    const meanY = y.reduce((a, b) => a + b, 0) / n

    let numerator = 0
    let denomX = 0
    let denomY = 0

    for (let i = 0; i < n; i++) {
      const dx = x[i] - meanX
      const dy = y[i] - meanY
      numerator += dx * dy
      denomX += dx * dx
      denomY += dy * dy
    }

    return numerator / Math.sqrt(denomX * denomY)
  }
}

/**
 * Mock LLM log-prob function for testing
 * In production, this would call actual LLM API
 */
export async function mockGetLlmLogProb(
  query: Query,
  memories: Memory[],
  response: AgentResponse
): Promise<number> {
  // Simulate log-prob based on memory relevance
  // Higher relevance = higher log-prob
  const relevanceScores = memories.map(mem =>
    cosineSimilarity(mem.embedding, response.embedding)
  )

  const avgRelevance = relevanceScores.length > 0
    ? relevanceScores.reduce((a, b) => a + b, 0) / relevanceScores.length
    : 0.5

  // Convert to log-prob (simplified)
  return Math.log(avgRelevance + 0.1)
}

/**
 * Cosine similarity between two vectors
 */
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

  return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB))
}
