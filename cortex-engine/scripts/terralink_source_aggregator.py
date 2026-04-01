"""
TerraLink Source Aggregator
═══════════════════════════
Calls TerraLink's SSE endpoints, captures intermediate agent outputs
as raw source strings, returns both final packet and ground-truth sources.

Usage:
    from scripts.terralink_source_aggregator import run_terralink_query
    packet, sources, metadata = await run_terralink_query("50-acre solar site in Texas Panhandle")
"""

import json
import time

import httpx

TERRALINK_BASE = "http://localhost:5001"
SSE_TIMEOUT = 90.0  # max seconds to wait for SSE stream


def _parse_sse_events(raw: str) -> list[dict]:
    """Parse raw SSE text into a list of event dicts."""
    events = []
    for line in raw.split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            try:
                payload = json.loads(line[6:])
                # Payload is {"type": ..., "data": ..., "ts": ...}
                events.append(payload)
            except json.JSONDecodeError:
                continue
    return events


def _flatten_packet_to_text(packet: dict) -> str:
    """Convert a TerraLink packet into a readable response string."""
    lines = []

    site = packet.get("site", {})
    if site:
        lines.append(
            f"Site: {site.get('name', 'Unknown')} in {site.get('county', '?')} County, "
            f"{site.get('state', '?')}. Satellite score: {site.get('satellite_score', '?')}. "
            f"Solar irradiance: {site.get('solar_irradiance', '?')} kWh/m2/day. "
            f"Slope: {site.get('slope', '?')} degrees. "
            f"Land cover: {site.get('land_cover', '?')}."
        )

    land = packet.get("land", {})
    if land:
        lines.append(
            f"Land: Owner {land.get('owner_name', '?')}, "
            f"parcel {land.get('parcel_id', '?')}, "
            f"{land.get('acreage', '?')} acres, "
            f"last sale {land.get('last_sale_price', '?')}, "
            f"zoning {land.get('zoning', '?')}."
        )

    yf = packet.get("yield_forecast", {})
    if yf:
        lines.append(
            f"Yield: P50 {yf.get('p50_mwh_yr', '?')} MWh/yr, "
            f"P90 {yf.get('p90_mwh_yr', '?')} MWh/yr, "
            f"variance {yf.get('variance_pct', '?')}%, "
            f"capacity factor P50 {yf.get('capacity_factor_p50', '?')}, "
            f"degradation {yf.get('degradation_rate_pct', '?')}%/yr."
        )

    grid = packet.get("grid", {})
    if grid:
        lines.append(
            f"Grid: Nearest substation {grid.get('substation_name', '?')} at "
            f"{grid.get('distance_mi', '?')}, {grid.get('voltage_kv', '?')}kV, "
            f"interconnection cost {grid.get('cost_range', '?')}, "
            f"queue region {grid.get('queue_region', '?')}."
        )

    perm = packet.get("permitting", {})
    if perm:
        lines.append(
            f"Permitting: Zoning {perm.get('zoning_class', '?')}, "
            f"CUP {'required' if perm.get('cup_required') else 'not required'}, "
            f"setback {perm.get('setback_ft', '?')}ft, "
            f"risk level {perm.get('risk_level', '?')}, "
            f"timeline {perm.get('estimated_permit_timeline', perm.get('cup_timeline', '?'))}."
        )

    fin = packet.get("financials", {})
    if fin:
        lines.append(
            f"Financials: Project size {fin.get('project_size_mw', '?')}, "
            f"capex {fin.get('capex', '?')}, "
            f"annual opex {fin.get('annual_opex', '?')}, "
            f"P50 IRR {fin.get('p50_irr', '?')}, P90 IRR {fin.get('p90_irr', '?')}, "
            f"IRA credit {fin.get('ira_credit', '?')}, "
            f"P50 revenue {fin.get('p50_revenue', '?')}, "
            f"NPV {fin.get('npv', '?')}, payback {fin.get('payback_year', '?')}."
        )

    comm = packet.get("community", {})
    if comm:
        lines.append(
            f"Community: Score {comm.get('score', '?')}, "
            f"IRA energy community: {'yes' if comm.get('ira_community') else 'no'}, "
            f"rating {comm.get('rating', '?')}."
        )

    return " ".join(lines)


def _extract_sources_from_packet(packet: dict) -> list[str]:
    """
    Extract agent data from the packet as natural language source strings.
    Uses natural language so the NLI model can match claims to sources.
    """
    sources = []

    # Source 1: Site satellite data (Agent 3)
    site = packet.get("site", {})
    if site:
        sources.append(
            f"The site {site.get('name', 'Unknown')} is located in "
            f"{site.get('county', '?')} County, {site.get('state', '?')}. "
            f"The satellite score is {site.get('satellite_score', '?')}. "
            f"The solar irradiance is {site.get('solar_irradiance', '?')} kWh/m2/day. "
            f"The slope is {site.get('slope', '?')} degrees. "
            f"The slope rating is {site.get('slope_rating', '?')}. "
            f"The land cover is {site.get('land_cover', '?')}. "
            f"The protected area status is {site.get('protected_area', '?')}."
        )

    # Source 2: Land intelligence (Agent 5)
    land = packet.get("land", {})
    if land:
        sources.append(
            f"The land owner is {land.get('owner_name', '?')}. "
            f"The mailing address is {land.get('mailing_address', '?')}. "
            f"The parcel ID is {land.get('parcel_id', '?')}. "
            f"The acreage is {land.get('acreage', '?')} acres. "
            f"The last sale price was {land.get('last_sale_price', '?')}. "
            f"The tax assessment is {land.get('tax_assessment', '?')}. "
            f"The land use is {land.get('land_use', '?')}. "
            f"The zoning is {land.get('zoning', '?')}."
        )

    # Source 3: Yield forecast (Agent 10)
    yf = packet.get("yield_forecast", {})
    if yf:
        sources.append(
            f"The P50 yield is {yf.get('p50_mwh_yr', '?')} MWh/yr. "
            f"The P90 yield is {yf.get('p90_mwh_yr', '?')} MWh/yr. "
            f"The variance is {yf.get('variance_pct', '?')}%. "
            f"The confidence score is {yf.get('confidence_score', '?')}. "
            f"The annual GHI is {yf.get('annual_ghi_kwh_m2', '?')} kWh/m2. "
            f"The inter-annual variability is {yf.get('inter_annual_variability', '?')}%. "
            f"The soiling loss is {yf.get('soiling_loss_pct', '?')}%. "
            f"The temperature loss is {yf.get('temperature_loss_pct', '?')}%. "
            f"The degradation rate is {yf.get('degradation_rate_pct', '?')}%/yr. "
            f"The capacity factor P50 is {yf.get('capacity_factor_p50', '?')}. "
            f"The capacity factor P90 is {yf.get('capacity_factor_p90', '?')}."
        )

    # Source 4: Grid connection (Agent 6)
    grid = packet.get("grid", {})
    if grid:
        sources.append(
            f"The nearest substation is {grid.get('substation_name', '?')}. "
            f"The distance to the nearest substation is {grid.get('distance_mi', '?')}. "
            f"The substation voltage is {grid.get('voltage_kv', '?')}kV. "
            f"The utility is {grid.get('utility', '?')}. "
            f"The interconnection cost range is {grid.get('cost_range', '?')}. "
            f"The queue region is {grid.get('queue_region', '?')}. "
            f"The queue status is {grid.get('queue_status', '?')}."
        )

    # Source 5: Permitting (Agent 9)
    perm = packet.get("permitting", {})
    if perm:
        cup = "required" if perm.get("cup_required") else "not required"
        sources.append(
            f"The zoning class is {perm.get('zoning_class', '?')}. "
            f"A Conditional Use Permit is {cup}. "
            f"The CUP timeline is {perm.get('cup_timeline', '?')}. "
            f"The setback is {perm.get('setback_ft', '?')} feet. "
            f"There is {'a' if perm.get('moratorium') else 'no'} moratorium. "
            f"The risk level is {perm.get('risk_level', '?')}. "
            f"The risk score is {perm.get('risk_score', '?')}. "
            f"The estimated permit timeline is {perm.get('estimated_permit_timeline', '?')}."
        )

    # Source 6: Financial model (Agent 7)
    fin = packet.get("financials", {})
    if fin:
        ec = "is" if fin.get("is_energy_community") else "is not"
        sources.append(
            f"The project size is {fin.get('project_size_mw', '?')}. "
            f"The capex is {fin.get('capex', '?')}. "
            f"The capex per watt is {fin.get('capex_per_w', '?')}. "
            f"The annual opex is {fin.get('annual_opex', '?')}. "
            f"The power price is {fin.get('power_price', '?')}. "
            f"The P50 revenue is {fin.get('p50_revenue', '?')}. "
            f"The P90 revenue is {fin.get('p90_revenue', '?')}. "
            f"The IRA credit is {fin.get('ira_credit', '?')}. "
            f"The IRA ITC percentage is {fin.get('ira_itc_pct', '?')}. "
            f"The site {ec} an IRA energy community. "
            f"The net capex after IRA credit is {fin.get('net_capex', '?')}. "
            f"The P50 IRR is {fin.get('p50_irr', '?')}. "
            f"The P90 IRR is {fin.get('p90_irr', '?')}. "
            f"The NPV is {fin.get('npv', '?')}. "
            f"The payback period is {fin.get('payback_year', '?')}. "
            f"The project life is {fin.get('project_life', '?')}."
        )

    # Source 7: Community
    comm = packet.get("community", {})
    if comm:
        ec2 = "is" if comm.get("ira_community") else "is not"
        sources.append(
            f"The community acceptance score is {comm.get('score', '?')}. "
            f"The site {ec2} an IRA energy community. "
            f"The income percentile is {comm.get('income_percentile', '?')}. "
            f"The employment rate is {comm.get('employment_rate', '?')}%. "
            f"The energy industry jobs percentage is {comm.get('energy_industry_jobs', '?')}%. "
            f"The community rating is {comm.get('rating', '?')}."
        )

    return sources


async def run_terralink_query(
    query: str,
    terralink_base: str = TERRALINK_BASE,
    timeout: float = SSE_TIMEOUT,
) -> tuple[dict | None, str, list[str], dict]:
    """
    Run a full TerraLink query (Phase 1 + Phase 2) and return results.

    Returns:
        (packet, response_text, sources, metadata)
        - packet: raw packet dict (or None on failure)
        - response_text: flattened text version of the packet
        - sources: list of source strings from each agent
        - metadata: timing and session info
    """
    meta = {"query": query, "started_at": time.time()}

    async with httpx.AsyncClient(timeout=timeout) as client:
        # Phase 1: Search
        try:
            r1 = await client.post(
                f"{terralink_base}/api/search",
                json={"query": query},
            )
            r1.raise_for_status()
            session_id = r1.json()["session_id"]
            meta["phase1_session_id"] = session_id
        except Exception as e:
            meta["error"] = f"Phase 1 search failed: {e}"
            return None, "", [], meta

        # Stream Phase 1 SSE
        sites = []
        params = {}
        try:
            async with client.stream(
                "GET", f"{terralink_base}/api/stream/{session_id}"
            ) as stream:
                buffer = ""
                async for chunk in stream.aiter_text():
                    buffer += chunk
                    # Process complete SSE lines
                    while "\n\n" in buffer:
                        event_block, buffer = buffer.split("\n\n", 1)
                        for line in event_block.split("\n"):
                            line = line.strip()
                            if line.startswith("data: "):
                                try:
                                    evt = json.loads(line[6:])
                                    if evt.get("type") == "phase1_complete":
                                        sites = evt.get("data", {}).get("sites", [])
                                        params = evt.get("data", {}).get("params", {})
                                    elif evt.get("type") == "agent_error":
                                        meta["phase1_error"] = evt.get("data", {}).get("fallback", "unknown")
                                except json.JSONDecodeError:
                                    continue
        except Exception as e:
            meta["error"] = f"Phase 1 SSE failed: {e}"
            return None, "", [], meta

        if not sites:
            meta["error"] = "Phase 1 returned no sites"
            return None, "", [], meta

        meta["phase1_elapsed"] = time.time() - meta["started_at"]
        meta["num_sites"] = len(sites)
        meta["top_site"] = sites[0].get("name", "?")

        # Phase 2+3: Build packet for top site
        try:
            r2 = await client.post(
                f"{terralink_base}/api/packet",
                json={"session_id": session_id, "site_index": 0},
            )
            r2.raise_for_status()
            packet_session_id = r2.json()["session_id"]
            meta["phase2_session_id"] = packet_session_id
        except Exception as e:
            meta["error"] = f"Phase 2 packet request failed: {e}"
            return None, "", [], meta

        # Stream Phase 2+3 SSE
        packet = None
        try:
            async with client.stream(
                "GET", f"{terralink_base}/api/stream/{packet_session_id}"
            ) as stream:
                buffer = ""
                async for chunk in stream.aiter_text():
                    buffer += chunk
                    while "\n\n" in buffer:
                        event_block, buffer = buffer.split("\n\n", 1)
                        for line in event_block.split("\n"):
                            line = line.strip()
                            if line.startswith("data: "):
                                try:
                                    evt = json.loads(line[6:])
                                    if evt.get("type") == "packet_complete":
                                        pdata = evt.get("data", {})
                                        packet = pdata.get("packet")
                                        meta["terralink_latency_ms"] = pdata.get("elapsed_ms", 0)
                                    elif evt.get("type") == "agent_error":
                                        meta["phase2_error"] = evt.get("data", {}).get("fallback", "unknown")
                                except json.JSONDecodeError:
                                    continue
        except Exception as e:
            meta["error"] = f"Phase 2 SSE failed: {e}"
            return None, "", [], meta

        if not packet:
            meta["error"] = "Phase 2 returned no packet"
            return None, "", [], meta

        meta["total_elapsed"] = time.time() - meta["started_at"]

    # Flatten packet to text and extract sources
    response_text = _flatten_packet_to_text(packet)
    sources = _extract_sources_from_packet(packet)

    return packet, response_text, sources, meta
