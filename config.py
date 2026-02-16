import os
import yaml


def get_run_dir():
    """Return the active run directory from FAQQER_RUN_DIR env var, or '.' for backward compat."""
    return os.environ.get('FAQQER_RUN_DIR', '.')

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")

def _load():
    with open(_CONFIG_PATH, 'r') as f:
        return yaml.safe_load(f)

_cfg = _load()

# --- Models ---
HELPER_MODEL = _cfg['models']['helper']
SMART_MODEL = _cfg['models']['smart']
EMBEDDING_MODEL = _cfg['models']['embedding']

# --- Generation ---
TEMPERATURE = _cfg['temperature']

# --- Clustering ---
DEDUP_SIMILARITY_THRESHOLD = _cfg['clustering']['dedup_similarity_threshold']
MIN_CLUSTER_SIZE = _cfg['clustering']['min_cluster_size']
MAX_CLUSTER_SIZE = _cfg['clustering']['max_cluster_size']
NOISE_RECOVERY_THRESHOLD = _cfg['clustering']['noise_recovery_threshold']

# --- API ---
EMBEDDING_BATCH_SIZE = _cfg['api']['embedding_batch_size']
MAX_RETRIES = _cfg['api']['max_retries']
RETRY_DELAY = _cfg['api']['retry_delay']
TIMEOUT = _cfg['api']['timeout']
