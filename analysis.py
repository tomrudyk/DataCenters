"""
Metric analysis for the fat-tree: how many pods survive link failures?

QUESTION
--------
A pod is the basic building block of the fat-tree (k/2 edge + k/2 aggr
switches and k^2/4 hosts). When a percentage of links fails, how many pods
are still intact, and how many are still connected to the rest of the
network? And how does this change as k grows?

EXPERIMENT
----------
For every k in K_VALUES and every failure percentage in FAIL_PERCENTS:
  1. build the fat-tree and fail that percentage of links at random
     (fail_links from fat_tree.py),
  2. find the groups of hosts that can still reach each other,
  3. classify every pod,
  4. repeat TRIALS times with different random failures and average.

METRICS (both are a fraction of the k pods)
-------
1. Intact pods: pods with no failed link in the pod itself (host-edge and
   edge-aggr links) or in its uplinks to the core (aggr-core links). The core
   belongs to no pod, so each uplink is counted for the pod of its aggr switch.
   The pod and its uplinks have 3k^2/4 links, so the expected probability that one pod is intact is
   (1 - p)^(3k^2/4): it collapses quickly as k grows.
   host = k^2/4 (k/2 edge * k/2 lowerpart of switch)    edge-aggr = k/2*k/2     aggr-core = k/2*k/2 ===> 3k^2/4
2. Connected pods: pods with at least one host in the largest group of
   hosts, where that group must span at least 2 pods (a single pod alone is
   not a network). These pods can still talk to other pods. A pod only gets
   cut off when almost all of its k^2/4 uplinks fail.

USAGE
-----
    python3 analysis.py          # prints a table and saves fat_tree_analysis.png
"""

import random

import matplotlib
matplotlib.use("Agg")                  # draw to a file, no window needed
import matplotlib.pyplot as plt

from fat_tree import build_fat_tree, fail_links

K_VALUES = [4, 8, 16, 24, 32]                          # switch port counts to compare
FAIL_PERCENTS = [0, 1, 2, 5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]  # failure %
TRIALS = 50                                            # random failure sets per point


def host_groups(nodes, alive):
    """Return a list of host groups: hosts that can still reach each other."""
    # Adjacency list built only from the links that did not fail
    neighbors = {name: [] for name in nodes}
    for a, _, b, _ in alive:
        neighbors[a].append(b)
        neighbors[b].append(a)

    seen, groups = set(), []
    for start in nodes:
        if start in seen:                              # already part of a counted group
            continue
        seen.add(start)
        stack, hosts = [start], []
        while stack:                                   # depth-first search over one group
            node = stack.pop()
            if nodes[node]["type"] == "host":          # collect hosts, walk through all nodes
                hosts.append(node)
            for nxt in neighbors[node]:
                if nxt not in seen:                    # visit each node only once
                    seen.add(nxt)
                    stack.append(nxt)
        groups.append(hosts)
    return groups


def run_experiment(k, percent, rng):
    """Returns (fraction of intact pods, fraction of connected pods)."""
    nodes, links = build_fat_tree(k)
    intact_sum, connected_sum = 0, 0

    for _ in range(TRIALS):
        # Randomly fail `percent`% of the links (different failures each trial)
        alive, failed = fail_links(links, percent, seed=rng.random())

        # Metric 1: pods touched by a failure. The lower node of a link
        # (aggr, edge or host) always belongs to a pod, so it identifies the pod.
        # A failed core-aggr link counts for the pod of its aggr switch.
        damaged = {nodes[lower]["pod"] for _, _, lower, _ in failed}
        intact_sum += k - len(damaged)

        # Metric 2: pods that have a host in the largest group of hosts
        main_group = max(host_groups(nodes, alive), key=len)
        pods_in_main = {nodes[h]["pod"] for h in main_group}
        if len(pods_in_main) >= 2:                     # one pod alone is not a network
            connected_sum += len(pods_in_main)

    # Average over all trials and convert to a fraction of the k pods
    return intact_sum / (TRIALS * k), connected_sum / (TRIALS * k)


def main():
    rng = random.Random(0)                             # fixed seed: reproducible results
    results = {k: [run_experiment(k, p, rng) for p in FAIL_PERCENTS] for k in K_VALUES}

    # Print a table: for each failure %, "intact/connected" for every k
    print("fail%  " + "  ".join(f"k={k:<2} intact/conn" for k in K_VALUES))
    for i, p in enumerate(FAIL_PERCENTS):
        row = "  ".join(f"{results[k][i][0]:.3f}/{results[k][i][1]:.3f}   " for k in K_VALUES)
        print(f"{p:4}   {row}")

    # Plot both metrics against the failure percentage, one line per k
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))
    x = [p / 100 for p in FAIL_PERCENTS]               # failure probability p in [0, 1]
    for k in K_VALUES:
        line, = ax1.plot(FAIL_PERCENTS, [r[0] for r in results[k]], "o-", label=f"k={k}")
        # Theory: all 3k^2/4 links of a pod must survive (dashed, same color as k)
        ax1.plot(FAIL_PERCENTS, [(1 - p) ** (3 * k * k / 4) for p in x],
                 "--", color=line.get_color(), alpha=0.6)
        ax2.plot(FAIL_PERCENTS, [r[1] for r in results[k]], "o-", label=f"k={k}")
    ax1.plot([], [], "k--", alpha=0.6, label=r"theory $(1-p)^{3k^2/4}$")  # legend entry only

    ax1.set(xlabel="failed links (%)", ylabel="fraction of pods",
            title="Intact pods (no failed link in the pod or its uplinks)")
    ax2.set(xlabel="failed links (%)", ylabel="fraction of pods",
            title="Pods still connected to the main network")
    for ax in (ax1, ax2):
        ax.grid(alpha=0.3)
        ax.legend()
    fig.tight_layout()
    fig.savefig("fat_tree_analysis.png", dpi=150)
    print("saved fat_tree_analysis.png")


if __name__ == "__main__":
    main()