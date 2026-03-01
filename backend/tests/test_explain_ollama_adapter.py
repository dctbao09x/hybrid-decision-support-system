"""
Tests for backend/explain/stage4/ollama_adapter.py
Covers Stage4Config, ValidationResult, OutputValidator, Stage4Output.
"""
import pytest
from datetime import datetime, timezone
from backend.explain.stage4.ollama_adapter import (
    Stage4Config,
    ValidationResult,
    OutputValidator,
    Stage4Output,
    STAGE4_VERSION,
)


class TestStage4Config:
    """Tests for Stage4Config."""

    def test_default_values(self):
        """Test default configuration values."""
        config = Stage4Config()
        
        assert config.enabled is True
        assert config.model == "llama3.2:1b"
        assert config.timeout == 5.0
        assert config.retry == 2
        assert config.strict_validate is True
        assert config.max_output_length == 2000
        assert config.log_level == "full"
        assert isinstance(config.hallucination_keywords, list)

    def test_from_dict_with_stage4_key(self):
        """Test from_dict with stage4 nested key."""
        data = {
            "stage4": {
                "enabled": False,
                "model": "custom-model",
                "timeout": 10.0,
                "retry": 3,
                "strict_validate": False,
                "max_output_length": 1000,
                "log_level": "minimal",
                "log_dir": "custom_logs",
            }
        }
        config = Stage4Config.from_dict(data)
        
        assert config.enabled is False
        assert config.model == "custom-model"
        assert config.timeout == 10.0
        assert config.retry == 3
        assert config.strict_validate is False
        assert config.max_output_length == 1000
        assert config.log_level == "minimal"
        assert config.log_dir == "custom_logs"

    def test_from_dict_without_stage4_key(self):
        """Test from_dict without stage4 nested key."""
        data = {
            "enabled": False,
            "model": "phi3",
            "timeout": 8.0,
        }
        config = Stage4Config.from_dict(data)
        
        assert config.enabled is False
        assert config.model == "phi3"
        assert config.timeout == 8.0

    def test_from_dict_defaults(self):
        """Test from_dict uses defaults for missing keys."""
        data = {}
        config = Stage4Config.from_dict(data)
        
        assert config.enabled is True
        assert config.model == "llama3.2:1b"

    def test_hallucination_keywords_default(self):
        """Test default hallucination keywords exist."""
        config = Stage4Config()
        
        assert "tôi nghĩ" in config.hallucination_keywords
        assert "có thể" in config.hallucination_keywords
        assert "khuyên" in config.hallucination_keywords


class TestValidationResult:
    """Tests for ValidationResult."""

    def test_valid_result(self):
        """Test valid result."""
        result = ValidationResult(valid=True)
        
        assert result.valid is True
        assert result.issues == []
        assert bool(result) is True

    def test_invalid_result(self):
        """Test invalid result."""
        result = ValidationResult(valid=False, issues=["Error 1", "Error 2"])
        
        assert result.valid is False
        assert len(result.issues) == 2
        assert bool(result) is False

    def test_bool_conversion(self):
        """Test boolean conversion."""
        valid = ValidationResult(valid=True)
        invalid = ValidationResult(valid=False)
        
        assert valid  # Should be truthy
        assert not invalid  # Should be falsy


class TestOutputValidator:
    """Tests for OutputValidator."""

    @pytest.fixture
    def strict_config(self):
        """Create strict validation config."""
        return Stage4Config(strict_validate=True)

    @pytest.fixture
    def lenient_config(self):
        """Create lenient validation config."""
        return Stage4Config(strict_validate=False)

    @pytest.fixture
    def strict_validator(self, strict_config):
        """Create strict validator."""
        return OutputValidator(strict_config)

    @pytest.fixture
    def lenient_validator(self, lenient_config):
        """Create lenient validator."""
        return OutputValidator(lenient_config)

    def test_validate_empty_output(self, strict_validator):
        """Test validation rejects empty output."""
        result = strict_validator.validate("", "Original text", ["reason1"])
        
        assert result.valid is False
        assert "empty" in result.issues[0].lower()

    def test_validate_whitespace_only_output(self, strict_validator):
        """Test validation rejects whitespace-only output."""
        result = strict_validator.validate("   \n\t  ", "Original text", ["reason1"])
        
        assert result.valid is False

    def test_validate_too_long_output_strict(self, strict_config):
        """Test validation rejects too-long output in strict mode."""
        config = Stage4Config(strict_validate=True, max_output_length=50)
        validator = OutputValidator(config)
        
        long_output = "A" * 100
        result = validator.validate(long_output, "Short", [])
        
        assert result.valid is False
        assert any("too long" in issue.lower() for issue in result.issues)

    def test_validate_too_long_output_lenient(self, lenient_config):
        """Test validation allows too-long output in lenient mode."""
        config = Stage4Config(strict_validate=False, max_output_length=50)
        validator = OutputValidator(config)
        
        long_output = "A" * 100
        result = validator.validate(long_output, "Short", [])
        
        # Lenient mode should still pass
        assert result.valid is True
        # But should have issues
        assert len(result.issues) > 0

    def test_validate_hallucination_keywords_strict(self, strict_validator):
        """Test validation detects hallucination keywords in strict mode."""
        result = strict_validator.validate(
            "Tôi nghĩ bạn nên làm như vậy",
            "Bạn làm như vậy",
            []
        )
        
        assert result.valid is False
        assert any("hallucination" in issue.lower() for issue in result.issues)

    def test_validate_hallucination_keywords_lenient(self, lenient_validator):
        """Test validation notes hallucination keywords in lenient mode."""
        result = lenient_validator.validate(
            "Tôi nghĩ bạn nên làm như vậy",
            "Bạn làm như vậy",
            []
        )
        
        # Lenient should still pass but note the issue
        assert result.valid is True
        assert len(result.issues) > 0

    def test_validate_valid_output(self, strict_validator):
        """Test validation accepts valid output."""
        result = strict_validator.validate(
            "Phân tích kỹ năng toán học",
            "Phân tích kỹ năng toán",
            ["toán học"]
        )
        
        assert result.valid is True

    def test_extract_keywords(self, strict_validator):
        """Test keyword extraction."""
        keywords = strict_validator._extract_keywords(
            "Bạn có kỹ năng toán học rất tốt"
        )
        
        # Should filter out stopwords like "bạn", "có"
        assert "kỹ" in keywords or "năng" in keywords or "toán" in keywords

    def test_validate_too_many_new_words_strict(self, strict_config):
        """Test validation rejects too many new words in strict mode."""
        validator = OutputValidator(strict_config)
        
        original = "abc def"
        llm_output = "abc def ghi jkl mno pqr stu vwx yza bcd efg hij"
        
        result = validator.validate(llm_output, original, [])
        
        # The new content check should flag this
        assert result.valid is False or len(result.issues) > 0


class TestStage4Output:
    """Tests for Stage4Output."""

    @pytest.fixture
    def sample_output(self):
        """Create sample Stage4Output."""
        return Stage4Output(
            trace_id="trace-001",
            career="Software Engineer",
            reasons=["Strong logic", "Math skills"],
            confidence=0.85,
            raw_text="Raw text from Stage 3",
            llm_text="Formatted text by Ollama",
            used_llm=True,
            ollama_model="llama3.2:1b",
            latency_ms=150.5,
        )

    def test_output_creation(self, sample_output):
        """Test output creation."""
        assert sample_output.trace_id == "trace-001"
        assert sample_output.career == "Software Engineer"
        assert len(sample_output.reasons) == 2
        assert sample_output.confidence == 0.85
        assert sample_output.used_llm is True
        assert sample_output.fallback is False

    def test_output_version(self, sample_output):
        """Test output has correct version."""
        assert sample_output.stage4_version == STAGE4_VERSION

    def test_output_timestamp_auto_generated(self):
        """Test timestamp is auto-generated."""
        output = Stage4Output(
            trace_id="test",
            career="Test",
            reasons=[],
            confidence=0.5,
            raw_text="raw",
            llm_text="formatted",
            used_llm=True,
        )
        
        assert output.timestamp != ""
        # Should be valid ISO timestamp
        datetime.fromisoformat(output.timestamp.replace("Z", "+00:00"))

    def test_to_dict(self, sample_output):
        """Test to_dict conversion."""
        data = sample_output.to_dict()
        
        assert data["trace_id"] == "trace-001"
        assert data["career"] == "Software Engineer"
        assert data["reasons"] == ["Strong logic", "Math skills"]
        assert data["confidence"] == 0.85
        assert data["raw_text"] == "Raw text from Stage 3"
        assert data["llm_text"] == "Formatted text by Ollama"
        assert data["used_llm"] is True
        assert data["fallback"] is False
        assert "meta" in data
        assert data["meta"]["ollama_model"] == "llama3.2:1b"
        assert data["meta"]["latency_ms"] == 150.5

    def test_to_api_response(self, sample_output):
        """Test to_api_response conversion."""
        data = sample_output.to_api_response()
        
        assert data["trace_id"] == "trace-001"
        assert data["career"] == "Software Engineer"
        assert data["used_llm"] is True
        # API response should not include meta
        assert "meta" not in data

    def test_output_fallback_mode(self):
        """Test output in fallback mode."""
        output = Stage4Output(
            trace_id="fallback-test",
            career="General",
            reasons=["Fallback reason"],
            confidence=0.5,
            raw_text="Original",
            llm_text="Original",  # Same as raw in fallback
            used_llm=False,
            fallback=True,
        )
        
        assert output.fallback is True
        assert output.used_llm is False

    def test_output_validation_issues(self):
        """Test output with validation issues."""
        output = Stage4Output(
            trace_id="validation-test",
            career="Engineer",
            reasons=["reason"],
            confidence=0.8,
            raw_text="raw",
            llm_text="formatted",
            used_llm=True,
            validation_issues=["Issue 1", "Issue 2"],
        )
        
        assert len(output.validation_issues) == 2

    def test_output_latency_rounding(self):
        """Test latency is rounded in to_dict."""
        output = Stage4Output(
            trace_id="test",
            career="Test",
            reasons=[],
            confidence=0.5,
            raw_text="raw",
            llm_text="formatted",
            used_llm=True,
            latency_ms=123.456789,
        )
        
        data = output.to_dict()
        assert data["meta"]["latency_ms"] == 123.46
