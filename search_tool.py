"""
Interactive search tool for KIE Telegram Bot
Allows command-line testing of the search functionality
"""

import sys
import os
# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from knowledge_storage import KnowledgeStorage

def interactive_search():
    """Run an interactive search session."""
    print("KIE Knowledge Base Search Tool")
    print("Type 'quit' or 'exit' to exit")
    print("-" * 40)
    
    # Initialize storage
    storage = KnowledgeStorage()
    
    while True:
        query = input("\nEnter search query: ").strip()
        
        if query.lower() in ['quit', 'exit', 'q']:
            print("Exiting...")
            break
        
        if not query:
            print("Please enter a search query.")
            continue
        
        # Search for entries
        results = storage.search_entries(query)
        
        if results:
            print(f"\nFound {len(results)} result(s) for '{query}':")
            print("-" * 30)
            for i, result in enumerate(results, 1):
                print(f"{i}. ID: {result['id']}")
                print(f"   Content: {result['content']}")
                print(f"   Author: {result['author_id']}")
                print(f"   Date: {result['timestamp'][:19]}")  # Just the date part
                print()
        else:
            print(f"\nNo results found for '{query}'")
            print("You can add knowledge using the bot with /add command")

if __name__ == "__main__":
    interactive_search()