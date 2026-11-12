from agents.knowledge_agent import organize
from agents.conflict_agent import diagnose


def run(pages):
    """Deterministic fallback shares the same node functions as LangGraph."""
    try:
        from langgraph.graph import StateGraph, START, END
    except ImportError:
        chunks = organize(pages)
        return {'pages':pages,'chunks':chunks,'issues':diagnose(chunks,pages),'engine':'顺序工作流'}
    from typing import TypedDict
    class State(TypedDict, total=False):
        pages: list
        chunks: list
        issues: list
    graph = StateGraph(State)
    graph.add_node('organize',lambda s:{'chunks':organize(s['pages'])})
    graph.add_node('diagnose',lambda s:{'issues':diagnose(s['chunks'],s['pages'])})
    graph.add_edge(START,'organize')
    graph.add_edge('organize','diagnose')
    graph.add_edge('diagnose',END)
    return {**graph.compile().invoke({'pages':pages}),'engine':'LangGraph'}
