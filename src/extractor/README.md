# Extractor Module

The Extractor module is responsible for extracting, parsing, and normalizing product specification fields from HTML pages. It implements the field definitions from `field_dictionary_v1.md` and provides robust extraction with multiple fallback strategies.

## Module Structure

```
src/extractor/
├── __init__.py                 # Module exports
├── field_registry.py           # Field code definitions and metadata
├── spec_extractor.py           # Main HTML extraction engine
├── normalizer.py               # Field value normalization
├── parsers/                    # Specialized parsers
│   ├── __init__.py
│   ├── resolution_parser.py    # Resolution parsing (WIDTHxHEIGHT)
│   ├── stream_parser.py        # Stream info parsing (FPS@Resolution)
│   └── range_parser.py         # Distance range parsing (meters)
└── tests/                      # Usage examples and tests
    ├── __init__.py
    └── test_example_usage.py
```

## Core Components

### 1. FieldRegistry (`field_registry.py`)

Centralized registry of all 19 Phase 1 field definitions from `field_dictionary_v1.md`.

**Key Classes:**
- `FieldDefinition`: Immutable dataclass containing field metadata
- `FieldRegistry`: Static methods for querying field definitions

**Usage:**
```python
from src.extractor import FieldRegistry

registry = FieldRegistry()

# Get field definition
field = registry.get_field("max_resolution")
print(field.field_name)  # "Max. Resolution"
print(field.required)    # True
print(field.canonical_unit)  # "px"

# Get all required fields
required = registry.get_required_field_codes()

# Find field by alias
field = registry.find_field_by_alias("最大分辨率")
```

### 2. SpecExtractor (`spec_extractor.py`)

HTML-based specification extractor with multiple extraction strategies.

**Extraction Strategies (in order of preference):**
1. **Label-based matching** (confidence: 1.0)
   - Finds field label in HTML structure
   - Extracts corresponding value from adjacent cell/element
   - Supports tables, lists, and description lists

2. **Position-based inference** (confidence: 0.7)
   - Infers value based on common positional patterns
   - Fallback when labels not found

3. **Regex fallback** (confidence: 0.6)
   - Pattern matching for known value formats
   - Last resort extraction

**Usage:**
```python
from src.extractor import SpecExtractor

extractor = SpecExtractor()

# Extract all fields from HTML
results, warnings = extractor.extract_all_fields(html_content, url)

# Access extraction results
for field_code, result in results.items():
    print(f"{field_code}: {result.normalized_value}")
    print(f"  Confidence: {result.confidence}")
    print(f"  Method: {result.extraction_method}")
```

### 3. Normalizer (`normalizer.py`)

Normalizes raw extracted values to canonical formats.

**Normalization Rules:**
- `max_resolution`: WIDTHxHEIGHT format (e.g., "4608x2592")
- `supplement_light_range`: Convert to meters (m)
- `aperture`: f/number format (e.g., "f/1.8")
- `main_stream_max_fps_resolution`: Structured format (e.g., "30fps (1920x1080)")
- `stream_count`: Integer value
- `interface_items`, `deep_learning_function_categories`: JSON arrays

**Usage:**
```python
from src.extractor import Normalizer

normalizer = Normalizer()

# Normalize a single field
normalized, unit, issues = normalizer.normalize(
    field_code="supplement_light_range",
    raw_value="100 ft"
)
print(normalized)  # "30.48m"
print(unit)        # "m"

# Batch normalize multiple fields
field_values = {
    "max_resolution": "4K (3840x2160)",
    "aperture": "F1.8",
}
results = normalizer.batch_normalize(field_values)
```

### 4. Specialized Parsers

#### ResolutionParser (`parsers/resolution_parser.py`)

Parses and validates resolution values.

**Features:**
- Extract width and height from various formats
- Calculate megapixels
- Determine aspect ratio
- Compare resolutions

**Usage:**
```python
from src.extractor import ResolutionParser

parser = ResolutionParser()

# Parse resolution
normalized = parser.normalize("2592P")  # "4608x2592"
mp = parser.calculate_megapixels(normalized)  # 12.4
aspect = parser.get_aspect_ratio(normalized)  # "16:9"

# Compare resolutions
result = parser.compare_resolutions("1920x1080", "4608x2592")
# result = -1 (first < second)
```

#### StreamParser (`parsers/stream_parser.py`)

Parses stream information (FPS and resolution).

**Features:**
- Extract FPS value
- Extract resolution
- Format as "<fps>fps (<width>x<height>)"
- Parse multiple streams from text

**Usage:**
```python
from src.extractor import StreamParser

parser = StreamParser()

# Parse stream info
normalized = parser.normalize("30fps (1920x1080)")
fps = parser.extract_fps("30fps (1920x1080)")  # 30
resolution = parser.extract_resolution("30fps (1920x1080)")  # (1920, 1080)

# Get structured JSON
structured = parser.to_structured("30fps (1920x1080)")
# {"fps_value": 30, "resolution_width": 1920, "resolution_height": 1080}
```

#### RangeParser (`parsers/range_parser.py`)

Parses distance ranges with unit conversion.

**Features:**
- Convert various units to meters (ft, inches, etc.)
- Handle single values and ranges
- Parse "up to" expressions
- Extract min/max values

**Usage:**
```python
from src.extractor import RangeParser

parser = RangeParser()

# Parse distance
normalized = parser.normalize("100 ft")  # "30.48m"
max_meters = parser.get_max_distance_in_meters("10-30m")  # 30.0
is_range = parser.is_range("10-30m")  # True

# Compare distances
result = parser.compare_distances("50m", "30m")
# result = 1 (first > second)
```

## Field Coverage

The extractor supports all 19 Phase 1 fields from `field_dictionary_v1.md`:

| Field Code | Field Name | Type | Canonical Unit |
|------------|------------|------|----------------|
| `image_sensor` | Image Sensor | text | n/a |
| `max_resolution` | Max. Resolution | text | px |
| `lens_type` | Lens Type | text | n/a |
| `aperture` | Aperture | text | f |
| `supplement_light_type` | Supplement Light Type | text | n/a |
| `supplement_light_range` | Supplement Light Range | number_or_text | m |
| `main_stream_max_fps_resolution` | Main Stream Max FPS@Resolution | text | fps+px |
| `stream_count` | Stream Count | integer | count |
| `interface_items` | Interface | list_text | n/a |
| `deep_learning_function_categories` | Deep Learning Function Categories | list_text | n/a |
| `approval_protection` | Approval.Protection | text | grade |
| `approval_anti_corrosion_protection` | Approval.Anti-Corrosion Protection | text | grade |

## Multi-Language Support

The extractor supports both English and Chinese field aliases:

```python
# English aliases
field = registry.find_field_by_alias("Max. Resolution")

# Chinese aliases
field = registry.find_field_by_alias("最大分辨率")

# Both return the same field definition
```

## Confidence Scoring

Each extraction includes a confidence score (0.0-1.0):

- **1.0**: Exact label match in structured table (highest confidence)
- **0.9-0.8**: Fuzzy label match or inferred from adjacent element
- **0.7**: Position-based inference
- **0.6**: Regex pattern match without label context
- **0.0**: Failed extraction

## Error Handling

The extractor is designed for resilience:

1. **Graceful degradation**: Single field parse failure doesn't stop entire extraction
2. **Fallback strategies**: Multiple extraction methods with decreasing confidence
3. **Issue tracking**: Each extraction result includes a list of issues/warnings
4. **Validation**: Parsers validate their own output

## Integration with Other Modules

The extractor module integrates with:

- **Agent-A (Core)**: Uses types from `src/core/types.py`
- **Agent-B (Storage)**: Provides normalized data for database storage
- **Agent-C/D (Adapters)**: Used by brand-specific adapters for field extraction
- **Agent-F (Quality)**: Confidence scores used for quality issue detection

## Running the Demo

To see the extractor in action:

```bash
cd /home/admin/code/auto-CompetitionAnalysis
python -m src.extractor.tests.test_example_usage
```

This will demonstrate:
- Field registry queries
- Resolution, stream, and range parsing
- Field normalization
- HTML-based extraction

## Testing Strategy

1. **Unit tests**: Test each parser with various input formats
2. **Integration tests**: Test full extraction pipeline with sample HTML
3. **Regression tests**: Re-run after parser updates to verify no degradation
4. **Multi-language tests**: Verify Chinese and English aliases work correctly

## Performance Considerations

- BeautifulSoup is used for HTML parsing (lxml backend for speed)
- Regex patterns are pre-compiled
- Field definitions are stored in memory (no I/O during extraction)
- List fields use JSON for efficient storage and comparison

## Future Enhancements (Phase 2+)

- Add more field codes beyond the initial 19
- Machine learning-based extraction for ambiguous cases
- Automated pattern learning from historical data
- Cross-brand field mapping (Hikvision ↔ Dahua)
