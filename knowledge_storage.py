"""
Knowledge storage module for KIE Telegram Bot
Handles storage and retrieval of knowledge entries
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Optional


class KnowledgeStorage:
    def __init__(self, storage_path: str = "./knowledge_store"):
        self.storage_path = storage_path
        self.entries_file = os.path.join(storage_path, "entries.json")
        self._initialized = False
        
    def ensure_storage_exists(self):
        """Ensure the storage directory and files exist (lazy initialization)."""
        if self._initialized:
            return
        os.makedirs(self.storage_path, exist_ok=True)
        
        # Create entries file if it doesn't exist
        if not os.path.exists(self.entries_file):
            with open(self.entries_file, 'w', encoding='utf-8') as f:
                json.dump([], f)
        self._initialized = True
    
    def add_entry(self, content: str, author_id: Optional[str] = None) -> bool:
        """Add a new knowledge entry."""
        try:
            # Load existing entries
            entries = self._load_entries()
            
            # Create new entry
            entry = {
                "id": len(entries) + 1,
                "content": content,
                "author_id": author_id,
                "timestamp": datetime.now().isoformat(),
                "tags": []  # Placeholder for future tagging functionality
            }
            
            # Add to entries
            entries.append(entry)
            
            # Save back to file
            self._save_entries(entries)
            
            return True
        except Exception as e:
            print(f"Error adding entry: {e}")
            return False
    
    def search_entries(self, query: str) -> List[Dict]:
        """Search for entries containing the query."""
        try:
            entries = self._load_entries()
            
            # Simple text search (to be improved with more advanced search later)
            query_lower = query.lower()
            results = []
            
            for entry in entries:
                if query_lower in entry["content"].lower():
                    results.append(entry)
            
            return results
        except Exception as e:
            print(f"Error searching entries: {e}")
            return []
    
    def get_all_entries(self) -> List[Dict]:
        """Get all knowledge entries."""
        try:
            return self._load_entries()
        except Exception as e:
            print(f"Error getting entries: {e}")
            return []
    
    def _load_entries(self) -> List[Dict]:
        """Load entries from the JSON file."""
        self.ensure_storage_exists()  # Lazy initialization
        try:
            if os.path.exists(self.entries_file):
                with open(self.entries_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            print(f"Error loading entries: {e}")
            return []
    
    def _save_entries(self, entries: List[Dict]):
        """Save entries to the JSON file."""
        self.ensure_storage_exists()  # Lazy initialization
        try:
            with open(self.entries_file, 'w', encoding='utf-8') as f:
                json.dump(entries, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving entries: {e}")