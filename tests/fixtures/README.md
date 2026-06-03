# Test Fixtures

Sample JSON files representing realistic data at each stage of the pipeline.
Use these instead of upstream implementations when developing a stream in isolation.

| File | Type | Used by |
|------|------|---------|
| `sample_document.json` | `Document` | Streams 2, tests |
| `sample_module.json` | `LearningModule` | Streams 3, 5, tests |
| `sample_bank.json` | `QuestionBank` | Streams 3, 5, tests |
| `sample_result.json` | `QuizResult` | Streams 4, 5, tests |
| `sample_stats.json` | `ModuleStats` | Stream 5, tests |

## Loading a fixture

```python
import json
from pathlib import Path

from ingestion.models import Document

FIXTURES = Path(__file__).parent

doc = Document.from_json(FIXTURES / "sample_document.json" .read_text())
```
