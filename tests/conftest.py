import sys
from pathlib import Path

# Allow `import config`, `import handlers`, etc. (flat layout, no package).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
