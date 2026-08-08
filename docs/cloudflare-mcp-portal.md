# Cloudflare MCP Server Portal

ChatGPT reaches planner-mcp through the Cloudflare MCP Server Portal, which terminates TLS and
enforces access control in front of the control plane.

- The control plane binds locally and is exposed only via the tunnel.
- The browser worker is never exposed through the portal.
- Streamable HTTP transport (`/mcp`) is the portal target; health probing uses the internal
  healthcheck binary instead.
- Portal access policy, identity and logging are configured outside this repository; no Cloudflare
  tokens are stored here.
