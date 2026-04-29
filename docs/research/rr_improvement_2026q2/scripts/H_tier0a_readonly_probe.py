"""
Tier 0a — optional read-only probe for Lighter SDK / REST (AGENT_BRIEF_TIER0A).

NOT run in CI by default. Intended for Linux executor or env where `import lighter` works.

Usage (after .env with testnet + READ creds):
  python H_tier0a_readonly_probe.py

Do NOT use on mainnet without explicit approval. No order placement.
"""
from __future__ import annotations

# Example (uncomment when running on compatible host):
# import asyncio
# import lighter
# from lighter.configuration import Configuration
# from lighter.api.order_api import OrderApi
#
# async def main():
#     Configuration.set_default(Configuration(host="https://mainnet.zklighter.elliot.ai"))
#     # set ApiClient default auth from SignerClient token...
#     api = OrderApi()
#     r = await api.account_inactive_orders(account_index=0, limit=5, auth="<token>")
#     print(r)
#
# if __name__ == "__main__":
#     asyncio.run(main())

print(__doc__)
