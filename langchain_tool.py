"""
langchain_tool.py
LangChain / LangGraph Tool Wrapper for AI TO AI HOLDING — Thai Trade Intelligence API

Usage:
    from langchain_tool import ThaiCustomsTool, ThaiSandboxTool
    tools = [ThaiCustomsTool(api_key="YOUR_KEY"), ThaiSandboxTool()]

Sandbox (free, no key needed):
    from langchain_tool import ThaiSandboxTool
    tool = ThaiSandboxTool()
    result = tool.run("frozen shrimp vannamei")

Docs: https://web-production-c9da4.up.railway.app/docs
"""

from __future__ import annotations
from typing import Optional, Type
import json
import requests
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

BASE_URL = "https://web-production-c9da4.up.railway.app"
SANDBOX_URL = f"{BASE_URL}/v1/sandbox/classify"
CLASSIFY_URL = f"{BASE_URL}/v1/customs/classify"


# ─── Input Schemas ────────────────────────────────────────────────────────────

class SandboxInput(BaseModel):
    product_description: str = Field(
        ...,
        description="Product name in Thai, English, or mixed. E.g. 'มือถือ iPhone 16', 'frozen shrimp'"
    )


class ClassifyInput(BaseModel):
    product_description: str = Field(
        ...,
        description="Product name in Thai, English, or mixed"
    )
    origin_country: Optional[str] = Field(
        None,
        description="ISO 3166-1 alpha-2 country code of origin (e.g. CN, US, JP, VN, TH)"
    )
    destination_country: Optional[str] = Field(
        None,
        description="Destination country for Halal check (ISO alpha-2). Defaults to TH."
    )
    value_usd: Optional[float] = Field(
        None,
        description="CIF value in USD for duty amount calculation"
    )


# ─── Free Sandbox Tool (no API key) ──────────────────────────────────────────

class ThaiSandboxTool(BaseTool):
    """
    Free Thai customs classifier — no API key required.
    Rate limited to 20 requests/min.

    Returns: HS code, confidence score, MFN duty rate, FTA rates, OGA permits,
             Halal status, Thai description, SHA-256 evidence hash.
    """
    name: str = "thai_customs_sandbox"
    description: str = (
        "Free Thai customs trade classifier. Given a product description (Thai, English, or mixed), "
        "returns: HS code, import duty rate (MFN), best FTA rate across 13 Thai FTA agreements, "
        "OGA permit requirements from Thai government agencies, Halal certification status across "
        "21 countries, and SHA-256 evidence chain. Use this for: HS code lookup, duty estimation, "
        "trade compliance pre-check. No API key needed for sandbox. Input: product description string."
    )
    args_schema: Type[BaseModel] = SandboxInput

    def _run(self, product_description: str) -> str:
        try:
            resp = requests.post(
                SANDBOX_URL,
                json={"description": product_description},
                timeout=30,
            )
            resp.raise_for_status()
            return json.dumps(resp.json(), ensure_ascii=False, indent=2)
        except requests.RequestException as e:
            return json.dumps({"error": str(e)})

    async def _arun(self, product_description: str) -> str:
        import httpx
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.post(
                    SANDBOX_URL,
                    json={"description": product_description},
                )
                resp.raise_for_status()
                return json.dumps(resp.json(), ensure_ascii=False, indent=2)
            except Exception as e:
                return json.dumps({"error": str(e)})


# ─── Production Tool (requires API key) ──────────────────────────────────────

class ThaiCustomsTool(BaseTool):
    """
    Production Thai customs classifier — requires API key ($1.50/query, prepaid via Stripe).
    Rate limited to 60 requests/min.

    Register at: https://web-production-c9da4.up.railway.app
    """
    name: str = "thai_customs_classifier"
    description: str = (
        "Production Thai customs trade intelligence API. Given a product description and optional "
        "origin country, returns: HS code (6-digit), confidence score, MFN duty rate, best FTA rate "
        "across 13 Thai FTA agreements (RCEP, AFTA, ACFTA, AJCEP, AKFTA, AANZFTA, AIFTA, JTEPA, "
        "TCFTA, TPFTA, MFN), OGA permit requirements from Thai agencies (FDA, TISI, DOF, DLD, DOA, "
        "DNP, ONCB, MOD), Halal certification status for 21 countries, and SHA-256 evidence chain. "
        "Requires X-API-Key header."
    )
    args_schema: Type[BaseModel] = ClassifyInput
    api_key: str = Field(default="", description="API key from AI TO AI HOLDING")

    def _run(
        self,
        product_description: str,
        origin_country: Optional[str] = None,
        destination_country: Optional[str] = None,
        value_usd: Optional[float] = None,
    ) -> str:
        payload: dict = {"description": product_description}
        if origin_country:
            payload["origin_country"] = origin_country
        if destination_country:
            payload["destination_country"] = destination_country
        if value_usd is not None:
            payload["value_usd"] = value_usd

        try:
            resp = requests.post(
                CLASSIFY_URL,
                headers={"X-API-Key": self.api_key, "Content-Type": "application/json"},
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            return json.dumps(resp.json(), ensure_ascii=False, indent=2)
        except requests.RequestException as e:
            return json.dumps({"error": str(e)})

    async def _arun(
        self,
        product_description: str,
        origin_country: Optional[str] = None,
        destination_country: Optional[str] = None,
        value_usd: Optional[float] = None,
    ) -> str:
        import httpx
        payload: dict = {"description": product_description}
        if origin_country:
            payload["origin_country"] = origin_country
        if destination_country:
            payload["destination_country"] = destination_country
        if value_usd is not None:
            payload["value_usd"] = value_usd

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.post(
                    CLASSIFY_URL,
                    headers={"X-API-Key": self.api_key},
                    json=payload,
                )
                resp.raise_for_status()
                return json.dumps(resp.json(), ensure_ascii=False, indent=2)
            except Exception as e:
                return json.dumps({"error": str(e)})


# ─── Quick test ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    tool = ThaiSandboxTool()
    print(tool.run("frozen shrimp vannamei"))
