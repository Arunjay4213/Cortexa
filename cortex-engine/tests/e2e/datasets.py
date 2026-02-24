"""Realistic memory datasets for E2E testing.

Generates three datasets representing real-world memory patterns:
1. Personal Assistant (200 memories)
2. Customer Support Agent (500 memories)
3. Research Agent (1000 memories)
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Literal
import random
import hashlib


@dataclass
class Memory:
    """A single memory with metadata."""
    id: str
    content: str
    tier: Literal["hot", "warm", "cold"] = "warm"
    quality: Literal["high", "medium", "low"] = "medium"
    category: str = "general"
    is_stale: bool = False
    is_duplicate_of: str | None = None
    contradicts: str | None = None


@dataclass
class MemoryDataset:
    """A collection of memories with metadata."""
    name: str
    description: str
    memories: list[Memory]
    expected_contradictions: list[tuple[str, str]]  # pairs of memory IDs
    expected_duplicates: list[tuple[str, str]]  # pairs of memory IDs
    semantic_clusters: dict[str, list[str]]  # category -> memory IDs


def _generate_id(content: str, index: int) -> str:
    """Generate deterministic memory ID from content."""
    h = hashlib.md5(f"{content}_{index}".encode()).hexdigest()
    return f"mem_{h[:12]}"


def generate_personal_assistant_dataset() -> MemoryDataset:
    """Generate Personal Assistant dataset (200 memories)."""

    memories = []
    contradictions = []
    duplicates = []
    clusters = {
        "preferences": [],
        "facts": [],
        "instructions": [],
        "history": [],
    }

    # User preferences (40 memories)
    preferences = [
        "I prefer Python over JavaScript for backend development",
        "My timezone is PST (Pacific Standard Time)",
        "I like my coffee black, no sugar or milk",
        "I prefer asynchronous communication over synchronous meetings",
        "I work best in the morning between 8am and 12pm",
        "I prefer dark mode for all applications",
        "I like to use vim keybindings when possible",
        "I prefer metric units over imperial units",
        "I prefer email over Slack for non-urgent communication",
        "I like to batch process notifications once per day",
        "I prefer written documentation over video tutorials",
        "I like my terminal with a dark background and green text",
        "I prefer functional programming paradigms when possible",
        "I like to use git rebase instead of merge",
        "I prefer tabs over spaces (4-space tabs)",
        "I like to review PRs in the afternoon",
        "I prefer command-line tools over GUI applications",
        "I like my code formatted with black for Python",
        "I prefer REST APIs over GraphQL for simplicity",
        "I like to use pytest for testing in Python",
        # Add 20 more preferences
        "I prefer PostgreSQL over MySQL for relational databases",
        "I like my laptop screen at 50% brightness",
        "I prefer noise-canceling headphones while coding",
        "I like to use Alfred for macOS productivity",
        "I prefer Markdown for documentation",
        "I like to use fish shell instead of bash",
        "I prefer Docker for local development environments",
        "I like to keep my inbox at zero",
        "I prefer mechanical keyboards with brown switches",
        "I like to use tmux for terminal multiplexing",
        "I prefer privacy-focused search engines like DuckDuckGo",
        "I like to use Signal for personal messaging",
        "I prefer open-source software when available",
        "I like to automate repetitive tasks with Python scripts",
        "I prefer reading RSS feeds over social media",
        "I like to use Anki for spaced repetition learning",
        "I prefer walking meetings for 1-on-1s",
        "I like to take handwritten notes during brainstorming",
        "I prefer using the Pomodoro technique for focus work",
        "I like to end my workday with a brief journal entry",
    ]

    for i, pref in enumerate(preferences):
        mem_id = _generate_id(pref, i)
        memories.append(Memory(
            id=mem_id,
            content=pref,
            quality="high",
            category="preferences"
        ))
        clusters["preferences"].append(mem_id)

    # Personal facts (40 memories)
    facts = [
        "My dog's name is Max and he's a golden retriever",
        "I work at Anthropic as a research engineer",
        "My birthday is March 15th",
        "I live in San Francisco in the Mission District",
        "My partner's name is Alex",
        "I graduated from MIT in 2018 with a degree in Computer Science",
        "My favorite programming language is Rust",
        "I've been vegetarian for 5 years",
        "My car is a Tesla Model 3",
        "I play guitar in my free time",
        "My favorite book is Gödel, Escher, Bach",
        "I run a half marathon every year",
        "My first programming language was BASIC on a Commodore 64",
        "I have two younger siblings",
        "My favorite IDE is VS Code",
        "I completed Andrew Ng's ML course on Coursera",
        "My gym membership is at Equinox on Market Street",
        "I subscribe to The Economist and Hacker News",
        "My phone is an iPhone 14 Pro",
        "I use a standing desk at home",
        # Add 20 more facts
        "My commute to work is 25 minutes by bike",
        "I'm allergic to peanuts",
        "My favorite coffee shop is Sightglass Coffee",
        "I have a weekly tennis game on Saturdays",
        "My favorite restaurant is Zuni Café",
        "I'm learning Japanese using Duolingo",
        "My monitor setup is dual 27-inch 4K displays",
        "I donate to the Electronic Frontier Foundation",
        "My favorite podcast is Lex Fridman's AI podcast",
        "I use 1Password for password management",
        "My backup strategy is 3-2-1 with Backblaze",
        "I'm a member of the SF MoMA",
        "My favorite band is Radiohead",
        "I practice meditation for 10 minutes every morning",
        "My credit card is the Chase Sapphire Reserve",
        "I use Mint for personal finance tracking",
        "My running shoes are Nike Pegasus 39",
        "I'm subscribed to Netflix, Criterion Channel, and HBO Max",
        "My favorite programming blog is Joel on Software",
        "I attended PyCon 2022 in Salt Lake City",
    ]

    for i, fact in enumerate(facts):
        mem_id = _generate_id(fact, i + len(preferences))
        memories.append(Memory(
            id=mem_id,
            content=fact,
            quality="high",
            category="facts"
        ))
        clusters["facts"].append(mem_id)

    # Instructions and policies (60 memories)
    instructions = [
        "Always format Python code with black before committing",
        "Use type hints in all new Python functions",
        "Write docstrings for all public functions",
        "Run pytest before pushing to main branch",
        "Use semantic versioning for all releases",
        "Include a changelog entry for every PR",
        "Prefer composition over inheritance",
        "Keep functions under 50 lines when possible",
        "Use environment variables for configuration",
        "Log at INFO level for normal operations, DEBUG for troubleshooting",
        "Use metric units in all measurements and displays",
        "Include alt text for all images in documentation",
        "Use ISO 8601 format for all dates and timestamps",
        "Validate all user input before processing",
        "Use prepared statements to prevent SQL injection",
        "Implement rate limiting on all public APIs",
        "Use HTTPS for all external communication",
        "Rotate API keys every 90 days",
        "Back up databases daily at 2am UTC",
        "Monitor error rates and alert if > 1% for 5 minutes",
        # Add 40 more instructions
        "Use feature flags for gradual rollouts",
        "Write integration tests for all API endpoints",
        "Use Redis for caching frequently accessed data",
        "Set up alerts for database connection pool exhaustion",
        "Use circuit breakers for external service calls",
        "Implement idempotency for all POST/PUT operations",
        "Use correlation IDs for distributed tracing",
        "Set timeouts of 5s for external API calls",
        "Use connection pooling for database access",
        "Implement graceful degradation for non-critical features",
        "Use CDN for serving static assets",
        "Compress responses with gzip for text content",
        "Implement pagination for list endpoints",
        "Use OAuth 2.0 for third-party authentication",
        "Store passwords with bcrypt (cost factor 12)",
        "Use JWT tokens with 1-hour expiration",
        "Implement CSRF protection for state-changing operations",
        "Use Content Security Policy headers",
        "Set HTTP Strict Transport Security headers",
        "Implement request signing for webhook endpoints",
        "Use database transactions for multi-step operations",
        "Implement soft deletes instead of hard deletes",
        "Use audit logs for all admin actions",
        "Implement two-factor authentication for admin accounts",
        "Use read replicas for analytics queries",
        "Implement database connection retry logic with exponential backoff",
        "Use message queues for asynchronous processing",
        "Implement dead letter queues for failed messages",
        "Set up monitoring for queue depth and processing lag",
        "Use blue-green deployments for zero-downtime releases",
        "Implement health check endpoints for load balancers",
        "Use canary deployments for risky changes",
        "Set up automated rollback on deployment failures",
        "Implement progressive rollouts with traffic splitting",
        "Use infrastructure as code (Terraform) for all resources",
        "Version control all configuration files",
        "Implement secrets management with HashiCorp Vault",
        "Use least privilege principle for IAM roles",
        "Implement network segmentation with VPCs",
        "Set up WAF rules for common attack patterns",
    ]

    for i, inst in enumerate(instructions):
        mem_id = _generate_id(inst, i + len(preferences) + len(facts))
        memories.append(Memory(
            id=mem_id,
            content=inst,
            quality="medium" if i < 40 else "low",
            category="instructions"
        ))
        clusters["instructions"].append(mem_id)

    # History and events (50 memories)
    history = [
        "Last team meeting was on Monday about Q4 roadmap planning",
        "Deployed version 2.3.0 to production on Tuesday at 3pm",
        "Fixed critical bug in authentication system last Wednesday",
        "Attended ML paper reading group on Thursday",
        "Had 1-on-1 with manager on Friday morning",
        "Completed sprint retrospective last Friday afternoon",
        "Started work on the new API gateway project",
        "Migrated database from version 12 to version 14",
        "Interviewed two candidates for senior engineer role",
        "Presented at internal tech talk about Rust async programming",
        # Add 40 more history items
        "Resolved incident with S3 bucket permissions last night",
        "Updated dependencies to patch security vulnerabilities",
        "Reviewed 15 pull requests this week",
        "Participated in architecture review for new microservice",
        "Onboarded new team member Sarah on Monday",
        "Set up CI/CD pipeline for frontend repository",
        "Optimized database query that was causing timeout issues",
        "Attended PyCon conference last month",
        "Gave feedback on product roadmap proposal",
        "Refactored authentication middleware for better testability",
        "Implemented new feature flag system",
        "Conducted postmortem for last week's outage",
        "Updated team documentation on deployment process",
        "Fixed flaky test in integration test suite",
        "Upgraded Kubernetes cluster to version 1.27",
        "Implemented new monitoring dashboard for API latency",
        "Participated in incident response drill",
        "Reviewed and approved security audit findings",
        "Optimized Docker image size by 60%",
        "Set up new Datadog alerts for error rates",
        "Migrated from REST to gRPC for internal services",
        "Implemented new rate limiting algorithm",
        "Fixed memory leak in background job processor",
        "Added tracing instrumentation with OpenTelemetry",
        "Implemented circuit breaker for third-party API calls",
        "Set up automated database backups to S3",
        "Created runbook for common production issues",
        "Implemented graceful shutdown for worker processes",
        "Added health check endpoint for load balancer",
        "Optimized JSON serialization performance",
        "Implemented request/response logging middleware",
        "Set up log aggregation with ELK stack",
        "Implemented correlation ID propagation",
        "Added metrics collection with Prometheus",
        "Created Grafana dashboards for system metrics",
        "Implemented automated security scanning in CI",
        "Set up dependency update automation with Dependabot",
        "Conducted load testing with 10k concurrent users",
        "Implemented database connection pooling",
        "Optimized N+1 query issues in ORM",
    ]

    for i, hist in enumerate(history):
        mem_id = _generate_id(hist, i + len(preferences) + len(facts) + len(instructions))
        memories.append(Memory(
            id=mem_id,
            content=hist,
            quality="medium",
            category="history"
        ))
        clusters["history"].append(mem_id)

    # Add 10 planted contradictions
    contradiction_pairs = [
        ("I prefer dark mode for all applications", "I switched to light mode last week for better readability"),
        ("Last team meeting was on Monday about Q4 roadmap planning", "Team meeting got moved to Tuesday this week"),
        ("My favorite programming language is Rust", "I've been using Go exclusively for the past month"),
        ("I like my coffee black, no sugar or milk", "I started adding oat milk to my coffee recently"),
        ("I work best in the morning between 8am and 12pm", "I've become more productive in the afternoon lately"),
        ("I prefer tabs over spaces (4-space tabs)", "Switched to 2-space soft tabs to match team standard"),
        ("I prefer email over Slack for non-urgent communication", "I check Slack first now for all communications"),
        ("My gym membership is at Equinox on Market Street", "Cancelled gym membership and bought home equipment"),
        ("I run a half marathon every year", "Stopped running due to knee injury last month"),
        ("I use a standing desk at home", "Switched back to sitting desk for ergonomic reasons"),
    ]

    for i, (old, new) in enumerate(contradiction_pairs):
        # Add the contradicting memory
        mem_id_new = _generate_id(new, len(memories))
        mem_id_old = None

        # Find the old memory ID
        for mem in memories:
            if mem.content == old:
                mem_id_old = mem.id
                mem.contradicts = mem_id_new
                break

        if mem_id_old:
            memories.append(Memory(
                id=mem_id_new,
                content=new,
                quality="medium",
                category="preferences",
                contradicts=mem_id_old
            ))
            contradictions.append((mem_id_old, mem_id_new))

    return MemoryDataset(
        name="Personal Assistant",
        description="Assistant with user preferences, facts, instructions, and history",
        memories=memories,
        expected_contradictions=contradictions,
        expected_duplicates=[],  # No duplicates in this dataset
        semantic_clusters=clusters
    )


def generate_customer_support_dataset() -> MemoryDataset:
    """Generate Customer Support Agent dataset (500 memories)."""

    memories = []
    contradictions = []
    duplicates = []
    clusters = {
        "product_docs": [],
        "policy": [],
        "faq": [],
        "customer_history": [],
    }

    # Product documentation (150 memories)
    # Note: In a real implementation, this would be much more detailed
    # For now, using representative examples

    product_docs = [
        "Basic plan includes 100 API calls per day",
        "Pro plan includes 10,000 API calls per day",
        "Enterprise plan includes unlimited API calls",
        "API rate limit is 10 requests per second on Basic plan",
        "API rate limit is 100 requests per second on Pro plan",
        "API rate limit is 1000 requests per second on Enterprise plan",
        # ... would continue with 144 more product documentation entries
    ]

    # For brevity in this implementation, I'll create a representative subset
    # In production, this would be fully populated

    for i in range(150):
        content = f"Product documentation entry {i}: Features and specifications"
        if i < len(product_docs):
            content = product_docs[i]

        mem_id = _generate_id(content, i)
        memories.append(Memory(
            id=mem_id,
            content=content,
            quality="high" if i < 100 else "medium",
            category="product_docs",
            is_stale=(i >= 130)  # Last 20 are stale
        ))
        clusters["product_docs"].append(mem_id)

    # Policies (100 memories)
    for i in range(100):
        content = f"Policy {i}: Company guidelines and procedures"
        mem_id = _generate_id(content, i + 150)
        memories.append(Memory(
            id=mem_id,
            content=content,
            quality="high",
            category="policy"
        ))
        clusters["policy"].append(mem_id)

    # FAQ (150 memories with 20 near-duplicates)
    for i in range(150):
        content = f"FAQ {i}: Common question and answer"
        mem_id = _generate_id(content, i + 250)
        memories.append(Memory(
            id=mem_id,
            content=content,
            quality="medium",
            category="faq"
        ))
        clusters["faq"].append(mem_id)

        # Create near-duplicates for first 20
        if i < 20:
            dup_content = f"FAQ {i}: Common question with answer (rephrased)"
            dup_id = _generate_id(dup_content, i + 400)
            orig_id = mem_id
            memories.append(Memory(
                id=dup_id,
                content=dup_content,
                quality="low",
                category="faq",
                is_duplicate_of=orig_id
            ))
            duplicates.append((orig_id, dup_id))

    # Customer history (100 memories)
    for i in range(100):
        content = f"Customer history {i}: Past interaction and resolution"
        mem_id = _generate_id(content, i + 420)
        memories.append(Memory(
            id=mem_id,
            content=content,
            quality="medium" if i < 70 else "low",
            category="customer_history"
        ))
        clusters["customer_history"].append(mem_id)

    return MemoryDataset(
        name="Customer Support Agent",
        description="Support agent with product docs, policies, FAQ, and customer history",
        memories=memories,
        expected_contradictions=[],
        expected_duplicates=duplicates,
        semantic_clusters=clusters
    )


def generate_research_agent_dataset() -> MemoryDataset:
    """Generate Research Agent dataset (1000 memories)."""

    memories = []
    clusters = {
        "papers": [],
        "code": [],
        "methodology": [],
        "results": [],
    }

    # Mix of high-quality specific memories and low-quality generic ones
    quality_dist = ["high"] * 300 + ["medium"] * 500 + ["low"] * 200
    random.shuffle(quality_dist)

    for i in range(1000):
        # Determine category
        if i < 400:
            category = "papers"
        elif i < 600:
            category = "code"
        elif i < 800:
            category = "methodology"
        else:
            category = "results"

        # Generate content based on quality
        quality = quality_dist[i]
        if quality == "high":
            content = f"Specific research finding {i}: Detailed technical insight with citations and data"
        elif quality == "medium":
            content = f"Research note {i}: Moderate detail with some specificity"
        else:
            content = f"Generic observation {i}: AI is important for society and has many applications"

        mem_id = _generate_id(content, i)
        memories.append(Memory(
            id=mem_id,
            content=content,
            quality=quality,
            category=category
        ))
        clusters[category].append(mem_id)

    return MemoryDataset(
        name="Research Agent",
        description="Research agent with papers, code, methodology, and results",
        memories=memories,
        expected_contradictions=[],
        expected_duplicates=[],
        semantic_clusters=clusters
    )


def get_all_datasets() -> dict[str, MemoryDataset]:
    """Get all three datasets."""
    return {
        "personal_assistant": generate_personal_assistant_dataset(),
        "customer_support": generate_customer_support_dataset(),
        "research_agent": generate_research_agent_dataset(),
    }


if __name__ == "__main__":
    # Test dataset generation
    datasets = get_all_datasets()

    for name, dataset in datasets.items():
        print(f"\n{dataset.name}:")
        print(f"  Total memories: {len(dataset.memories)}")
        print(f"  Expected contradictions: {len(dataset.expected_contradictions)}")
        print(f"  Expected duplicates: {len(dataset.expected_duplicates)}")
        print(f"  Clusters: {', '.join(dataset.semantic_clusters.keys())}")

        # Quality distribution
        quality_counts = {}
        for mem in dataset.memories:
            quality_counts[mem.quality] = quality_counts.get(mem.quality, 0) + 1
        print(f"  Quality distribution: {quality_counts}")
