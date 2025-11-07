
import logging




import json
logger = logging.getLogger(__name__)




# Lazy singleton instance (created on first access)
_streamlit_app_instance = None

def get_streamlit_app() -> StreamlitApp:
    """Get or create the streamlit app singleton instance."""
    global _streamlit_app_instance
    if _streamlit_app_instance is None:
        _streamlit_app_instance = StreamlitApp()
    return _streamlit_app_instance


# For backward compatibility, create on first access
def __getattr__(name: str):
    if name == "streamlit_app":
        return get_streamlit_app()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
