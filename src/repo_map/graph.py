"""Approximate call graph.

An edge caller -> callee exists for every call site resolved to a project symbol.
NetworkX is already a dependency:

    import networkx as nx

    graph = nx.DiGraph()
    graph.add_edge("tiny_pkg.a.public_api", "tiny_pkg.b.helper")
    nx.shortest_path(graph, source, target)   # raises nx.NetworkXNoPath
"""

from repo_map.model import CallSite


class CallGraph:
    @classmethod
    def from_call_sites(cls, call_sites: list[CallSite]) -> "CallGraph":
        raise NotImplementedError("CallGraph.from_call_sites")

    def callers(self, qualified_name: str) -> list[str]:
        raise NotImplementedError("CallGraph.callers")

    def callees(self, qualified_name: str) -> list[str]:
        raise NotImplementedError("CallGraph.callees")

    def shortest_path(self, source: str, target: str) -> list[str] | None:
        raise NotImplementedError("CallGraph.shortest_path")
