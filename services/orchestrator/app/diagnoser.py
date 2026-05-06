import hashlib
import re
from dataclasses import dataclass
from typing import Any

# Defining diagnosis class and making instances immutable to keep
# the error message/details intact
@dataclass(frozen=True)
class Diagnosis:
    """
    Diagnosis Class saving immutable details of each error/incident_type.

    Attributes:
        incident_type (str): Name of the incident/category of incidents from predefined ones.
        confidence (float): Confidence percentage that the error/incident falls
            in the particular category.
        error_signature (str): Optional, more details about the error/incident.
        summary (str): System generated/understood details of the error/incident.
    """
    incident_type: str
    confidence: float
    error_signature: str | None
    summary: str

# Predefined errors/patterns that help the system understand what type of error it is.
# Saved in list of tuple format.
_SIG_PATTERNS = [
    # Runtime / Spark related general errors
    (re.compile(r"(outofmemory|gc overhead|executor.*lost|executorlostfailure|killed by yarn)", re.I), "RUNTIME_FAILURE", 0.85),
    (re.compile(r"(timeout|timed out|connection reset|network is unreachable|temporarily unavailable)", re.I), "RUNTIME_FAILURE", 0.75),

    # Schema drift errors
    (re.compile(r"(cannot resolve|unknown field|no such struct field|schema.*mismatch|incompatible schema|cannot cast)", re.I), "SCHEMA_DRIFT", 0.90),

    # Data quality errors
    (re.compile(r"(dq failed|great expectations|deequ|expectation failed|null spike|duplicate spike|invalid range)", re.I), "DQ_REGRESSION", 0.85),

    # Late data / missing partition errors
    (re.compile(r"(missing partition|no files found|file not found|path does not exist|late data|upstream not run)", re.I), "LATE_DATA", 0.80),
]

# Removing numbers and unwanted content from error message.
# Helps the system in understanding the error better.
def _normalise_error(text: str) -> str:
    """
    Function to remove all unwanted data/content from error message.

    Args:
        text (str): Decrypted error message in string format.

    Returns:
        str: Error message striped of irrelevant data. Length of returned
            can be increased/decreased according to user and system needs.
    """

    # remove timestamps / ids / run numbers to make error message stable and system readable.
    t = text.strip()
    t = re.sub(r"\b\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?\b", "<ts>", t)
    t = re.sub(r"\b[0-9a-f]{8,}\b", "<hex>", t, flags=re.I)
    t = re.sub(r"\b\d+\b", "<n>", t)
    t = re.sub(r"\s+", " ", t)
    return t[:600] # increase the character length depending upon usecase

# Decrypting the error messages
def _hash_sig(text: str) -> str:
    """
    Function to decrypt the error messages into a string.

    Args:
        text (str): Binary/encrypted error message.

    Returns:
        str: Full error message decrypted.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

# Main diagnose function
def diagnose(event_type: str, payload: dict[str, Any]) -> Diagnosis:
    """
    Main diagnosis function that calls all other functions, to better understand
    the type of error and return all impot information related to the error.

    Args:
        event_type (str): Initial decrypted error message.
        payload (dict[str, Any]): Original error dictionay or string that containes
            all the encrypted details.

    Returns:
        Diagnosis: Returns a Diagnosis class instance with all the details of the error saved.
    """

    err = ""
    if isinstance(payload, dict):
        err = str(payload.get("error") or payload.get("message") or payload.get("exception") or "")

    base_summary = f"{event_type}"
    if err:
        norm = _normalise_error(err)
        sig = _hash_sig(norm)
    else:
        norm = ""
        sig = None

    # Default mapping if event_type already tells us important details
    if event_type == "LATE_DATA":
        return Diagnosis("LATE_DATA", 0.80, sig, "Late or missing upstream data detected.")
    if event_type == "DQ_FAILED":
        return Diagnosis("DQ_REGRESSION", 0.85, sig, "Data quality checks failed.")

    # Identifying error from previously defined _SIG_PATTERNS
    for pattern, itype, conf in _SIG_PATTERNS:
        if err and pattern.search(err):
            summary = f"{itype}: {err[:160]}".strip()
            return Diagnosis(itype, conf, sig, summary)

    # Fallback
    summary = (err[:160] if err else base_summary)
    return Diagnosis("UNKNOWN", 0.55, sig, summary)
