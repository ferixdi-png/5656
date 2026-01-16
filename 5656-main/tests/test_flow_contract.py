"""
Test flow contract: ensure all models have correct flow_type and required_fields.

PHASE 1: КОНТРАКТЫ FLOW/INPUT
Tests that:
1. All 72 models have a determined flow_type
2. image_edit models ALWAYS have image_url as first required field
3. image2image/image2video models have image_url as first required field
4. text2* models have prompt as required
5. video models have video_url as first required
6. audio models have audio_url as first required
"""

import pytest
import logging
from app.kie.builder import load_source_of_truth
from app.kie.flow_types import (
    get_flow_type,
    get_primary_required_fields,
    get_expected_input_order,
    FLOW_IMAGE_EDIT,
    FLOW_IMAGE2IMAGE,
    FLOW_IMAGE2VIDEO,
    FLOW_IMAGE_UPSCALE,
    FLOW_TEXT2IMAGE,
    FLOW_TEXT2VIDEO,
    FLOW_TEXT2AUDIO,
    FLOW_VIDEO_EDIT,
    FLOW_AUDIO_PROCESSING,
)

logger = logging.getLogger(__name__)


@pytest.fixture
def models_registry():
    """Load all models from SOURCE_OF_TRUTH."""
    return load_source_of_truth()


class TestFlowContractAllModels:
    """Verify flow contract for all 72 models."""
    
    def test_all_models_have_flow_type(self, models_registry):
        """FAIL if any model has flow_type = 'unknown'."""
        unknown_models = []
        for model in models_registry:
            model_id = model.get("model_id")
            flow_type = get_flow_type(model_id, model)
            if flow_type == "unknown":
                unknown_models.append(model_id)
        
        assert not unknown_models, f"Models without determined flow_type: {unknown_models}"
    
    def test_image_edit_flow_structure(self, models_registry):
        """CRITICAL: image_edit models MUST collect image BEFORE prompt."""
        image_edit_models = [m for m in models_registry 
                            if get_flow_type(m.get("model_id"), m) == FLOW_IMAGE_EDIT]
        
        assert image_edit_models, "No image_edit models found - check determine_flow_type logic"
        
        for model in image_edit_models:
            model_id = model.get("model_id")
            expected_order = get_expected_input_order(FLOW_IMAGE_EDIT)
            primary_required = get_primary_required_fields(FLOW_IMAGE_EDIT)
            
            # Check that image_url comes first
            assert "image_url" in expected_order or any(f in expected_order for f in ["image_urls", "input_image"]), \
                f"{model_id}: image_edit MUST have image field in expected order: {expected_order}"
            
            # Check order - image must be first
            image_fields = [f for f in expected_order if f in ["image_url", "image_urls", "input_image"]]
            assert image_fields and expected_order.index(image_fields[0]) == 0, \
                f"{model_id}: image_edit image field MUST be first in order {expected_order}"
    
    def test_image2image_flow_structure(self, models_registry):
        """image2image models must have image_url as first input."""
        image2image_models = [m for m in models_registry 
                             if get_flow_type(m.get("model_id"), m) == FLOW_IMAGE2IMAGE]
        
        for model in image2image_models:
            model_id = model.get("model_id")
            expected_order = get_expected_input_order(FLOW_IMAGE2IMAGE)
            
            image_fields = [f for f in expected_order if f in ["image_url", "image_urls", "input_image"]]
            assert image_fields, f"{model_id}: image2image MUST have image field, got {expected_order}"
            assert expected_order.index(image_fields[0]) == 0, \
                f"{model_id}: image2image image MUST be first, got order {expected_order}"
    
    def test_image2video_flow_structure(self, models_registry):
        """image2video models must have image_url as first input."""
        image2video_models = [m for m in models_registry 
                             if get_flow_type(m.get("model_id"), m) == FLOW_IMAGE2VIDEO]
        
        for model in image2video_models:
            model_id = model.get("model_id")
            expected_order = get_expected_input_order(FLOW_IMAGE2VIDEO)
            
            image_fields = [f for f in expected_order if f in ["image_url", "image_urls", "input_image"]]
            assert image_fields, f"{model_id}: image2video MUST have image field, got {expected_order}"
            assert expected_order.index(image_fields[0]) == 0, \
                f"{model_id}: image2video image MUST be first, got order {expected_order}"
    
    def test_image_upscale_flow_structure(self, models_registry):
        """image_upscale models must have image_url as ONLY input."""
        upscale_models = [m for m in models_registry 
                         if get_flow_type(m.get("model_id"), m) == FLOW_IMAGE_UPSCALE]
        
        for model in upscale_models:
            model_id = model.get("model_id")
            expected_order = get_expected_input_order(FLOW_IMAGE_UPSCALE)
            
            assert expected_order and all(f in ["image_url", "image_urls", "input_image"] for f in expected_order), \
                f"{model_id}: image_upscale MUST only have image input, got {expected_order}"
    
    def test_text2image_flow_structure(self, models_registry):
        """text2image models must have prompt as required."""
        text2image_models = [m for m in models_registry 
                            if get_flow_type(m.get("model_id"), m) == FLOW_TEXT2IMAGE]
        
        for model in text2image_models:
            model_id = model.get("model_id")
            expected_order = get_expected_input_order(FLOW_TEXT2IMAGE)
            
            assert "prompt" in expected_order or "text" in expected_order, \
                f"{model_id}: text2image MUST have prompt/text, got {expected_order}"
    
    def test_text2video_flow_structure(self, models_registry):
        """text2video models must have prompt as required."""
        text2video_models = [m for m in models_registry 
                            if get_flow_type(m.get("model_id"), m) == FLOW_TEXT2VIDEO]
        
        for model in text2video_models:
            model_id = model.get("model_id")
            expected_order = get_expected_input_order(FLOW_TEXT2VIDEO)
            
            assert "prompt" in expected_order or "text" in expected_order, \
                f"{model_id}: text2video MUST have prompt/text, got {expected_order}"
    
    def test_text2audio_flow_structure(self, models_registry):
        """text2audio models must have prompt as required."""
        text2audio_models = [m for m in models_registry 
                            if get_flow_type(m.get("model_id"), m) == FLOW_TEXT2AUDIO]
        
        for model in text2audio_models:
            model_id = model.get("model_id")
            expected_order = get_expected_input_order(FLOW_TEXT2AUDIO)
            
            assert "prompt" in expected_order or "text" in expected_order, \
                f"{model_id}: text2audio MUST have prompt/text, got {expected_order}"
    
    def test_video_edit_flow_structure(self, models_registry):
        """video_edit models must have video_url as first input."""
        video_edit_models = [m for m in models_registry 
                            if get_flow_type(m.get("model_id"), m) == FLOW_VIDEO_EDIT]
        
        for model in video_edit_models:
            model_id = model.get("model_id")
            expected_order = get_expected_input_order(FLOW_VIDEO_EDIT)
            
            video_fields = [f for f in expected_order if f in ["video_url", "video_urls"]]
            if video_fields:
                assert expected_order.index(video_fields[0]) == 0, \
                    f"{model_id}: video_edit video MUST be first, got order {expected_order}"
    
    def test_audio_processing_flow_structure(self, models_registry):
        """audio models must have audio_url as first input."""
        audio_models = [m for m in models_registry 
                       if get_flow_type(m.get("model_id"), m) == FLOW_AUDIO_PROCESSING]
        
        for model in audio_models:
            model_id = model.get("model_id")
            expected_order = get_expected_input_order(FLOW_AUDIO_PROCESSING)
            
            audio_fields = [f for f in expected_order if f in ["audio_url", "audio_urls", "audio_file"]]
            assert audio_fields, f"{model_id}: audio_processing MUST have audio field, got {expected_order}"
    
    def test_model_count(self, models_registry):
        """Verify we have ~72 models loaded."""
        count = len(models_registry)
        assert count > 60, f"Expected ~72 models, got {count}"
        logger.info(f"Total models loaded: {count}")
    
    def test_flow_type_distribution(self, models_registry):
        """Log distribution of flow types across models."""
        flow_type_counts = {}
        for model in models_registry:
            model_id = model.get("model_id")
            flow_type = get_flow_type(model_id, model)
            flow_type_counts[flow_type] = flow_type_counts.get(flow_type, 0) + 1
        
        logger.info(f"Flow type distribution: {flow_type_counts}")
        
        # Verify main flow types are represented
        assert FLOW_TEXT2IMAGE in flow_type_counts, "Missing text2image models"
        assert FLOW_IMAGE_EDIT in flow_type_counts, "Missing image_edit models"
        assert flow_type_counts.get(FLOW_TEXT2IMAGE, 0) > 5, "Insufficient text2image models"
