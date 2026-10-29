"""The one import point for the contracts of this package, as beethoven-qa's definition of done asks
(contracts on every public function, reviewed as the specification; CrossHair with Z3 proving them;
beartype outermost, the contracts beneath it).

Why a module of its own. beethoven-qa keeps its decorators behind `beethoven_qa.contracts` so that a
package's contracts always come from one checked place and the gate recognises them by one rule.
bordercall does not yet carry beethoven-qa's pinned copy (vendor/beethoven-qa, the consumer steps of
symphony-template's docs/setup/beethoven-qa.md), so this file is the one place that imports icontract
and beartype directly, the exception the definition of done allows a file that must stand alone;
when the copy is taken, this module becomes `from beethoven_qa.contracts import ...` and nothing
else in the package changes.

A lambda's parameter names match the function's; `result` is the return value; every condition
carries a plain sentence, which is what a reviewer reads.
"""
from __future__ import annotations

from beartype import beartype
from icontract import DBC, ViolationError, ensure, invariant, require

__all__ = ["DBC", "ViolationError", "beartype", "ensure", "invariant", "require"]
