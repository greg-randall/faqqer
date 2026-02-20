import os
import copy
import yaml


_PROMPTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts.yaml")

def _load():
    with open(_PROMPTS_PATH, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

_prompts = _load()


def _resolve(dotted_key):
    """Walk into the nested dict using a dotted key like 'enrich_faq.audit.system'."""
    node = _prompts
    for part in dotted_key.split('.'):
        node = node[part]
    return node


def get(dotted_key, **kwargs):
    """Return a prompt string, optionally formatted with kwargs.

    Example:
        get("enrich_faq.audit.system")
        get("enrich_faq.classify.system", taxonomy='["A","B"]')
    """
    value = _resolve(dotted_key)
    if kwargs:
        return value.format(**kwargs)
    return value


def get_tools(dotted_key):
    """Return a deep copy of the tools list at the given path.

    Always returns a copy so callers can safely mutate (e.g. inject enums).
    """
    return copy.deepcopy(_resolve(dotted_key + '.tools'))


def get_tool_choice(dotted_key):
    """Return the tool_choice dict at the given path."""
    return _resolve(dotted_key + '.tool_choice')
