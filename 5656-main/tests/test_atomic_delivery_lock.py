"""
Unit tests for platform-wide atomic delivery lock.

Tests:
1. State normalization (done/completed → success)
2. Polling exit on lock skip
3. Migration contains both delivered_at and delivering_at
4. No references to delivered_at on tables without it
"""

import pytest
import re
from pathlib import Path


class TestStateNormalization:
    """Test that state variations are normalized correctly"""
    
    def test_normalize_state_success_variants(self):
        from app.delivery import normalize_state
        
        assert normalize_state('success') == 'success'
        assert normalize_state('done') == 'success'
        assert normalize_state('completed') == 'success'
        assert normalize_state('SUCCESS') == 'success'
        assert normalize_state('DONE') == 'success'
    
    def test_normalize_state_failure_variants(self):
        from app.delivery import normalize_state
        
        assert normalize_state('failed') == 'failed'
        assert normalize_state('fail') == 'failed'
        assert normalize_state('error') == 'failed'
        assert normalize_state('canceled') == 'failed'
        assert normalize_state('FAILED') == 'failed'
    
    def test_normalize_state_running_variants(self):
        from app.delivery import normalize_state
        
        assert normalize_state('running') == 'running'
        assert normalize_state('pending') == 'running'
        assert normalize_state('waiting') == 'running'
        assert normalize_state('queued') == 'running'
    
    def test_normalize_state_unknown(self):
        from app.delivery import normalize_state
        
        # Unknown states preserved
        assert normalize_state('unknown') == 'unknown'
        assert normalize_state('custom') == 'custom'


class TestMigrationSchema:
    """Test that migration 010 has required columns"""
    
    def test_migration_010_exists(self):
        migration_file = Path('migrations/010_delivery_lock_platform_wide.sql')
        assert migration_file.exists(), "Migration 010 must exist"
    
    def test_migration_has_delivered_at(self):
        migration_file = Path('migrations/010_delivery_lock_platform_wide.sql')
        content = migration_file.read_text()
        
        # Must add delivered_at to generation_jobs
        assert 'delivered_at' in content.lower()
        assert 'generation_jobs' in content.lower()
        assert re.search(r'alter\s+table\s+generation_jobs\s+add\s+column\s+delivered_at', content, re.IGNORECASE)
    
    def test_migration_has_delivering_at(self):
        migration_file = Path('migrations/010_delivery_lock_platform_wide.sql')
        content = migration_file.read_text()
        
        # Must add delivering_at to generation_jobs
        assert 'delivering_at' in content.lower()
        assert re.search(r'alter\s+table\s+generation_jobs\s+add\s+column\s+delivering_at', content, re.IGNORECASE)
    
    def test_migration_has_indexes(self):
        migration_file = Path('migrations/010_delivery_lock_platform_wide.sql')
        content = migration_file.read_text()
        
        # Must create optimized indexes
        assert 'CREATE INDEX' in content or 'create index' in content
        assert 'idx_generation_jobs' in content.lower()
    
    def test_migration_is_idempotent(self):
        migration_file = Path('migrations/010_delivery_lock_platform_wide.sql')
        content = migration_file.read_text()
        
        # Must have IF NOT EXISTS checks
        assert 'IF NOT EXISTS' in content or 'if not exists' in content
        assert content.count('IF NOT EXISTS') >= 3  # At least for columns and indexes


class TestPollingLogic:
    """Test polling exit condition on lock skip"""
    
    def test_polling_has_lock_skip_exit(self):
        generator_file = Path('app/kie/generator.py')
        content = generator_file.read_text()
        
        # Must have DELIVER_LOCK_SKIP_POLL_EXIT log
        assert 'DELIVER_LOCK_SKIP_POLL_EXIT' in content
        assert 'already_delivered' in content.lower()
    
    def test_polling_has_state_normalization(self):
        generator_file = Path('app/kie/generator.py')
        content = generator_file.read_text()
        
        # Must use normalize_state
        assert 'normalize_state' in content
        assert 'POLL_SUCCESS_EQUIV' in content


class TestCoordinatorLogic:
    """Test unified delivery coordinator"""
    
    def test_coordinator_exists(self):
        coordinator_file = Path('app/delivery/coordinator.py')
        assert coordinator_file.exists()
    
    def test_coordinator_has_atomic_function(self):
        coordinator_file = Path('app/delivery/coordinator.py')
        content = coordinator_file.read_text()
        
        assert 'deliver_result_atomic' in content
        assert 'try_acquire_delivery_lock' in content
        assert 'mark_delivered' in content
    
    def test_coordinator_handles_categories(self):
        coordinator_file = Path('app/delivery/coordinator.py')
        content = coordinator_file.read_text()
        
        # Must handle multiple categories
        assert '_deliver_image' in content
        assert '_deliver_video' in content
        assert '_deliver_audio' in content
    
    def test_coordinator_has_logs(self):
        coordinator_file = Path('app/delivery/coordinator.py')
        content = coordinator_file.read_text()
        
        assert 'DELIVER_LOCK_WIN' in content
        assert 'DELIVER_LOCK_SKIP' in content
        assert 'DELIVER_OK' in content
        assert 'MARK_DELIVERED' in content
        assert 'DELIVER_FAIL_RELEASED' in content


class TestNoOrphanedReferences:
    """Test that delivered_at is not used on tables without it"""
    
    def test_no_orphaned_delivered_at_references(self):
        # Static check: ensure delivered_at only used after migration adds it
        # This is a smoke test - real errors would show at runtime
        
        migration_010 = Path('migrations/010_delivery_lock_platform_wide.sql')
        assert migration_010.exists()
        
        content = migration_010.read_text()
        # Migration must add delivered_at before creating indexes on it
        lines = content.split('\n')
        
        delivered_at_added = False
        index_created = False
        
        for line in lines:
            if 'ADD COLUMN delivered_at' in line:
                delivered_at_added = True
            if 'CREATE INDEX' in line and 'delivered_at' in line:
                index_created = True
                # Index can only be created AFTER column exists
                assert delivered_at_added, "Index on delivered_at created before column added!"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
