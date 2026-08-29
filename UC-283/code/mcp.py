"""Compatibility entrypoint for the validated dynamic MCP tool server."""
from __future__ import annotations

import json

from mcp_server import MCPToolServer, build_pricing_server


if __name__ == "__main__":
    context = {"product_id": "SKU-123", "current_price": 249.99,
               "cost": 150, "competitor_price": 245, "historical_volatility": 5.5}
    server = build_pricing_server(lambda: context)
    print(json.dumps({"tools": server.list_tools(),
                      "example": server.call_tool("get_market_context", {"product_id": "SKU-123"})},
                     indent=2, ensure_ascii=False))