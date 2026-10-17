"""
k-ary fat-tree topology generator (Al-Fares, Loukissas, Vahdat, SIGCOMM 2008).

INPUT PARAMETERS
----------------
k : int  (even, >= 2)
    Number of ports per switch. Every switch in the network is identical.
    This single parameter fixes the whole topology:

        pods                    = k
        core switches           = (k/2)^2
        aggr switches per pod   = k/2      (upper layer of each pod)
        edge switches per pod   = k/2      (lower layer of each pod)
        hosts per edge switch   = k/2
        total switches          = (k/2)^2 + k*k = 5k^2 / 4
        total hosts             = k^3 / 4
        total nodes             = (5k^2 + k^3) / 4 = switches + hosts
        total links             = k^3/4 + k^3/4 + k^3/4 = 3k^3 / 4
                                  (core-aggr + aggr-edge + edge-host)

    Examples: k=4  -> 16 hosts, 20 switches (Figure 3 of the paper)
              k=48 -> 27,648 hosts, 2,880 switches

USAGE
-----
    python fat_tree.py 4                    # print summary
    python fat_tree.py 4 --verbose          # also print every link
    python fat_tree.py 8 --json out.json    # export topology to JSON

    from fat_tree import build_fat_tree
    nodes, links = build_fat_tree(4)

OUTPUT
------
nodes : dict  name -> {"type": "core"|"aggr"|"edge"|"host", "pod": int or None}
links : list of (upper_node, port, lower_node, port), ordered top to bottom:
        core-aggr links first, then aggr-edge, then edge-host.

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
import json

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

    nodes = {}
    links = []

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
    parser.add_argument("--json", metavar="FILE", help="export topology as JSON")
    args = parser.parse_args()

    nodes, links = build_fat_tree(args.k)
    check_counts(args.k, nodes, links)

    counts = count_nodes(args.k)
    print(f"k={args.k}: {len(nodes)} nodes, {len(links)} links")
    for layer in LAYERS:
        print(f"  {layer:5s}: {counts[layer]}")
    print(f"  total switches: {counts['switches']}")

    if args.verbose:
        for a, pa, b, pb in links:
            print(f"{a}:{pa} <-> {b}:{pb}")

    if args.json:
        with open(args.json, "w") as f:
            json.dump({"k": args.k, "nodes": nodes, "links": links}, f, indent=1)
        print(f"written to {args.json}")


if __name__ == "__main__":
    main()