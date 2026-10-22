"""The tool layer.

Four tools, each a pure function over the database (docs/PLAN.md, the agentic
flow):

  * `search_products(filters)` — the catalog, with price/stock/filters.
  * `get_benchmarks(component, resolution)` — the measured frame rates.
  * `check_compatibility(parts)` — the deterministic rule engine.
  * `search_wiki(query)` — the hybrid wiki search.

Every tool returns a plain dictionary, and every number in it is a fact the
assistant is allowed to state. The guardrail checks the answer against these
values, so a tool's output is the *only* source of a price or a stock count.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from apps.catalog.models import Entity, Product
from apps.compat.services import check_parts

from .retrieval import retrieve


@dataclass
class ToolResult:
    """One tool's result."""

    tool: str
    arguments: dict[str, Any] = field(default_factory=dict)
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error

    def as_dict(self) -> dict:
        return {
            "tool": self.tool,
            "arguments": self.arguments,
            "data": self.data,
            "error": self.error,
        }

    def facts(self) -> list[str]:
        """The values this result contributes to the fact list.

        Every number in here is allowed to appear in the answer.
        """
        values: list[str] = []
        for item in self.data.get("items", []):
            if isinstance(item, dict):
                for value in item.values():
                    if isinstance(value, (int, float, str)):
                        values.append(str(value))
        return values


def search_products(
    *,
    entity_type: str = "",
    brand: str = "",
    min_price: int = 0,
    max_price: int = 0,
    in_stock: bool | None = None,
    limit: int = 8,
) -> ToolResult:
    """Find products in the catalog.

    Filters: entity type, brand slug, a price range, and stock. The results
    carry the price, the stock and the "last updated" date — the three things
    the assistant must quote correctly.
    """
    arguments = {
        "entity_type": entity_type,
        "brand": brand,
        "min_price": min_price,
        "max_price": max_price,
        "in_stock": in_stock,
        "limit": limit,
    }
    try:
        products = Product.objects.filter(is_active=True).select_related("entity", "entity__brand")
        if entity_type:
            products = products.filter(entity__type=entity_type)
        if brand:
            products = products.filter(entity__brand__slug=brand)
        if min_price:
            products = products.filter(price__gte=min_price)
        if max_price:
            products = products.filter(price__lte=max_price)
        if in_stock is True:
            products = products.filter(stock__gt=0)
        elif in_stock is False:
            products = products.filter(stock=0)

        items = [
            {
                "sku": product.sku,
                "title": product.display_title,
                "entity_slug": product.entity.slug,
                "entity_type": product.entity.type,
                "price": str(product.price),
                "currency": product.currency,
                "stock": product.stock,
                "in_stock": product.in_stock,
                "updated_at": product.updated_at.isoformat(),
                "price_updated_at": (
                    product.price_updated_at.isoformat() if product.price_updated_at else None
                ),
            }
            for product in products.order_by("price")[:limit]
        ]

        return ToolResult(
            tool="search_products",
            arguments=arguments,
            data={"count": len(items), "items": items},
        )
    except Exception as exc:
        return ToolResult(tool="search_products", arguments=arguments, error=str(exc))


def get_benchmarks(
    component: str = "", resolution: str = "", game: str = "", limit: int = 10
) -> ToolResult:
    """The measured frame rates of a component.

    `component` is an entity slug; `resolution` and `game` narrow it down.
    """
    arguments = {
        "component": component,
        "resolution": resolution,
        "game": game,
        "limit": limit,
    }
    try:
        from apps.benchmarks.models import Benchmark

        benchmarks = Benchmark.objects.select_related("component")
        if component:
            benchmarks = benchmarks.filter(component__slug=component)
        if resolution:
            benchmarks = benchmarks.filter(resolution=resolution)
        if game:
            benchmarks = benchmarks.filter(game__iexact=game)

        items = [
            {
                "component": benchmark.component.slug,
                "component_title": benchmark.component.display_title,
                "game": benchmark.game,
                "game_fa": benchmark.game_fa,
                "resolution": benchmark.resolution,
                "preset": benchmark.preset,
                "avg_fps": benchmark.avg_fps,
                "p1_low": benchmark.p1_low,
                "tested_at": benchmark.tested_at.isoformat(),
            }
            for benchmark in benchmarks.order_by("-tested_at")[:limit]
        ]

        return ToolResult(
            tool="get_benchmarks",
            arguments=arguments,
            data={"count": len(items), "items": items},
        )
    except Exception as exc:
        return ToolResult(tool="get_benchmarks", arguments=arguments, error=str(exc))


def check_compatibility(parts: list[str]) -> ToolResult:
    """Check whether a set of parts works together.

    The verdict comes from the deterministic rule engine — never from a model.
    """
    arguments = {"parts": parts}
    try:
        report = check_parts(parts)
        return ToolResult(
            tool="check_compatibility",
            arguments=arguments,
            data={
                "verdict": report.verdict,
                "findings": [finding.as_dict() for finding in report.findings],
                "checked": report.checked,
            },
        )
    except Exception as exc:
        return ToolResult(tool="check_compatibility", arguments=arguments, error=str(exc))


def search_wiki(query: str, limit: int = 6) -> ToolResult:
    """Search the wiki and return the matching sections.

    This is the tool that produces the *citations*: each item carries the page
    and the section it came from.
    """
    arguments = {"query": query, "limit": limit}
    try:
        result = retrieve(query, limit=limit)
        items = []
        for item in result.chunks:
            citation = item.citation
            items.append(
                {
                    **citation,
                    "text": item.text[:600],
                }
            )
        return ToolResult(
            tool="search_wiki",
            arguments=arguments,
            data={"count": len(items), "items": items},
        )
    except Exception as exc:
        return ToolResult(tool="search_wiki", arguments=arguments, error=str(exc))


#: The tool registry, for the model's function-calling schema.
TOOLS: dict[str, Any] = {
    "search_products": search_products,
    "get_benchmarks": get_benchmarks,
    "check_compatibility": check_compatibility,
    "search_wiki": search_wiki,
}


def tool_schemas() -> list[dict]:
    """The tools as OpenAI-style function schemas, for a model that supports
    function calling."""
    return [
        {
            "name": "search_products",
            "description": (
                "Find products in the catalog. Returns the price, the stock and "
                "the last-updated date. Use this for any price or availability "
                "question — never state a price from memory."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_type": {
                        "type": "string",
                        "description": "cpu, gpu, ram, motherboard, psu, case, cooler, storage, prebuilt",
                    },
                    "brand": {"type": "string", "description": "the brand slug"},
                    "min_price": {"type": "integer", "description": "minimum price in tomans"},
                    "max_price": {"type": "integer", "description": "maximum price in tomans"},
                    "in_stock": {"type": "boolean", "description": "only available products"},
                    "limit": {"type": "integer", "description": "how many products (default 8)"},
                },
            },
        },
        {
            "name": "get_benchmarks",
            "description": "The measured frame rates of a component in a game.",
            "parameters": {
                "type": "object",
                "properties": {
                    "component": {"type": "string", "description": "the entity slug"},
                    "resolution": {"type": "string", "description": "720p, 1080p, 1440p or 4k"},
                    "game": {"type": "string", "description": "the game name"},
                    "limit": {"type": "integer", "description": "how many rows (default 10)"},
                },
            },
        },
        {
            "name": "check_compatibility",
            "description": (
                "Check whether a set of parts works together. The verdict comes "
                "from the deterministic rule engine, never from a model."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "parts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "the entity slugs to check",
                    }
                },
            },
        },
        {
            "name": "search_wiki",
            "description": "Search the wiki; returns the matching sections with their URLs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "description": "how many sections (default 6)"},
                },
            },
        },
    ]


def run_tool(name: str, arguments: dict[str, Any] | None = None) -> ToolResult:
    """Run a tool by name."""
    tool = TOOLS.get(name)
    if tool is None:
        return ToolResult(tool=name, arguments=arguments or {}, error=f"unknown tool {name!r}")
    try:
        return tool(**(arguments or {}))
    except TypeError as exc:
        return ToolResult(tool=name, arguments=arguments or {}, error=str(exc))


def resolve_entity_slugs(text: str, limit: int = 6) -> list[str]:
    """The entity slugs a text mentions — used to pick the parts to check."""
    entities = Entity.objects.filter(is_active=True).select_related("brand")
    found: list[str] = []
    lowered = text.lower()
    for entity in entities:
        names = [entity.title, entity.title_fa, *entity.aliases]
        if any(name and name.lower() in lowered for name in names):
            found.append(entity.slug)
            if len(found) >= limit:
                break
    return found
