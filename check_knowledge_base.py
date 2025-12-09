"""
Knowledge base checker for KIE Telegram Bot
This script displays all entries in the knowledge base
"""

import sys
import os
import json
# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def check_knowledge_base():
    """Display all entries in the knowledge base."""
    print("Checking knowledge base entries...")
    
    # Define the path to the entries file
    entries_file = os.path.join("knowledge_store", "entries.json")
    
    # Check if file exists
    if not os.path.exists(entries_file):
        print("No entries file found!")
        return
    
    # Load and display entries
    with open(entries_file, 'r', encoding='utf-8') as f:
        entries = json.load(f)
    
    print(f"Found {len(entries)} entries in the knowledge base:\n")
    
    for entry in entries:
        print(f"ID: {entry['id']}")
        print(f"Content: {entry['content']}")
        print(f"Author: {entry['author_id']}")
        print(f"Timestamp: {entry['timestamp']}")
        print("-" * 50)

if __name__ == "__main__":
    check_knowledge_base()