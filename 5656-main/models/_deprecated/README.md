# Deprecated Model Sources

**DO NOT USE THESE FILES IN RUNTIME CODE**

All model definitions, pricing, and schemas are now consolidated in:
- **SSOT**: `/models/KIE_SOURCE_OF_TRUTH.json`

These files are kept for historical/debugging purposes only.

If you need to update model catalog:
1. Edit `KIE_SOURCE_OF_TRUTH.json` directly
2. Or use sync scripts that UPDATE `KIE_SOURCE_OF_TRUTH.json`

**Runtime code must ONLY read from `KIE_SOURCE_OF_TRUTH.json`**
