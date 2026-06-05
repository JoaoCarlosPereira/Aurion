"""Busca na web via DuckDuckGo."""

from duckduckgo_search import DDGS
from langchain.tools import tool


@tool("duckduckgo_search", return_direct=True)
def duckduckgo_search_tool(query: str) -> str:
    """
    Perform a web search using DuckDuckGo and return the top result.
    Use this tool when the user asks a question that requires up-to-date information from the internet.
    """
    with DDGS() as ddgs:
        results = ddgs.text(query, region='wt-wt', safesearch='Moderate', max_results=1)
        results_list = list(results)

    if not results_list:
        return f"Apologies, I couldn't find any results for: \"{query}\"."

    top = results_list[0]
    return (
        f"Certainly sir, here's the top result for: \"{query}\"\n\n"
        f"\U0001f539 Title: {top['title']}\n"
        f"\U0001f517 URL: {top['href']}\n"
    )
