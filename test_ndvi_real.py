import os
# Mock env vars BEFORE importing config
os.environ["BOT_TOKEN"] = "test_token_123"
os.environ["ANTHROPIC_API_KEY"] = "sk-test-key"

import asyncio
from modules.crop_analyzer import CropAnalyzer
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)

async def test_ndvi():
    print("🚀 Testing Real NDVI Logic...")
    
    # Initialize with dummy key for fallback test
    analyzer = CropAnalyzer(api_key="sk-test")
    
    # 1. Test Polygon (Tashkent field)
    bbox = [69.24, 41.29, 69.25, 41.30]
    lat = 41.295
    lon = 69.245
    
    print(f"\n📡 Testing Polygon Analysis for {lat}, {lon}...")
    result = await analyzer.analyze_ndvi_only(lat, lon, "uz", bbox=bbox)
    
    print("\n✅ Result Summary:")
    print(result['summary'])
    
    if "Smart Estimate" in result['summary']:
        print("✅ Smart Fallback worked (Real Weather used or simulated)")
    elif "Sentinel" in result['summary']:
        print("✅ Sentinel data obtained")
        
    print("\n✅ Test Complete")

if __name__ == "__main__":
    asyncio.run(test_ndvi())
