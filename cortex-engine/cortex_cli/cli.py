"""CortexOS CLI — Mode B: Scriptable command-line interface.

Usage:
    python -m cortex_cli stats
    python -m cortex_cli agents
    python -m cortex_cli memories [--agent AGENT] [--limit N]
    python -m cortex_cli search QUERY [--top-k N]
    python -m cortex_cli hallucinations [--agent AGENT]
    python -m cortex_cli attribute TXN_ID
    python -m cortex_cli dead
    python -m cortex_cli export [--format json|csv]
"""

from __future__ import annotations

import argparse
import json
import sys

from cortex_cli.api import CortexAPI
from cortex_cli.config import CORTEX_API_KEY, CORTEX_URL
from cortex_cli.formatters import (
    BOLD,
    CYAN,
    DIM,
    GREEN,
    MAGENTA,
    RED,
    RESET,
    YELLOW,
    c,
    halluc_bar,
    halluc_color,
    reason_label,
    score_bar,
    short_id,
    trunc,
)


def _api(args: argparse.Namespace) -> CortexAPI:
    url = getattr(args, "url", None) or CORTEX_URL
    key = getattr(args, "key", None) or CORTEX_API_KEY
    return CortexAPI(base_url=url, api_key=key)


def _json_out(data) -> None:
    json.dump(data, sys.stdout, indent=2, default=str)
    print()


# ── Commands ──────────────────────────────────────────────────────


def cmd_stats(args: argparse.Namespace) -> None:
    api = _api(args)
    s = api.stats_sync()
    if args.json:
        _json_out({
            "total_agents": s.total_agents,
            "total_memories": s.total_memories,
            "total_transactions": s.total_transactions,
            "total_attributions": s.total_attributions,
            "avg_hallucination_index": s.avg_hallucination_index,
            "most_active_agent": s.most_active_agent,
        })
        return
    print(f"\n{c('CortexOS Stats', BOLD)}")
    print(f"  Agents:        {c(str(s.total_agents), CYAN)}")
    print(f"  Memories:      {c(str(s.total_memories), CYAN)}")
    print(f"  Transactions:  {c(str(s.total_transactions), CYAN)}")
    print(f"  Attributions:  {c(str(s.total_attributions), CYAN)}")
    if s.avg_hallucination_index > 0:
        print(f"  Avg Halluc:    {c(f'{s.avg_hallucination_index:.0%}', halluc_color(s.avg_hallucination_index))}")
    if s.most_active_agent:
        print(f"  Most Active:   {c(s.most_active_agent, MAGENTA)}")
    print()


def cmd_agents(args: argparse.Namespace) -> None:
    api = _api(args)
    agents = api.agents_sync()
    if args.json:
        _json_out([{
            "agent_id": a.agent_id,
            "memories": a.total_memories,
            "transactions": a.total_transactions,
            "avg_attribution": a.avg_attribution,
        } for a in agents])
        return
    print(f"\n{c('Agents', BOLD)} ({len(agents)})\n")
    fmt = "  {:<28s} {:>6s} {:>6s} {:>8s}"
    print(c(fmt.format("AGENT", "MEMS", "TXNS", "AVG_ATTR"), DIM))
    for a in agents:
        print(fmt.format(
            c(a.agent_id, MAGENTA),
            str(a.total_memories),
            str(a.total_transactions),
            f"{a.avg_attribution:.3f}" if a.avg_attribution else "-",
        ))
    print()


def cmd_memories(args: argparse.Namespace) -> None:
    api = _api(args)
    mems, total = api.memories_sync(agent_id=args.agent, limit=args.limit)
    if args.json:
        _json_out([{
            "id": m.id, "agent_id": m.agent_id,
            "content": m.content, "retrieval_count": m.retrieval_count,
        } for m in mems])
        return
    label = f"for {c(args.agent, MAGENTA)}" if args.agent else ""
    print(f"\n{c('Memories', BOLD)} {label} ({total} total)\n")
    for m in mems:
        print(f"  {c(short_id(m.id), CYAN)}  {c(m.agent_id, MAGENTA)}")
        print(f"    {trunc(m.content, 70)}")
        print(f"    {c(f'recalls: {m.retrieval_count}', DIM)}")
    print()


def cmd_search(args: argparse.Namespace) -> None:
    api = _api(args)
    query = " ".join(args.query)
    results = api.search_sync(query, top_k=args.top_k)
    if args.json:
        _json_out(results)
        return
    print(f"\n{c('Search', BOLD)}: \"{query}\" ({len(results)} results)\n")
    for r in results:
        mem = r.get("memory", {})
        sim = r.get("similarity", 0)
        bar = score_bar(sim, 16)
        print(f"  {sim:.3f} {bar}  {c(mem.get('agent_id', '?'), MAGENTA)}")
        print(f"    {trunc(mem.get('content', ''), 70)}")
    print()


def cmd_hallucinations(args: argparse.Namespace) -> None:
    api = _api(args)
    data = api.hallucinations_sync(agent_id=args.agent, limit=args.limit)
    if args.json:
        _json_out(data)
        return
    print(f"\n{c('Hallucination Report', BOLD)} ({len(data)} transactions)\n")
    for h in data:
        aid = h.get("agent_id", "?")
        hi = h.get("hallucination_index", 0)
        tid = h.get("transaction_id", "?")
        bar = halluc_bar(hi, 15)
        print(f"  {c(short_id(tid), CYAN)} {c(aid, MAGENTA)} {bar} {c(f'{hi:.0%}', halluc_color(hi))}")
    print()


def cmd_attribute(args: argparse.Namespace) -> None:
    api = _api(args)
    txn_id = args.txn_id
    try:
        data = api.trigger_cama_sync(txn_id)
    except Exception as e:
        print(f"{c('Error', RED)}: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        _json_out(data)
        return

    hi = data.get("hallucination_index", 0)
    claims = data.get("claims", [])
    grounded = [cl for cl in claims if not cl.get("is_hallucination")]
    halluc = [cl for cl in claims if cl.get("is_hallucination")]

    print(f"\n{c('CAMA Attribution', BOLD)} — {c(short_id(txn_id), CYAN)}")
    print(f"  Claims: {len(claims)}  Grounded: {c(str(len(grounded)), GREEN)}  "
          f"Hallucinated: {c(str(len(halluc)), RED)}  "
          f"Index: {c(f'{hi:.0%}', halluc_color(hi))}\n")

    if grounded:
        print(f"  {c('GROUNDED', GREEN)}")
        for cl in grounded:
            reason = cl.get("hallucination_reason", "")
            tag = f" [{reason}]" if reason else ""
            print(f"    {c('✓', GREEN)} \"{trunc(cl['claim'], 65)}\"{c(tag, DIM)}")
            for s in cl.get("sources", []):
                sv = s.get("shapley_value", 0)
                bar = score_bar(sv, 12)
                print(f"      └── {c(short_id(s['memory_id']), CYAN)} {bar} {sv:.2f}")
        print()

    if halluc:
        print(f"  {c('HALLUCINATED', RED)}")
        for cl in halluc:
            reason = reason_label(cl.get("hallucination_reason", ""))
            print(f"    {c('✗', RED)} \"{trunc(cl['claim'], 60)}\" {c(f'[{reason}]', YELLOW)}")
        print()

    dead = data.get("dead_memories", [])
    if dead:
        print(f"  {c('DEAD MEMORIES', YELLOW)} ({len(dead)})")
        for mid in dead:
            print(f"    • {c(short_id(mid), DIM)}")
        print()


def cmd_dead(args: argparse.Namespace) -> None:
    api = _api(args)
    dead = api.dead_memories_sync()
    if args.json:
        _json_out([{
            "memory_id": d.memory_id, "agent_id": d.agent_id,
            "content": d.content, "retrieval_count": d.retrieval_count,
            "mean_attribution": d.mean_attribution,
        } for d in dead])
        return
    print(f"\n{c('Dead Memories', BOLD)} ({len(dead)})\n")
    if not dead:
        print(f"  {c('No dead memories found.', GREEN)}\n")
        return
    for d in dead:
        print(f"  {c(short_id(d.memory_id), CYAN)} {c(d.agent_id, MAGENTA)}")
        print(f"    {trunc(d.content, 70)}")
        print(f"    {c(f'recalls: {d.retrieval_count}  avg_attr: {d.mean_attribution:.3f}', DIM)}")
    print()


def cmd_export(args: argparse.Namespace) -> None:
    api = _api(args)
    all_mems = []
    offset = 0
    while True:
        mems, total = api.memories_sync(limit=50, offset=offset)
        all_mems.extend(mems)
        offset += len(mems)
        if offset >= total or not mems:
            break

    if args.format == "csv":
        print("id,agent_id,content,retrieval_count,created_at")
        for m in all_mems:
            content = m.content.replace('"', '""').replace("\n", " ")
            print(f'"{m.id}","{m.agent_id}","{content}",{m.retrieval_count},"{m.created_at}"')
    else:
        _json_out([{
            "id": m.id, "agent_id": m.agent_id, "content": m.content,
            "retrieval_count": m.retrieval_count, "created_at": m.created_at,
        } for m in all_mems])


# ── Entry Point ───────────────────────────────────────────────────


def cli_main() -> None:
    parser = argparse.ArgumentParser(
        prog="cortex",
        description="CortexOS CLI — Memory Attribution Engine",
    )
    parser.add_argument("--url", help="CortexOS server URL", default=None)
    parser.add_argument("--key", help="API key", default=None)

    # Common flags added to every subparser
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="Output as JSON")
    common.add_argument("--no-color", action="store_true", help="Disable colors")

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("stats", help="System statistics", parents=[common])

    sub.add_parser("agents", help="List all agents", parents=[common])

    p_mem = sub.add_parser("memories", help="Browse memories", parents=[common])
    p_mem.add_argument("--agent", help="Filter by agent ID")
    p_mem.add_argument("--limit", type=int, default=20)

    p_search = sub.add_parser("search", help="Semantic search", parents=[common])
    p_search.add_argument("query", nargs="+", help="Search query")
    p_search.add_argument("--top-k", type=int, default=5)

    p_halluc = sub.add_parser("hallucinations", help="Hallucination report", parents=[common])
    p_halluc.add_argument("--agent", help="Filter by agent ID")
    p_halluc.add_argument("--limit", type=int, default=20)

    p_attr = sub.add_parser("attribute", help="Run CAMA attribution on a transaction", parents=[common])
    p_attr.add_argument("txn_id", help="Transaction ID")

    sub.add_parser("dead", help="List dead memories", parents=[common])

    p_export = sub.add_parser("export", help="Export all memories", parents=[common])
    p_export.add_argument("--format", choices=["json", "csv"], default="json")

    args = parser.parse_args()

    if args.no_color:
        import cortex_cli.formatters as fmt
        fmt.USE_COLOR = False

    commands = {
        "stats": cmd_stats,
        "agents": cmd_agents,
        "memories": cmd_memories,
        "search": cmd_search,
        "hallucinations": cmd_hallucinations,
        "attribute": cmd_attribute,
        "dead": cmd_dead,
        "export": cmd_export,
    }

    if not args.command:
        parser.print_help()
        sys.exit(0)

    fn = commands.get(args.command)
    if fn:
        fn(args)
    else:
        parser.print_help()
        sys.exit(1)
