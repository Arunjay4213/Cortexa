#!/usr/bin/env python3
"""Test CortexOS EAS with REAL LLMs (Claude or Gemini).

This test uses real LLM APIs to validate that EAS attribution
correlates with which memories a real LLM actually uses.

Usage:
    # With Claude API
    export ANTHROPIC_API_KEY="your-key"
    python tests/e2e/test_real_llm.py --llm claude --backend http://localhost:8001

    # With Gemini API
    export GOOGLE_API_KEY="your-key"
    python tests/e2e/test_real_llm.py --llm gemini --backend http://localhost:8001
"""

import asyncio
import os
import sys
import argparse
import numpy as np
from scipy import stats
import httpx
import uuid
from typing import List, Dict, Tuple

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from e2e.datasets import generate_personal_assistant_dataset
from e2e.agent_simulator import simple_embed


class RealLLM:
    """Real LLM (Claude or Gemini) with memory citation tracking."""

    def __init__(self, llm_type: str, api_key: str):
        self.llm_type = llm_type.lower()
        self.api_key = api_key

        if self.llm_type == "claude":
            self._init_claude()
        elif self.llm_type == "gemini":
            self._init_gemini()
        else:
            raise ValueError(f"Unknown LLM type: {llm_type}")

    def _init_claude(self):
        """Initialize Claude API client."""
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=self.api_key)
            self.model = "claude-3-5-sonnet-20241022"
        except ImportError:
            raise ImportError("Install: pip install anthropic")

    def _init_gemini(self):
        """Initialize Gemini API client."""
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self.client = genai.GenerativeModel("gemini-2.5-flash")
            self.model = "gemini-2.5-flash"
        except ImportError:
            raise ImportError("Install: pip install google-generativeai")

    async def generate_with_citations(
        self,
        query: str,
        memories: List[Tuple[str, str]],  # (id, content)
    ) -> Tuple[str, Dict[str, float]]:
        """Generate response and track which memories were cited.

        Returns:
            response: Generated text
            citation_scores: Dict[memory_id -> citation_weight (0-1)]
        """

        # Build prompt with numbered memories
        memory_text = "\n\n".join([
            f"[Memory {i+1}] (ID: {mem_id})\n{content}"
            for i, (mem_id, content) in enumerate(memories)
        ])

        prompt = f"""You are answering a question based on retrieved memories.

Retrieved Memories:
{memory_text}

Question: {query}

Instructions:
1. Answer the question using ONLY information from the memories above
2. For each piece of information you use, cite the memory number in brackets like [1] or [2]
3. If you use multiple memories, cite all of them
4. If no memories are relevant, say "I don't have information about that"

Answer:"""

        # Generate response
        if self.llm_type == "claude":
            response = await self._generate_claude(prompt)
        else:
            response = await self._generate_gemini(prompt)

        # Parse citations to compute weights
        citation_scores = self._parse_citations(response, memories)

        return response, citation_scores

    async def _generate_claude(self, prompt: str) -> str:
        """Generate with Claude API."""
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )
            return message.content[0].text
        except Exception as e:
            print(f"Claude API error: {e}")
            return ""

    async def _generate_gemini(self, prompt: str) -> str:
        """Generate with Gemini API."""
        try:
            response = self.client.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"Gemini API error: {e}")
            return ""

    def _parse_citations(
        self,
        response: str,
        memories: List[Tuple[str, str]],
    ) -> Dict[str, float]:
        """Parse [1], [2] citations from response.

        Returns citation weights (normalized to sum to 1.0).
        """
        import re

        # Find all [N] citations
        citations = re.findall(r'\[(\d+)\]', response)

        if not citations:
            # No citations found - return uniform weights as fallback
            return {mem_id: 1.0 / len(memories) for mem_id, _ in memories}

        # Count citations per memory
        citation_counts = {}
        for cite_num_str in citations:
            cite_idx = int(cite_num_str) - 1  # Convert to 0-indexed
            if 0 <= cite_idx < len(memories):
                mem_id = memories[cite_idx][0]
                citation_counts[mem_id] = citation_counts.get(mem_id, 0) + 1

        # Normalize to weights
        total_citations = sum(citation_counts.values())
        citation_weights = {}

        for mem_id, _ in memories:
            count = citation_counts.get(mem_id, 0)
            citation_weights[mem_id] = count / total_citations if total_citations > 0 else 0.0

        return citation_weights


async def test_real_llm_attribution(
    llm_type: str,
    api_key: str,
    backend_url: str,
    n_queries: int = 10,
):
    """Test EAS correlation with real LLM citations.

    Args:
        llm_type: "claude" or "gemini"
        api_key: API key for the LLM
        backend_url: CortexOS backend URL
        n_queries: Number of queries to test

    Returns:
        Dict with correlation results
    """

    print("="*70)
    print(f"REAL LLM TEST: {llm_type.upper()} vs CortexOS EAS")
    print("="*70)
    print()

    # 1. Load dataset
    print("Loading dataset...")
    dataset = generate_personal_assistant_dataset()
    memory_texts = [m.content for m in dataset.memories]
    memory_ids = [m.id for m in dataset.memories]
    print(f"✓ Loaded {len(memory_ids)} memories\n")

    # 2. Initialize real LLM
    print(f"Initializing {llm_type} API...")
    llm = RealLLM(llm_type, api_key)
    print(f"✓ Using model: {llm.model}\n")

    # 3. Pre-embed memories for retrieval
    print("Pre-embedding memories...")
    memory_embeddings = np.array([simple_embed(text) for text in memory_texts])
    print(f"✓ Embeddings shape: {memory_embeddings.shape}\n")

    # 4. Set up CortexOS backend (seed memories)
    print(f"Setting up CortexOS backend at {backend_url}...")
    agent_id = f"real_llm_test_{uuid.uuid4().hex[:8]}"

    memory_id_map = {}  # test_id -> backend_id

    async with httpx.AsyncClient() as client:
        for test_id, content in zip(memory_ids, memory_texts):
            try:
                resp = await client.post(
                    f"{backend_url}/api/v1/memories",
                    json={"agent_id": agent_id, "content": content},
                    timeout=10.0,
                )
                resp.raise_for_status()
                backend_id = resp.json().get("id")
                if backend_id:
                    memory_id_map[test_id] = backend_id
            except Exception as e:
                print(f"Warning: Failed to seed memory: {e}")

    print(f"✓ Seeded {len(memory_id_map)} memories to backend\n")

    # 5. Run queries through real LLM and get EAS scores
    print(f"Running {n_queries} queries...\n")

    correlations = []
    results = []

    test_queries = [
        "What's my favorite programming language?",
        "Tell me about my pet",
        "What time do I usually wake up?",
        "Where do I work?",
        "What's my favorite food?",
        "Tell me about my exercise routine",
        "What music do I like?",
        "What are my hobbies?",
        "What framework do I prefer for backend?",
        "What database do I usually use?",
    ]

    for i, query in enumerate(test_queries[:n_queries]):
        print(f"Query {i+1}/{n_queries}: {query[:50]}...")

        # Retrieve top-5 memories
        query_emb = simple_embed(query)
        similarities = memory_embeddings @ query_emb
        top_k_indices = np.argsort(similarities)[-5:][::-1]

        retrieved_memories = [
            (memory_ids[idx], memory_texts[idx])
            for idx in top_k_indices
        ]
        retrieved_ids = [memory_ids[idx] for idx in top_k_indices]

        # Generate response with real LLM (get citations)
        response, citation_weights = await llm.generate_with_citations(
            query, retrieved_memories
        )

        print(f"  Response: {response[:80]}...")
        print(f"  Citations: {sum(1 for w in citation_weights.values() if w > 0)} memories cited")

        # Get EAS scores from CortexOS
        retrieved_backend_ids = [memory_id_map[tid] for tid in retrieved_ids if tid in memory_id_map]

        eas_scores = {}
        try:
            async with httpx.AsyncClient() as client:
                transaction_resp = await client.post(
                    f"{backend_url}/api/v1/transactions",
                    json={
                        "agent_id": agent_id,
                        "query_text": query,
                        "query_embedding": query_emb.tolist(),
                        "retrieved_memory_ids": retrieved_backend_ids,
                        "response_text": response,
                    },
                    timeout=30.0,
                )
                transaction_resp.raise_for_status()
                result = transaction_resp.json()

                # Map backend IDs back to test IDs
                backend_to_test = {v: k for k, v in memory_id_map.items()}
                for score in result.get("scores", []):
                    backend_id = score["memory_id"]
                    test_id = backend_to_test.get(backend_id, backend_id)
                    eas_scores[test_id] = score["score"]

        except Exception as e:
            print(f"  Warning: EAS failed: {e}")
            continue

        # Compute correlation
        if len(eas_scores) >= 2 and len(citation_weights) >= 2:
            common_ids = set(eas_scores.keys()) & set(citation_weights.keys())
            if len(common_ids) >= 2:
                citation_vals = [citation_weights[mid] for mid in common_ids]
                eas_vals = [eas_scores[mid] for mid in common_ids]

                corr, _ = stats.spearmanr(citation_vals, eas_vals)
                if not np.isnan(corr):
                    correlations.append(corr)
                    print(f"  Correlation: {corr:.3f}")

        results.append({
            "query": query,
            "response": response,
            "citation_weights": citation_weights,
            "eas_scores": eas_scores,
        })

        print()

    # 6. Report results
    print("="*70)
    print("RESULTS")
    print("="*70)
    print()

    mean_corr = np.mean(correlations) if correlations else 0.0

    print(f"Queries tested: {len(results)}")
    print(f"Correlations computed: {len(correlations)}")
    print(f"Mean Spearman correlation: {mean_corr:.3f}")
    print()

    if mean_corr >= 0.5:
        print(f"✅ PASSED: EAS correlates well with {llm_type.upper()} citations!")
        print(f"   EAS can predict which memories real LLMs use.")
    elif mean_corr >= 0.3:
        print(f"⚠️  MODERATE: Some correlation ({mean_corr:.3f}), but not strong.")
        print(f"   EAS partially predicts {llm_type.upper()} memory usage.")
    else:
        print(f"❌ LOW: Weak correlation ({mean_corr:.3f}).")
        print(f"   EAS may not align well with {llm_type.upper()} citations.")

    print()

    # Cleanup
    print("Cleaning up...")
    async with httpx.AsyncClient() as client:
        for backend_id in memory_id_map.values():
            try:
                await client.delete(
                    f"{backend_url}/api/v1/memories/{backend_id}",
                    params={"agent_id": agent_id},
                    timeout=10.0,
                )
            except:
                pass

    print("✓ Cleanup complete\n")

    return {
        "llm_type": llm_type,
        "queries_tested": len(results),
        "mean_correlation": mean_corr,
        "correlations": correlations,
        "passed": mean_corr >= 0.5,
    }


async def main():
    parser = argparse.ArgumentParser(description="Test CortexOS EAS with real LLMs")
    parser.add_argument("--llm", required=True, choices=["claude", "gemini"],
                        help="LLM to test (claude or gemini)")
    parser.add_argument("--backend", required=True,
                        help="CortexOS backend URL (e.g., http://localhost:8001)")
    parser.add_argument("--queries", type=int, default=10,
                        help="Number of queries to test (default: 10)")

    args = parser.parse_args()

    # Get API key from environment
    if args.llm == "claude":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            print("❌ Error: ANTHROPIC_API_KEY not set")
            print("   Set it with: export ANTHROPIC_API_KEY='your-key'")
            sys.exit(1)
    else:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print("❌ Error: GOOGLE_API_KEY not set")
            print("   Set it with: export GOOGLE_API_KEY='your-key'")
            sys.exit(1)

    # Run test
    result = await test_real_llm_attribution(
        llm_type=args.llm,
        api_key=api_key,
        backend_url=args.backend,
        n_queries=args.queries,
    )

    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    asyncio.run(main())
