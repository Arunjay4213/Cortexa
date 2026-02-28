import httpx


async def find_source_quote(
    claim: str,
    sources: list[str],
    groq_api_key: str,
    model: str,
) -> str | None:
    """
    Find the exact sentence in sources that supports this claim.
    Only called for claims already verified as grounded by NLI.
    """
    combined = "\n\n".join(sources)

    prompt = f"""Find the exact sentence from the SOURCE TEXT that supports the following claim.

CLAIM: {claim}

SOURCE TEXT:
{combined}

Return ONLY the exact sentence from the source. Nothing else.
If you cannot find an exact sentence, return NONE."""

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {groq_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.0,
                    "max_tokens": 512,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        content = data["choices"][0]["message"]["content"].strip()
        if content.upper() == "NONE":
            return None
        return content
    except Exception:
        return None
