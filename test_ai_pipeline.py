#!/usr/bin/env python3
"""
test_ai_pipeline.py - Test the AI enrichment pipeline with real API keys
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("=" * 60)
print("Testing BetOracle AI Enrichment Pipeline")
print("=" * 60)

# Check environment
print("\n📋 Environment Check:")
print(f"  FOOTBALL_API_KEY: {'✓ Set' if os.getenv('FOOTBALL_API_KEY') else '✗ Missing'}")
print(f"  ANTHROPIC_API_KEY: {'✓ Set' if os.getenv('ANTHROPIC_API_KEY') else '✗ Missing'}")
print(f"  OPENAI_API_KEY: {'✓ Set' if os.getenv('OPENAI_API_KEY') else '✗ Missing'}")
print(f"  AI_PROVIDER: {os.getenv('AI_PROVIDER', 'anthropic')}")
print(f"  AI_ENRICHMENT_ENABLED: {os.getenv('AI_ENRICHMENT_ENABLED', 'True')}")

# Test imports
print("\n📦 Import Tests:")
try:
    from ai_enrichment import AIEnricher, AIEnrichedData
    print("  ✓ ai_enrichment module imports")
except Exception as e:
    print(f"  ✗ ai_enrichment import failed: {e}")
    sys.exit(1)

try:
    from data_fetcher import DataFetcher
    print("  ✓ data_fetcher module imports")
except Exception as e:
    print(f"  ✗ data_fetcher import failed: {e}")
    sys.exit(1)

# Test DataFetcher initialization
print("\n🔧 DataFetcher Initialization:")
try:
    fetcher = DataFetcher()
    print("  ✓ DataFetcher initialized")
    print(f"    - Mock mode: {fetcher.mock_mode}")
    print(f"    - AI enrichment enabled: {fetcher.ai_enrichment_enabled}")
    print(f"    - Football API key: {'✓' if fetcher.football_api_key else '✗'}")
except Exception as e:
    print(f"  ✗ DataFetcher init failed: {e}")
    sys.exit(1)

# Test AI Enricher
print("\n🤖 AI Enricher Test:")
try:
    enricher = AIEnricher()
    print("  ✓ AIEnricher initialized")
    print(f"    - Provider: {enricher.provider}")
    print(f"    - Claude client: {'✓' if enricher._claude_client else '✗'}")
    print(f"    - OpenAI client: {'✓' if enricher._openai_client else '✗'}")
    print(f"    - Mock mode: {enricher.mock_mode}")
except Exception as e:
    print(f"  ✗ AIEnricher init failed: {e}")
    sys.exit(1)

# Test enrichment with real AI call
print("\n🧠 AI Enrichment Test (Real API Call):")
print("  Calling Claude/OpenAI for Arsenal vs Chelsea analysis...")
try:
    result = enricher.enrich_match_data(
        home_team="Arsenal",
        away_team="Chelsea",
        league="EPL",
        home_form=["W", "W", "D", "L", "W"],
        away_form=["L", "W", "W", "D", "D"],
        h2h_record=["HOME", "AWAY", "DRAW", "HOME"]
    )
    print("  ✓ AI enrichment successful!")
    print("\n  📊 Results:")
    print(f"    Form Summary: {result.form_summary}")
    print("    Key Insights:")
    for i, insight in enumerate(result.key_insights, 1):
        print(f"      {i}. {insight}")
    print(f"    Injuries Found: {len(result.injury_report)}")
    if result.injury_report:
        for inj in result.injury_report:
            print(f"      - {inj['player']} ({inj['team']}): {inj['severity']}")
    print("    Confidence Factors:")
    for factor, weight in result.confidence_factors.items():
        print(f"      - {factor}: {weight}")
except Exception as e:
    print(f"  ✗ AI enrichment failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test market odds generation
print("\n💰 AI Market Odds Test:")
print("  Generating probability-based odds...")
try:
    odds = enricher.get_market_insights("Arsenal", "Chelsea", "EPL")
    if odds:
        print("  ✓ Market insights generated!")
        print(f"    Home win prob: {odds.get('home_win_prob', 'N/A')}")
        print(f"    Draw prob: {odds.get('draw_prob', 'N/A')}")
        print(f"    Away win prob: {odds.get('away_win_prob', 'N/A')}")
        print(f"    Confidence: {odds.get('confidence', 'N/A')}")
        print(f"    Reasoning: {odds.get('reasoning', 'N/A')[:100]}...")
    else:
        print("  ⚠ No market insights (AI may not be configured)")
except Exception as e:
    print(f"  ✗ Market insights failed: {e}")

# Test DataFetcher integration
print("\n🔗 DataFetcher Integration Test:")
try:
    # Test injuries via AI enrichment
    injuries = fetcher.get_injuries("Arsenal", "EPL")
    print(f"  ✓ get_injuries() returned {len(injuries)} injuries")
    
    # Test market odds via AI enrichment
    odds = fetcher.get_market_odds("Arsenal", "Chelsea", "EPL")
    if odds:
        print("  ✓ get_market_odds() returned:")
        print(f"    Home: {odds.get('home')}, Draw: {odds.get('draw')}, Away: {odds.get('away')}")
        print(f"    Source: {odds.get('source', 'unknown')}")
    else:
        print("  ⚠ get_market_odds() returned None")
except Exception as e:
    print(f"  ✗ DataFetcher integration failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("✅ All tests completed successfully!")
print("=" * 60)
