"""
Initial knowledge loader for KIE Telegram Bot
This script adds some example knowledge entries to get started
"""

import sys
import os
# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from knowledge_storage import KnowledgeStorage

def load_initial_knowledge():
    """Load initial knowledge entries into the storage."""
    print("Loading initial knowledge entries...")
    
    # Initialize storage
    storage = KnowledgeStorage()
    
    # Sample knowledge entries
    initial_entries = [
        "The capital of France is Paris",
        "Python is a high-level programming language",
        "The Earth revolves around the Sun",
        "Water boils at 100 degrees Celsius at sea level",
        "The Great Wall of China is visible from space (debateable)",
        "Photosynthesis is the process by which plants convert light energy into chemical energy",
        "The human body has 206 bones",
        "The Internet was developed in the late 20th century",
        "Quantum mechanics is a fundamental theory in physics that provides a description of the physical properties of nature at the scale of atoms and subatomic particles",
        "The Fibonacci sequence is a series of numbers where each number is the sum of the two preceding ones, usually starting with 0 and 1"
    ]
    
    # Add entries to storage
    for entry in initial_entries:
        success = storage.add_entry(entry, "system")
        if success:
            print(f"Added: {entry[:50]}...")
        else:
            print(f"Failed to add: {entry[:50]}...")
    
    print(f"\nLoaded {len(initial_entries)} initial knowledge entries!")
    print("The bot is now ready to use with some sample knowledge.")

if __name__ == "__main__":
    load_initial_knowledge()