"""Agent Simulator with MockLLM for E2E testing.

Simulates a real Mem0/Supermemory-powered agent with ground truth tracking.
The MockLLM deliberately chooses which memories to use, giving us ground truth
for validating CortexOS attribution scores.
"""

from __future__ import annotations
from dataclasses import dataclass
import random
import numpy as np
from typing import Protocol
import re
import httpx
import asyncio
from datetime import datetime, UTC
import uuid


@dataclass
class MemoryWithId:
    """Memory with ID for tracking."""
    id: str
    content: str
    similarity: float  # cosine similarity to query


@dataclass
class SimulationResult:
    """Result of processing one query through the agent."""
    query: str
    retrieved_memories: list[MemoryWithId]
    response: str
    ground_truth_sources: list[str]  # memory IDs actually used by LLM
    ground_truth_weights: dict[str, float]  # memory_id -> usage weight (0-1)
    cortex_attribution: dict[str, float] | None  # memory_id -> EAS score (populated later)
    cortex_transaction_id: str | None


class LLM(Protocol):
    """LLM interface for generating responses."""

    def generate(
        self,
        query: str,
        retrieved_memories: list[MemoryWithId],
    ) -> tuple[str, list[str], dict[str, float]]:
        """Generate response from query and memories.

        Returns:
            response: The generated text
            sources: List of memory IDs actually used
            weights: Dict of memory_id -> usage weight (0-1)
        """
        ...


class MockLLM:
    """Mock LLM that generates responses with known ground truth.

    Strategy:
    1. Randomly select 2-4 memories from retrieved set
    2. Extract key phrases from selected memories
    3. Paraphrase and combine them with:
       - Word shuffling
       - Synonym substitution
       - Sentence recombination
    4. Add 10-20% novel content not from any memory
    5. Track exactly which memories were used and their weights

    This gives us perfect ground truth: we know exactly which memories
    the response was derived from and how much each contributed.
    """

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.np_rng = np.random.default_rng(seed)

        # Synonym map for paraphrasing
        self.synonyms = {
            "prefer": ["like", "favor", "choose", "opt for"],
            "use": ["utilize", "employ", "apply", "work with"],
            "always": ["consistently", "regularly", "typically", "usually"],
            "never": ["rarely", "seldom", "not often", "avoid"],
            "good": ["excellent", "great", "fine", "solid"],
            "bad": ["poor", "subpar", "inadequate", "problematic"],
            "fast": ["quick", "rapid", "speedy", "swift"],
            "slow": ["sluggish", "gradual", "unhurried", "leisurely"],
            "important": ["crucial", "vital", "essential", "key"],
            "simple": ["straightforward", "easy", "basic", "uncomplicated"],
        }

    def _paraphrase(self, text: str) -> str:
        """Paraphrase text with synonym substitution and word shuffling."""
        words = text.split()

        # Synonym substitution (30% of words)
        for i in range(len(words)):
            word_lower = words[i].lower().strip(".,!?;:")
            if word_lower in self.synonyms and self.rng.random() < 0.3:
                words[i] = self.rng.choice(self.synonyms[word_lower])

        # Slight word reordering (keep it grammatical)
        # Just swap adjacent words occasionally
        for i in range(len(words) - 1):
            if self.rng.random() < 0.1:
                words[i], words[i + 1] = words[i + 1], words[i]

        return " ".join(words)

    def _extract_key_phrases(self, memory_content: str) -> list[str]:
        """Extract 1-3 key phrases from memory content."""
        # Split into sentences
        sentences = re.split(r'[.!?]+', memory_content)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return [memory_content]

        # Take 1-2 sentences
        n_sentences = min(len(sentences), self.rng.randint(1, 2))
        selected = self.rng.sample(sentences, n_sentences)

        return selected

    def _generate_novel_content(self, query: str) -> str:
        """Generate novel content not from any memory."""
        templates = [
            f"Based on your question about {self._extract_topic(query)}, here's what I think:",
            f"Regarding {self._extract_topic(query)}, let me clarify:",
            "Additionally, it's worth noting that",
            "One more thing to consider is",
            "From my understanding,",
            "In general,",
        ]

        return self.rng.choice(templates)

    def _extract_topic(self, query: str) -> str:
        """Extract rough topic from query."""
        # Very simple: take first few words
        words = query.split()[:3]
        return " ".join(words).rstrip("?.,!;:")

    def generate(
        self,
        query: str,
        retrieved_memories: list[MemoryWithId],
    ) -> tuple[str, list[str], dict[str, float]]:
        """Generate response with ground truth tracking."""

        if not retrieved_memories:
            # No memories: pure hallucination
            response = f"I don't have specific information about that. {self._generate_novel_content(query)}"
            return response, [], {}

        # Select 2-4 memories to actually use (or fewer if less available)
        n_memories_to_use = min(
            len(retrieved_memories),
            self.rng.randint(2, 4)
        )

        # Bias selection toward higher-similarity memories
        # Use softmax on similarity scores to get selection probabilities
        similarities = np.array([m.similarity for m in retrieved_memories])
        # Avoid division by zero or overflow
        if similarities.max() > 0:
            exp_sims = np.exp(similarities - similarities.max())
            probs = exp_sims / exp_sims.sum()
        else:
            probs = np.ones(len(similarities)) / len(similarities)

        selected_indices = self.np_rng.choice(
            len(retrieved_memories),
            size=n_memories_to_use,
            replace=False,
            p=probs
        )

        selected_memories = [retrieved_memories[i] for i in selected_indices]

        # Assign selection weights (how much to favor each memory when building response)
        # Use Dirichlet distribution for realistic weight distribution
        selection_weights = self.np_rng.dirichlet([1.0] * len(selected_memories))

        # Build response from selected memories
        response_parts = []
        memory_contributions = {}  # Track which parts came from which memory

        # Add novel opening (10% of response)
        novel_opening = self._generate_novel_content(query)
        response_parts.append(novel_opening)

        # Add paraphrased content from each selected memory (weighted by selection importance)
        for mem, weight in zip(selected_memories, selection_weights):
            # Extract key phrases
            phrases = self._extract_key_phrases(mem.content)

            # Paraphrase them
            paraphrased = [self._paraphrase(p) for p in phrases]

            # Add to response (more weight = more content)
            n_phrases = max(1, int(len(paraphrased) * weight * 2))
            used_phrases = paraphrased[:n_phrases]

            # Track contribution
            memory_contributions[mem.id] = used_phrases
            response_parts.extend(used_phrases)

        # Shuffle parts slightly for naturalness
        if len(response_parts) > 2:
            middle_parts = response_parts[1:]
            self.rng.shuffle(middle_parts)
            response_parts = [response_parts[0]] + middle_parts

        response = " ".join(response_parts)

        # CRITICAL FIX: Compute ground truth weights based on ACTUAL token contribution
        # Count tokens from each memory that appear in the final response
        total_response_tokens = len(response.split())

        # Initialize weights for ALL retrieved memories (not just selected)
        ground_truth_weights = {}
        for mem in retrieved_memories:
            ground_truth_weights[mem.id] = 0.0  # Default to 0 for all memories

        # Update weights for selected memories based on actual contribution
        for mem in selected_memories:
            if mem.id in memory_contributions:
                # Count tokens from this memory's phrases
                mem_tokens = sum(len(phrase.split()) for phrase in memory_contributions[mem.id])
                weight = mem_tokens / max(total_response_tokens, 1)
                ground_truth_weights[mem.id] = float(weight)

        # Normalize weights to sum to 1.0 (excluding novel content)
        total_weight = sum(ground_truth_weights.values())
        if total_weight > 0:
            ground_truth_weights = {
                mem_id: weight / total_weight
                for mem_id, weight in ground_truth_weights.items()
            }

        sources = [mem.id for mem in selected_memories]

        return response, sources, ground_truth_weights


class AgentSimulator:
    """Simulates a Mem0/Supermemory-powered agent.

    Workflow:
    1. Receive query
    2. Retrieve top-k memories via cosine similarity
    3. Construct prompt with system + memories + query
    4. Call LLM to generate response
    5. Report transaction to CortexOS
    6. Return SimulationResult with ground truth
    """

    def __init__(
        self,
        memories: list[tuple[str, str]],  # (id, content)
        memory_embeddings: np.ndarray,  # (N, d) embedding matrix
        embed_fn: callable,  # Function to embed queries
        cortex_client=None,  # CortexOS client (optional for testing)
        llm: LLM | None = None,
        k: int = 5,  # Number of memories to retrieve
        memory_id_map: dict[str, str] | None = None,  # test_id -> backend_id mapping
    ):
        """Initialize agent simulator.

        Args:
            memories: List of (memory_id, content) tuples
            memory_embeddings: Pre-computed embeddings for memories (N, d)
            embed_fn: Function that takes text and returns embedding
            cortex_client: Optional CortexOS client for reporting
            llm: LLM to use (defaults to MockLLM)
            k: Number of memories to retrieve per query
            memory_id_map: Mapping from test memory IDs to backend memory IDs
        """
        self.memories = memories
        self.memory_embeddings = memory_embeddings
        self.embed_fn = embed_fn
        self.cortex_client = cortex_client
        self.llm = llm or MockLLM()
        self.k = k
        self.memory_id_map = memory_id_map or {}

        # Build ID -> index mapping
        self.id_to_idx = {mem_id: i for i, (mem_id, _) in enumerate(memories)}

    def _cosine_similarity(self, query_emb: np.ndarray, memory_embs: np.ndarray) -> np.ndarray:
        """Compute cosine similarity between query and all memories."""
        # Normalize
        query_norm = query_emb / (np.linalg.norm(query_emb) + 1e-8)
        memory_norms = memory_embs / (np.linalg.norm(memory_embs, axis=1, keepdims=True) + 1e-8)

        # Dot product
        similarities = memory_norms @ query_norm

        return similarities

    def _retrieve_memories(self, query: str) -> list[MemoryWithId]:
        """Retrieve top-k memories for query via cosine similarity."""
        # Embed query
        query_emb = self.embed_fn(query)

        # Compute similarities
        similarities = self._cosine_similarity(query_emb, self.memory_embeddings)

        # Get top-k indices
        top_k_indices = np.argsort(similarities)[-self.k:][::-1]

        # Build results
        retrieved = []
        for idx in top_k_indices:
            mem_id, content = self.memories[idx]
            retrieved.append(MemoryWithId(
                id=mem_id,
                content=content,
                similarity=float(similarities[idx])
            ))

        return retrieved

    async def process_query(self, query: str, agent_id: str = "simulator") -> SimulationResult:
        """Process query through the agent workflow.

        Returns SimulationResult with ground truth and CortexOS attribution.
        """
        # Step 1: Retrieve memories
        retrieved_memories = self._retrieve_memories(query)

        # Step 2: Generate response with LLM
        response, sources, weights = self.llm.generate(query, retrieved_memories)

        # Step 3: Report to CortexOS (if client provided)
        cortex_attribution = None
        transaction_id = None

        if self.cortex_client:
            try:
                # Prepare transaction data
                retrieved_test_ids = [m.id for m in retrieved_memories]

                # Map test IDs to backend IDs (if mapping exists)
                retrieved_backend_ids = []
                for test_id in retrieved_test_ids:
                    backend_id = self.memory_id_map.get(test_id)
                    if backend_id:
                        retrieved_backend_ids.append(backend_id)
                    else:
                        # If no mapping, use test ID as-is (won't work with backend but keeps test running)
                        retrieved_backend_ids.append(test_id)

                # Compute query embedding
                query_embedding = self.embed_fn(query)

                # POST /api/v1/transactions (single-shot)
                transaction_data = {
                    "agent_id": agent_id,
                    "query_text": query,
                    "query_embedding": query_embedding.tolist(),
                    "retrieved_memory_ids": retrieved_backend_ids,  # Use backend IDs
                    "response_text": response,
                }

                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        f"{self.cortex_client}/api/v1/transactions",
                        json=transaction_data,
                        timeout=30.0,
                    )
                    resp.raise_for_status()
                    result = resp.json()

                # Extract transaction ID
                if "transaction" in result:
                    transaction_id = result["transaction"]["id"]
                else:
                    transaction_id = result.get("transaction_id")

                # Attribution scores should be in the response (with backend IDs)
                if "scores" in result:
                    # Map backend IDs back to test IDs for comparison with ground truth
                    backend_to_test = {v: k for k, v in self.memory_id_map.items()}
                    cortex_attribution = {}
                    for score in result["scores"]:
                        backend_id = score["memory_id"]
                        test_id = backend_to_test.get(backend_id, backend_id)
                        cortex_attribution[test_id] = score["score"]

            except Exception as e:
                print(f"Warning: Failed to report to CortexOS: {e}")
                # Don't fail the test, just continue without attribution

        # Step 4: Return result
        return SimulationResult(
            query=query,
            retrieved_memories=retrieved_memories,
            response=response,
            ground_truth_sources=sources,
            ground_truth_weights=weights,
            cortex_attribution=cortex_attribution,
            cortex_transaction_id=transaction_id,
        )


async def setup_test_environment(
    base_url: str,
    dataset_memories: list[tuple[str, str]],  # (id, content)
    agent_id: str | None = None,
    timeout: float = 5.0,
) -> dict:
    """Set up test environment by creating agent and seeding memories.

    Args:
        base_url: CortexOS backend URL (e.g., "http://localhost:8000")
        dataset_memories: List of (memory_id, content) tuples to seed
        agent_id: Optional agent ID (generates one if not provided)
        timeout: Health check timeout in seconds

    Returns:
        Dict with agent_id and memory_ids

    Raises:
        RuntimeError: If backend is not available
    """
    # Step 1: Check if backend is running
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{base_url}/healthz", timeout=timeout)
            resp.raise_for_status()
    except Exception as e:
        raise RuntimeError(
            f"CortexOS backend not available at {base_url}/healthz: {e}\n"
            f"Start the backend with: uvicorn cortex.api.app:app --port 8000"
        )

    # Step 2: Use test agent (created implicitly when first memory is added)
    if agent_id is None:
        agent_id = f"test_agent_{uuid.uuid4().hex[:8]}"

    print(f"✓ Using agent: {agent_id}")

    # Step 3: Seed dataset memories via API
    # Note: Backend auto-generates memory IDs, so we track the mapping
    memory_id_map = {}  # test_id -> backend_id
    backend_memory_ids = []

    print(f"Seeding {len(dataset_memories)} memories...")

    async with httpx.AsyncClient() as client:
        for test_mem_id, content in dataset_memories:
            memory_data = {
                "agent_id": agent_id,
                "content": content,
            }

            try:
                resp = await client.post(
                    f"{base_url}/api/v1/memories",
                    json=memory_data,
                    timeout=10.0,
                )
                resp.raise_for_status()
                result = resp.json()

                # Extract backend-generated ID
                backend_mem_id = result.get("id")
                if backend_mem_id:
                    memory_id_map[test_mem_id] = backend_mem_id
                    backend_memory_ids.append(backend_mem_id)

                if len(backend_memory_ids) % 50 == 0:
                    print(f"  Seeded {len(backend_memory_ids)}/{len(dataset_memories)} memories...")

            except Exception as e:
                print(f"Warning: Failed to create memory: {e}")
                continue

    print(f"✓ Seeded {len(backend_memory_ids)} memories")

    return {
        "agent_id": agent_id,
        "memory_ids": backend_memory_ids,
        "memory_id_map": memory_id_map,  # For mapping test IDs to backend IDs
        "base_url": base_url,
    }


async def teardown_test_environment(
    base_url: str,
    agent_id: str,
    memory_ids: list[str],
) -> None:
    """Clean up test data after the run.

    Args:
        base_url: CortexOS backend URL
        agent_id: Agent ID to clean up
        memory_ids: Memory IDs to delete
    """
    print(f"\nCleaning up test environment...")

    async with httpx.AsyncClient() as client:
        # Delete memories (soft delete)
        deleted_count = 0
        for mem_id in memory_ids:
            try:
                resp = await client.delete(
                    f"{base_url}/api/v1/memories/{mem_id}",
                    params={"agent_id": agent_id},
                    timeout=10.0,
                )
                if resp.status_code in [200, 204, 404]:  # 404 = already deleted
                    deleted_count += 1
            except Exception:
                continue

        print(f"✓ Deleted {deleted_count}/{len(memory_ids)} memories")

        # Note: We don't delete the agent itself - it's fine to leave test agents
        # in the system. They don't cost anything without active transactions.

    print(f"✓ Cleanup complete")


# Helper functions for embedding
def simple_embed(text: str, dim: int = 384) -> np.ndarray:
    """Simple deterministic embedding for testing (no real model needed).

    Uses a hash-based approach to create consistent embeddings.
    Not semantically meaningful, but consistent and deterministic.
    """
    # Hash the text to get a seed
    import hashlib
    h = hashlib.md5(text.encode()).digest()
    seed = int.from_bytes(h[:4], 'big')

    # Generate deterministic random vector
    rng = np.random.default_rng(seed)
    embedding = rng.standard_normal(dim)

    # Normalize
    embedding = embedding / (np.linalg.norm(embedding) + 1e-8)

    return embedding.astype(np.float32)


def create_test_simulator(
    memory_contents: list[str],
    memory_ids: list[str] | None = None,
    k: int = 5,
    cortex_base_url: str | None = None,
    memory_id_map: dict[str, str] | None = None,
) -> AgentSimulator:
    """Create a test agent simulator with simple embeddings.

    Args:
        memory_contents: List of memory content strings
        memory_ids: Optional list of memory IDs (generated if not provided)
        k: Number of memories to retrieve
        cortex_base_url: Optional CortexOS backend URL (e.g., "http://localhost:8000")
                        If provided, will report to real backend
        memory_id_map: Mapping from test memory IDs to backend memory IDs

    Returns:
        AgentSimulator ready for testing
    """
    if memory_ids is None:
        memory_ids = [f"mem_{i}" for i in range(len(memory_contents))]

    # Create memories
    memories = list(zip(memory_ids, memory_contents))

    # Pre-compute embeddings
    embeddings = np.array([simple_embed(content) for content in memory_contents])

    # Create simulator
    return AgentSimulator(
        memories=memories,
        memory_embeddings=embeddings,
        embed_fn=simple_embed,
        cortex_client=cortex_base_url,  # None = no backend, URL = use real backend
        llm=MockLLM(),
        k=k,
        memory_id_map=memory_id_map or {},
    )


if __name__ == "__main__":
    # Test the simulator
    import asyncio

    # Create test memories
    test_memories = [
        "I prefer Python over JavaScript for backend development",
        "My dog's name is Max and he's a golden retriever",
        "Always format Python code with black before committing",
        "Last team meeting was on Monday about Q4 roadmap planning",
        "I work at Anthropic as a research engineer",
    ]

    # Create simulator
    simulator = create_test_simulator(test_memories, k=3)

    # Test query
    async def test():
        query = "What programming language do I prefer?"

        result = await simulator.process_query(query)

        print(f"Query: {result.query}")
        print(f"\nRetrieved {len(result.retrieved_memories)} memories:")
        for mem in result.retrieved_memories:
            print(f"  [{mem.id}] (sim={mem.similarity:.3f}): {mem.content[:60]}...")

        print(f"\nResponse: {result.response}")

        print(f"\nGround Truth Sources: {result.ground_truth_sources}")
        print(f"Ground Truth Weights: {result.ground_truth_weights}")

        # Verify ground truth tracking works
        assert len(result.ground_truth_sources) > 0, "Should have at least one source"
        assert abs(sum(result.ground_truth_weights.values()) - 1.0) < 0.01, "Weights should sum to 1"

        print("\n✓ Simulator test passed!")

    asyncio.run(test())
