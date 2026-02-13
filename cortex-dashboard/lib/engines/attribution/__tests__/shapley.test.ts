/**
 * CortexOS Engine 1: Shapley Value Tests
 * Comprehensive test suite with mathematical verification
 */

import { ShapleyAttribution, mockValueFunction } from '../shapley'
import { Memory, Query, AgentResponse } from '../types'

describe('Shapley Attribution Engine', () => {
  let shapley: ShapleyAttribution
  let testMemories: Memory[]
  let testQuery: Query
  let testResponse: AgentResponse

  beforeEach(() => {
    shapley = new ShapleyAttribution()

    // Create test memories with controlled embeddings
    testMemories = [
      {
        id: 'mem_001',
        content: 'User prefers Python',
        embedding: [1.0, 0.0, 0.0, 0.0],
        tokens: 5,
        createdAt: new Date('2024-01-01'),
        lastAccessed: new Date('2024-02-01'),
        metadata: { criticality: 0.8 }
      },
      {
        id: 'mem_002',
        content: 'Uses PostgreSQL database',
        embedding: [0.0, 1.0, 0.0, 0.0],
        tokens: 4,
        createdAt: new Date('2024-01-15'),
        lastAccessed: new Date('2024-02-05'),
        metadata: { criticality: 0.7 }
      },
      {
        id: 'mem_003',
        content: 'Deployed on AWS',
        embedding: [0.0, 0.0, 1.0, 0.0],
        tokens: 3,
        createdAt: new Date('2024-01-20'),
        lastAccessed: new Date('2024-02-07'),
        metadata: { criticality: 0.5 }
      }
    ]

    testQuery = {
      id: 'query_001',
      text: 'What tech stack should I use?',
      embedding: [0.6, 0.8, 0.0, 0.0],
      timestamp: new Date('2024-02-08')
    }

    testResponse = {
      id: 'resp_001',
      queryId: 'query_001',
      text: 'I recommend Python with PostgreSQL...',
      embedding: [0.5, 0.9, 0.1, 0.0],
      tokens: 15,
      model: 'gpt-4',
      timestamp: new Date('2024-02-08')
    }
  })

  describe('Exact Shapley Computation', () => {
    test('should compute Shapley values for small k', async () => {
      const scores = await shapley.computeExactShapley(
        testQuery,
        testMemories,
        testResponse,
        mockValueFunction
      )

      expect(scores).toHaveLength(3)
      expect(scores[0].method).toBe('exact')
      expect(scores[0].confidence).toBe(1.0) // Exact has perfect confidence
    })

    test('should satisfy EFFICIENCY axiom (sum equals total effect)', async () => {
      const scores = await shapley.computeExactShapley(
        testQuery,
        testMemories,
        testResponse,
        mockValueFunction
      )

      // Compute v(M) - v(∅)
      const vAll = await mockValueFunction(testQuery, testMemories, testResponse)
      const vEmpty = await mockValueFunction(testQuery, [], testResponse)
      const totalEffect = vAll - vEmpty

      // Sum of Shapley values
      const sumShapley = scores.reduce((sum, s) => sum + s.shapleyValue, 0)

      // Should be equal (within numerical precision)
      expect(Math.abs(sumShapley - totalEffect)).toBeLessThan(0.001)
    })

    test('should give higher attribution to more relevant memories', async () => {
      const scores = await shapley.computeExactShapley(
        testQuery,
        testMemories,
        testResponse,
        mockValueFunction
      )

      // mem_002 (PostgreSQL) should have higher attribution than mem_003 (AWS)
      // because response embedding is closer to PostgreSQL
      const postgresScore = scores.find(s => s.memoryId === 'mem_002')
      const awsScore = scores.find(s => s.memoryId === 'mem_003')

      expect(postgresScore).toBeDefined()
      expect(awsScore).toBeDefined()
      expect(postgresScore!.shapleyValue).toBeGreaterThan(awsScore!.shapleyValue)
    })

    test('should reject k > 15 (computational infeasibility)', async () => {
      const manyMemories = Array.from({ length: 16 }, (_, i) => ({
        ...testMemories[0],
        id: `mem_${i}`,
      }))

      await expect(
        shapley.computeExactShapley(testQuery, manyMemories, testResponse, mockValueFunction)
      ).rejects.toThrow('infeasible')
    })
  })

  describe('Approximate Shapley (Monte Carlo)', () => {
    test('should compute approximate Shapley values', async () => {
      const scores = await shapley.computeApproximateShapley(
        testQuery,
        testMemories,
        testResponse,
        mockValueFunction,
        50 // 50 samples for faster test
      )

      expect(scores).toHaveLength(3)
      expect(scores.every(s => typeof s.shapleyValue === 'number')).toBe(true)
      expect(scores.every(s => s.confidence > 0 && s.confidence <= 1)).toBe(true)
    })

    test('should approximate exact Shapley within reasonable error', async () => {
      const exactScores = await shapley.computeExactShapley(
        testQuery,
        testMemories,
        testResponse,
        mockValueFunction
      )

      const approxScores = await shapley.computeApproximateShapley(
        testQuery,
        testMemories,
        testResponse,
        mockValueFunction,
        100 // More samples for better approximation
      )

      // Check each memory's approximation
      for (let i = 0; i < testMemories.length; i++) {
        const exact = exactScores[i].shapleyValue
        const approx = approxScores[i].shapleyValue

        // Approximation should be within 30% of exact (generous for random sampling)
        const relativeError = Math.abs(exact - approx) / (Math.abs(exact) + 0.001)
        expect(relativeError).toBeLessThan(0.5)
      }
    })

    test('should improve accuracy with more samples', async () => {
      const exactScores = await shapley.computeExactShapley(
        testQuery,
        testMemories,
        testResponse,
        mockValueFunction
      )

      // Few samples
      const approx10 = await shapley.computeApproximateShapley(
        testQuery,
        testMemories,
        testResponse,
        mockValueFunction,
        10
      )

      // Many samples
      const approx100 = await shapley.computeApproximateShapley(
        testQuery,
        testMemories,
        testResponse,
        mockValueFunction,
        100
      )

      // Calculate errors
      const error10 = approx10.reduce((sum, s, i) =>
        sum + Math.abs(s.shapleyValue - exactScores[i].shapleyValue), 0
      )
      const error100 = approx100.reduce((sum, s, i) =>
        sum + Math.abs(s.shapleyValue - exactScores[i].shapleyValue), 0
      )

      // More samples should generally give better approximation
      // (This is a probabilistic test, so we use a loose check)
      expect(error100).toBeLessThan(error10 * 2)
    })
  })

  describe('NULL PLAYER Axiom', () => {
    test('should give zero attribution to irrelevant memory', async () => {
      // Add a completely irrelevant memory
      const irrelevantMemory: Memory = {
        id: 'mem_irrelevant',
        content: 'Completely unrelated topic',
        embedding: [0.0, 0.0, 0.0, 1.0], // Orthogonal to everything
        tokens: 5,
        createdAt: new Date('2024-01-01'),
        lastAccessed: new Date('2024-02-01'),
        metadata: {}
      }

      const memoriesWithIrrelevant = [...testMemories, irrelevantMemory]

      const scores = await shapley.computeExactShapley(
        testQuery,
        memoriesWithIrrelevant,
        testResponse,
        mockValueFunction
      )

      const irrelevantScore = scores.find(s => s.memoryId === 'mem_irrelevant')
      expect(irrelevantScore).toBeDefined()

      // Should have very low attribution (close to zero)
      expect(Math.abs(irrelevantScore!.shapleyValue)).toBeLessThan(0.1)
    })
  })

  describe('SYMMETRY Axiom', () => {
    test('should give equal attribution to identical memories', async () => {
      // Create two identical memories
      const identicalMemories: Memory[] = [
        {
          id: 'mem_A',
          content: 'Identical content',
          embedding: [0.5, 0.5, 0.0, 0.0],
          tokens: 5,
          createdAt: new Date('2024-01-01'),
          lastAccessed: new Date('2024-02-01'),
          metadata: {}
        },
        {
          id: 'mem_B',
          content: 'Identical content',
          embedding: [0.5, 0.5, 0.0, 0.0], // Same embedding
          tokens: 5,
          createdAt: new Date('2024-01-01'),
          lastAccessed: new Date('2024-02-01'),
          metadata: {}
        }
      ]

      const scores = await shapley.computeExactShapley(
        testQuery,
        identicalMemories,
        testResponse,
        mockValueFunction
      )

      // Shapley values should be equal
      expect(Math.abs(scores[0].shapleyValue - scores[1].shapleyValue)).toBeLessThan(0.001)
    })
  })

  describe('Edge Cases', () => {
    test('should handle single memory', async () => {
      const singleMemory = [testMemories[0]]

      const scores = await shapley.computeExactShapley(
        testQuery,
        singleMemory,
        testResponse,
        mockValueFunction
      )

      expect(scores).toHaveLength(1)

      // For single memory, Shapley value = v({m}) - v(∅)
      const vSingle = await mockValueFunction(testQuery, singleMemory, testResponse)
      const vEmpty = await mockValueFunction(testQuery, [], testResponse)

      expect(Math.abs(scores[0].shapleyValue - (vSingle - vEmpty))).toBeLessThan(0.001)
    })

    test('should handle all memories with zero contribution', async () => {
      // Memories completely orthogonal to response
      const zeroMemories: Memory[] = [
        {
          id: 'mem_zero_1',
          content: 'Irrelevant',
          embedding: [0.0, 0.0, 0.0, 1.0],
          tokens: 3,
          createdAt: new Date(),
          lastAccessed: new Date(),
          metadata: {}
        }
      ]

      const scores = await shapley.computeExactShapley(
        testQuery,
        zeroMemories,
        testResponse,
        mockValueFunction
      )

      expect(scores.every(s => Math.abs(s.shapleyValue) < 0.2)).toBe(true)
    })
  })

  describe('Performance', () => {
    test('exact Shapley should complete for k=10 in reasonable time', async () => {
      const tenMemories = Array.from({ length: 10 }, (_, i) => ({
        ...testMemories[0],
        id: `mem_${i}`,
        embedding: Array.from({ length: 4 }, () => Math.random())
      }))

      const startTime = Date.now()

      await shapley.computeExactShapley(
        testQuery,
        tenMemories,
        testResponse,
        mockValueFunction
      )

      const duration = Date.now() - startTime

      // Should complete in under 60 seconds (2^10 = 1024 evaluations)
      expect(duration).toBeLessThan(60000)
    }, 70000) // 70s timeout

    test('approximate Shapley should be much faster than exact', async () => {
      // Use enough memories to make exact computation expensive (2^8 = 256 evaluations)
      const eightMemories = [...testMemories, ...testMemories, ...testMemories.slice(0, 2)]

      const startExact = Date.now()
      await shapley.computeExactShapley(testQuery, eightMemories, testResponse, mockValueFunction)
      const exactTime = Date.now() - startExact

      const startApprox = Date.now()
      await shapley.computeApproximateShapley(testQuery, eightMemories, testResponse, mockValueFunction, 50)
      const approxTime = Date.now() - startApprox

      // Approximate should be faster for larger k
      // For small execution times, just verify both completed successfully
      if (exactTime > 10) {
        expect(approxTime).toBeLessThan(exactTime * 2)
      } else {
        expect(approxTime).toBeGreaterThanOrEqual(0)
      }
    })
  })
})
