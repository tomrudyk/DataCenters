"""
k-ary fat-tree topology generator (Al-Fares, Loukissas, Vahdat, SIGCOMM 2008).


USAGE
-----
    python fat_tree.py 4                    # print summary
    python fat_tree.py 4 --verbose          # also print every link
    python fat_tree.py 8 --fail-percent 10 --seed 1   # fail 10% of the links

    from fat_tree import build_fat_tree, fail_links
    nodes, links = build_fat_tree(4)
    alive, failed = fail_links(links, 10, seed=1)

OUTPUT
------
nodes : dict  name -> {"type": "core"|"aggr"|"edge"|"host", "pod": int or None}
links : list of (upper_node, port, lower_node, port), ordered top to bottom:
        core-aggr links first, then aggr-edge, then edge-host.
alive, failed : the links after applying fail_links (alive + failed = links)

Node names (all indices start at 0):
    core switch c_<row>_<col>          (k/2 x k/2 grid)
    aggr switch a_<pod>_<index>
    edge switch e_<pod>_<index>
    host        h_<pod>_<edge>_<i>     i-th host under that edge switch

Port numbering:
    core : port p -> pod p
    aggr : ports 0..k/2-1 -> edge switches, ports k/2..k-1 -> core switches
    edge : ports 0..k/2-1 -> hosts,         ports k/2..k-1 -> aggr switches
    host : single port 0

    example:
    c_1_1:2 <-> a_2_1:3 reads:
        c_1_1:2: core switch row 1, col 1, port 2. Port 2 faces pod 2
        a_2_1:3: aggregation switch 1 in pod 2. This matches the pod the core port points to.
        Port 3 on the aggregation switch is an uplink - connected to core.
"""

import argparse
import random
from collections import defaultdict

LAYERS = ["core", "aggr", "edge", "host"]    # top to bottom


def count_nodes(k):
    """Number of nodes per layer, computed from the formulas in the paper."""
    half = k // 2
    counts = {
        "core": half * half,
        "aggr": k * half,
        "edge": k * half,
        "host": k * half * half,
    }
    counts["switches"] = counts["core"] + counts["aggr"] + counts["edge"]
    return counts


def build_fat_tree(k):
    if k < 2 or k % 2:
        raise ValueError("k must be an even integer >= 2")
    half = k // 2

    nodes = {} ## The switch itself and where is it.
    links = [] ## A list of connections between nodes.

    def add_node(name, kind, pod=None):
        nodes[name] = {"type": kind, "pod": pod}

    # Nodes, top to bottom
    for row in range(half):
        for col in range(half):
            add_node(f"c_{row}_{col}", "core")
    for pod in range(k):
        for i in range(half):
            add_node(f"a_{pod}_{i}", "aggr", pod)
    for pod in range(k):
        for i in range(half):
            add_node(f"e_{pod}_{i}", "edge", pod)
    for pod in range(k):
        for e in range(half):
            for h in range(half):
                add_node(f"h_{pod}_{e}_{h}", "host", pod)

    
    
    # Core <-> aggregation: aggr switch a connects to core row a.
    # Its uplink i goes to core (a, i); that core switch's port `pod` faces
    # this pod, so each core switch reaches every pod exactly once.
    for pod in range(k):
        for a in range(half):
            for i in range(half):
                links.append((f"c_{a}_{i}", pod, f"a_{pod}_{a}", half + i))

    # Aggregation <-> edge: full bipartite graph inside each pod
    for pod in range(k):
        for a in range(half):
            for e in range(half):
                links.append((f"a_{pod}_{a}", e, f"e_{pod}_{e}", half + a))

    # Edge <-> hosts: k/2 hosts per edge switch
    for pod in range(k):
        for e in range(half):
            for h in range(half):
                links.append((f"e_{pod}_{e}", h, f"h_{pod}_{e}_{h}", 0))

    return nodes, links





def fail_links(links, percent, seed=None):
    """Randomly fail `percent`% of the links. Returns (alive, failed)."""
    if not 0 <= percent <= 100:
        raise ValueError("fail percent must be between 0 and 100")
    num_failed = round(len(links) * percent / 100)
    failed = set(random.Random(seed).sample(links, num_failed))
    # Randomly choosing links to fail
    # checking wheter a link is in links and not in faild
    alive = [link for link in links if link not in failed]
    return alive, list(failed)


def largest_host_group(nodes, alive):
    """Number of hosts in the biggest set of hosts that can still reach each other."""

    # Builds a neighbor list from the links that did not fail, then runs a depth-first
    # search from each unvisited node to collect one connected group at a time,
    # marking nodes as seen so each is visited only once. It counts the hosts in
    # each group and returns the size of the largest one, i.e. how many hosts can still reach each other. 
    neighbors = defaultdict(list)
    for a, _, b, _ in alive:
        neighbors[a].append(b)
        neighbors[b].append(a)

    seen, best = set(), 0
    for start in nodes: ## Start looks for a new group
        if start in seen:                    # already part of a group we counted
            continue
        seen.add(start)
        stack, hosts = [start], 0
        while stack:                         # depth-first search over one group
            node = stack.pop()
            hosts += nodes[node]["type"] == "host"   # count hosts only, not switches
            for nxt in neighbors[node]:
                if nxt not in seen:          # visit each node once
                    seen.add(nxt)
                    stack.append(nxt)
        best = max(best, hosts)              # keep the largest group found
    return best


def check_counts(k, nodes, links):
    """Verify the generated topology against the formulas."""
    expected = count_nodes(k)
    for layer in LAYERS:
        actual = sum(1 for n in nodes.values() if n["type"] == layer)
        assert actual == expected[layer], layer
    assert expected["switches"] == 5 * k * k // 4
    assert len(links) == 3 * k ** 3 // 4          # core-aggr, aggr-edge, edge-host

    # Every switch must use exactly k distinct ports.
    used = set()
    for a, pa, b, pb in links:
        for end in ((a, pa), (b, pb)):
            assert end not in used, f"port reused: {end}"
            used.add(end)
    for name, n in nodes.items():
        if n["type"] != "host":
            assert sum(1 for x, _ in used if x == name) == k, name


def main():
    parser = argparse.ArgumentParser(description="Generate a k-ary fat-tree.")
    parser.add_argument("k", type=int, help="ports per switch (even number)")
    parser.add_argument("--verbose", action="store_true", help="print all links")
    parser.add_argument("--fail-percent", type=float, default=0,
                        help="percentage of links that fail (default 0)")
    parser.add_argument("--seed", type=int, help="random seed for the failures")
    args = parser.parse_args()

    nodes, links = build_fat_tree(args.k)
    check_counts(args.k, nodes, links)

    counts = count_nodes(args.k)
    print(f"k={args.k}: {len(nodes)} nodes, {len(links)} links")
    for layer in LAYERS:
        print(f"  {layer:5s}: {counts[layer]}")
    print(f"  total switches: {counts['switches']}")

    alive, failed = fail_links(links, args.fail_percent, args.seed)
    if failed:
        group = largest_host_group(nodes, alive)
        print(f"failed links: {len(failed)} of {len(links)} ({args.fail_percent}%)")
        print(f"  hosts still connected to each other: {group} of {counts['host']}")

    if args.verbose:
        failed_set = set(failed)
        for link in links:
            a, pa, b, pb = link
            mark = "  [FAILED]" if link in failed_set else ""
            print(f"{a}:{pa} <-> {b}:{pb}{mark}")



if __name__ == "__main__":
    main()