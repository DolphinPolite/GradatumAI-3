# GradatumAI Testing Guide

## 🧪 Unit Testing Setup

### Installation

```powershell
pip install pytest pytest-cov
```

### Running Tests

```powershell
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_config.py

# Run specific test class
pytest tests/test_config.py::TestConfigLoader

# Run specific test
pytest tests/test_config.py::TestConfigLoader::test_load_valid_config

# Run with verbose output
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=. --cov-report=html

# Run and stop on first failure
pytest tests/ -x

# Run only failed tests from last run
pytest tests/ --lf
```

---

## 📋 Test Organization

```
tests/
├── __init__.py
├── test_config.py      ← Config loader tests (15 tests)
├── test_player.py      ← Player model tests (12 tests)
├── conftest.py         ← Pytest fixtures (add later)
└── integration/        ← Integration tests (add later)
    └── test_pipeline.py
```

---

## ✅ Current Test Coverage

### **test_config.py** (TestConfigLoader - 12 tests)
- ✅ Load valid YAML config
- ✅ Handle missing files
- ✅ Dot notation access (nested values)
- ✅ Default values
- ✅ Required values with error handling
- ✅ Section access
- ✅ Full dict export
- ✅ Config reload
- ✅ Singleton pattern
- ✅ Real main_config.yaml validation

**Coverage:** ConfigLoader utility fully tested

### **test_player.py** (TestPlayer - 16 tests)
- ✅ Player initialization
- ✅ Position tracking (add, update, clear)
- ✅ Ball possession state
- ✅ Bounding box management
- ✅ Data integrity
- ✅ Multiple player independence
- ✅ Color representation

**Coverage:** Player data model fully tested

---

## 🎯 Test Execution

### Example Output:

```
tests/test_config.py::TestConfigLoader::test_load_valid_config PASSED     [5%]
tests/test_config.py::TestConfigLoader::test_load_nonexistent_file PASSED  [10%]
tests/test_config.py::TestConfigLoader::test_get_nested_value PASSED       [15%]
...
tests/test_player.py::TestPlayerInitialization::test_player_creation PASSED [80%]
...

======================== 28 passed in 0.45s ========================
```

---

## 📊 Coverage Report

After running:
```powershell
pytest tests/ --cov=config --cov=Modules.IDrecognition.player --cov-report=html
```

Coverage report generated in `htmlcov/index.html`

**Current Target:**
- ConfigLoader: 100% coverage
- Player: 100% coverage
- Next: player_detection.py, ball_detect_track.py

---

## 🔧 Adding New Tests

### Template:

```python
import pytest
from module_to_test import Class

class TestMyFeature:
    """Test suite for MyFeature."""
    
    @pytest.fixture
    def sample_data(self):
        """Create sample data for tests."""
        return {"key": "value"}
    
    def test_basic_functionality(self, sample_data):
        """Test basic functionality."""
        result = some_function(sample_data)
        assert result == expected_value
    
    def test_error_handling(self):
        """Test error handling."""
        with pytest.raises(ValueError):
            invalid_function()
```

---

## 🚨 Common Issues

### ImportError: No module named 'config'
```powershell
# Make sure you're in project root:
cd c:\Users\LOQ\Downloads\GradatumAI-3-main\GradatumAI-3-main
pytest tests/
```

### ModuleNotFoundError: No module named 'Modules'
```powershell
# Add project root to PYTHONPATH:
$env:PYTHONPATH = $PWD
pytest tests/
```

### pytest not found
```powershell
pip install pytest pytest-cov
```

---

## 📈 Next Testing Phases

### Phase 3.2: Player Detection Tests
- [ ] FeetDetector initialization
- [ ] SIFT feature matching
- [ ] Team color classification
- [ ] IoU calculation accuracy

### Phase 3.3: Ball Tracking Tests
- [ ] Ball detection
- [ ] Template matching
- [ ] Circle detection
- [ ] Tracker state management

### Phase 3.4: Integration Tests
- [ ] Full pipeline (video → output)
- [ ] Config integration
- [ ] Module communication
- [ ] Performance benchmarks

---

## 💡 Best Practices

1. **One assertion per test** (usually)
2. **Descriptive test names** (test_xxx_xxx)
3. **Use fixtures for setup** (reusable data)
4. **Test error cases** (not just happy path)
5. **Keep tests independent** (no test order dependency)
6. **Use mocking** for external dependencies (video files, models)

---

## 📚 Resources

- Pytest docs: https://docs.pytest.org/
- Fixtures: https://docs.pytest.org/en/stable/fixture.html
- Coverage.py: https://coverage.readthedocs.io/

---

**Start testing:**
```powershell
pytest tests/ -v
```

Happy testing! 🚀
