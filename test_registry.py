#!/usr/bin/env python3
"""
Test script for registry analyzer functionality
"""

import sys
import os

# Add the current directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.registry_analyzer import RegistryAnalyzer

def test_registry_analyzer():
    """Test the registry analyzer service"""
    print("Testing Registry Analyzer Service...")
    
    # Create analyzer instance
    analyzer = RegistryAnalyzer()
    
    # Test getting available hives
    print("\n1. Testing get_available_hives()...")
    hives = analyzer.get_available_hives()
    print(f"Available hives: {len(hives)} found")
    for hive in hives[:5]:  # Show first 5
        print(f"  - {hive}")
    
    # Test path resolution
    print(f"\n2. Testing tool paths...")
    print(f"RawCopy path: {analyzer.rawcopy_path}")
    print(f"RLA path: {analyzer.rla_path}")
    
    # Check if tools exist
    print(f"\n3. Checking tool availability...")
    print(f"RawCopy exists: {os.path.exists(analyzer.rawcopy_path)}")
    print(f"RLA exists: {os.path.exists(analyzer.rla_path)}")
    
    print("\nRegistry Analyzer test completed!")

if __name__ == "__main__":
    test_registry_analyzer() 