"""
Pairing a request with the gateway event it is expected to produce.

An assertion installs its filter on the gateway *before* the request goes out, then
waits for the matching event, which closes the window where a fast reply could arrive
before anyone was listening for it. Anything expected but absent surfaces as a
`TimeoutError` on the assertion's deadline; anything present but wrong surfaces as an
`AssertionError` naming what was found.

`assert_request` sends and then waits. `assert_gateway` only waits, for the second and
later messages of an exchange that one request set off.
"""

from ._base import Assertion
from .autocomplete import AutoCompleteAssertion, AutoCompleteAssertionBuilder
from .message import (
    ButtonExpectation,
    DropdownExpectation,
    MessageAssertion,
    MessageAssertionBuilder
)
from .modal import ModalAssertion, ModalAssertionBuilder

__all__ = [
    "Assertion",
    "AutoCompleteAssertion",
    "AutoCompleteAssertionBuilder",
    "ButtonExpectation",
    "DropdownExpectation",
    "MessageAssertion",
    "MessageAssertionBuilder",
    "ModalAssertion",
    "ModalAssertionBuilder"
]