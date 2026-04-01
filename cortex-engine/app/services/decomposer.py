import json
import re

import httpx


DECOMPOSE_PROMPT = """Break this text into independent, atomic factual claims.

Rules:
- Each claim must contain exactly ONE verifiable fact or number
- Skip greetings, opinions, hedging ("I think", "probably")
- Skip meta-statements ("As mentioned", "In summary")
- Keep exact numbers, dates, names, quantities
- Each claim should be a complete sentence

Text to decompose:
{response}

Return ONLY a JSON array of strings. No explanation. No markdown.
Example: ["Claim 1", "Claim 2", "Claim 3"]"""


def _strip_think_blocks(text: str) -> str:
    """Strip <think>...</think> blocks from Qwen/reasoning models."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _extract_json_array(text: str) -> list[str]:
    """Extract a JSON array from possibly messy LLM output."""
    text = _strip_think_blocks(text)
    # Try direct parse first
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return [str(item) for item in result]
    except json.JSONDecodeError:
        pass

    # Try to find JSON array in the text
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group())
            if isinstance(result, list):
                return [str(item) for item in result]
        except json.JSONDecodeError:
            pass

    return []


async def _groq_chat(
    client: httpx.AsyncClient,
    groq_api_key: str,
    model: str,
    messages: list[dict],
    max_retries: int = 3,
) -> dict:
    """Call Groq chat API with retries for transient errors."""
    last_exc = None
    for attempt in range(max_retries):
        try:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {groq_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": 0.0,
                    "max_tokens": 4096,
                },
            )
            resp.raise_for_status()
            return resp.json()
        except (httpx.ConnectError, httpx.ReadTimeout) as e:
            last_exc = e
            import asyncio
            await asyncio.sleep(1.0 * (attempt + 1))
    raise last_exc  # type: ignore[misc]


async def decompose(
    response: str,
    groq_api_key: str,
    model: str,
    max_claims: int = 50,
) -> list[str]:
    """
    Break response into atomic factual claims using Groq.
    Each claim has exactly one verifiable assertion.
    """
    prompt = DECOMPOSE_PROMPT.format(response=response)

    async with httpx.AsyncClient(timeout=60.0) as client:
        data = await _groq_chat(
            client, groq_api_key, model,
            [{"role": "user", "content": prompt}],
        )

    content = data["choices"][0]["message"]["content"]
    claims = _extract_json_array(content)

    if not claims:
        # Retry once with a stricter prompt
        async with httpx.AsyncClient(timeout=60.0) as client:
            retry_data = await _groq_chat(
                client, groq_api_key, model,
                [
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": content},
                    {
                        "role": "user",
                        "content": "That was not valid JSON. Return ONLY a JSON array of strings like [\"claim1\", \"claim2\"]. Nothing else.",
                    },
                ],
            )

        retry_content = retry_data["choices"][0]["message"]["content"]
        claims = _extract_json_array(retry_content)

    return claims[:max_claims]
