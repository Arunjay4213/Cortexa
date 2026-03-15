import re
import time

from app.config import Settings
from app.models.check import CheckRequest, CheckResponse, Claim, ClaimVerdict
from app.services.attributor import AttributionService
from app.services.decomposer import decompose
from app.services.nli import NLIService, check_nli
from app.services.numerical import check_numerical


def check_fuzzy_containment(claim: str, sources: list[str]) -> tuple[bool, str | None]:
    """
    Check if a claim is a near-verbatim restatement of source text.
    Normalizes whitespace and punctuation for comparison.
    Returns (grounded, best_source_sentence).
    """
    # Normalize: lowercase, collapse whitespace, strip punctuation at edges
    def normalize(text: str) -> str:
        text = text.lower().strip().rstrip(".")
        text = re.sub(r"\s+", " ", text)
        return text

    claim_norm = normalize(claim)
    if len(claim_norm) < 15:  # too short to match reliably
        return False, None

    for source in sources:
        # Split source into sentences
        sentences = re.split(r"[.!?]+", source)
        for sentence in sentences:
            sent_norm = normalize(sentence)
            if len(sent_norm) < 10:
                continue
            # Check if claim is contained in source sentence (or vice versa)
            if claim_norm in sent_norm or sent_norm in claim_norm:
                return True, sentence.strip()
    return False, None


def is_opinion(text: str) -> bool:
    """Simple heuristic for opinion detection."""
    opinion_markers = [
        "i think",
        "i believe",
        "probably",
        "maybe",
        "in my opinion",
        "it seems",
        "arguably",
        "best",
        "worst",
        "great",
        "terrible",
        "should",
        "recommend",
        "suggest",
    ]
    text_lower = text.lower()
    return any(marker in text_lower for marker in opinion_markers)


async def _run_attribution(
    claim_text: str,
    sources: list[str],
    attributor: AttributionService,
    threshold: float,
    max_sources: int,
) -> tuple[list[dict] | None, int | None, int]:
    """
    Run leave-one-out Shapley attribution on a single claim.

    Returns:
        (attribution_data, primary_source_index, nli_call_count)
    """
    capped_sources = sources[:max_sources]
    attr_result = await attributor.compute(claim_text, capped_sources)

    attribution_data = [
        {
            "source_index": inf.source_index,
            "influence": inf.influence_norm,
            "influence_raw": inf.influence_raw,
            "direction": inf.direction,
            "source_preview": inf.source_preview,
            "is_primary": inf.is_primary,
        }
        for inf in attr_result.influences
        if abs(inf.influence_norm) >= threshold
    ]

    return (
        attribution_data if attribution_data else None,
        attr_result.primary_source_index,
        attr_result.computation_calls,
    )


async def run_check(
    request: CheckRequest,
    nli_service: NLIService,
    settings: Settings,
    attributor: AttributionService | None = None,
) -> CheckResponse:
    start = time.time()

    # Resolve config
    config = request.config
    do_attribution = (
        config is not None
        and config.attribution
        and attributor is not None
    )
    attr_threshold = config.attribution_threshold if config else 0.05
    attr_max_sources = config.max_attribution_sources if config else 10

    # 1. Decompose response into claims
    raw_claims = await decompose(
        request.response,
        settings.groq_api_key,
        settings.groq_model,
        max_claims=settings.max_claims,
    )

    combined_sources = "\n\n".join(request.sources)
    claims: list[Claim] = []
    grounded_count = 0
    hallucinated_count = 0
    opinion_count = 0
    total_attribution_calls = 0
    attribution_start = None

    for claim_text in raw_claims:
        # 2. Opinion filter
        if is_opinion(claim_text):
            claims.append(
                Claim(
                    text=claim_text,
                    grounded=True,
                    verdict=ClaimVerdict.OPINION,
                    reason="Subjective claim, not verifiable",
                )
            )
            opinion_count += 1
            continue

        # 3. Numerical gate
        num_passed, num_reason = check_numerical(claim_text, combined_sources)
        if not num_passed:
            # Attribution on NUM_MISMATCH claims (find contradicting source)
            attr_data = None
            attr_primary = None
            if do_attribution:
                if attribution_start is None:
                    attribution_start = time.time()
                attr_data, attr_primary, calls = await _run_attribution(
                    claim_text, request.sources, attributor,
                    attr_threshold, attr_max_sources,
                )
                total_attribution_calls += calls

            claims.append(
                Claim(
                    text=claim_text,
                    grounded=False,
                    verdict=ClaimVerdict.NUM_MISMATCH,
                    reason=num_reason,
                    attribution=attr_data,
                    primary_source_index=attr_primary,
                )
            )
            hallucinated_count += 1
            continue

        # 3.5. Fuzzy containment gate (catches verbatim restatements)
        fuzzy_match, fuzzy_source = check_fuzzy_containment(
            claim_text, request.sources
        )
        if fuzzy_match:
            claims.append(
                Claim(
                    text=claim_text,
                    grounded=True,
                    verdict=ClaimVerdict.GROUNDED,
                    source_quote=fuzzy_source,
                    confidence=1.0,
                )
            )
            grounded_count += 1
            continue

        # 4. NLI gate
        nli_grounded, nli_conf, best_sentence = await check_nli(
            claim_text,
            request.sources,
            nli_service,
            settings.nli_entailment_threshold,
        )

        if not nli_grounded:
            # Attribution on UNSUPPORTED claims (find contradicting source)
            attr_data = None
            attr_primary = None
            if do_attribution:
                if attribution_start is None:
                    attribution_start = time.time()
                attr_data, attr_primary, calls = await _run_attribution(
                    claim_text, request.sources, attributor,
                    attr_threshold, attr_max_sources,
                )
                total_attribution_calls += calls

            claims.append(
                Claim(
                    text=claim_text,
                    grounded=False,
                    verdict=ClaimVerdict.UNSUPPORTED,
                    reason=f"No source sentence entails this claim (best: {nli_conf:.2f})",
                    confidence=nli_conf,
                    attribution=attr_data,
                    primary_source_index=attr_primary,
                )
            )
            hallucinated_count += 1
            continue

        # 5. Grounded — run attribution if enabled
        attr_data = None
        attr_primary = None
        if do_attribution:
            if attribution_start is None:
                attribution_start = time.time()
            attr_data, attr_primary, calls = _run_attribution(
                claim_text, request.sources, attributor,
                attr_threshold, attr_max_sources,
            )
            total_attribution_calls += calls

        claims.append(
            Claim(
                text=claim_text,
                grounded=True,
                verdict=ClaimVerdict.GROUNDED,
                source_quote=best_sentence,
                confidence=nli_conf,
                attribution=attr_data,
                primary_source_index=attr_primary,
            )
        )
        grounded_count += 1

    # Calculate hallucination index
    verifiable = grounded_count + hallucinated_count
    hallucination_index = hallucinated_count / verifiable if verifiable > 0 else 0.0

    # Attribution timing
    attribution_latency = None
    if attribution_start is not None:
        attribution_latency = round((time.time() - attribution_start) * 1000, 1)

    return CheckResponse(
        hallucination_index=round(hallucination_index, 4),
        total_claims=len(claims),
        grounded_count=grounded_count,
        hallucinated_count=hallucinated_count,
        opinion_count=opinion_count,
        claims=claims,
        latency_ms=round((time.time() - start) * 1000, 1),
        attribution_calls=total_attribution_calls if do_attribution else None,
        attribution_latency_ms=attribution_latency,
    )
