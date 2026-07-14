"""The backend-adapter layer (ADR-0005 D2).

Loads the frozen, vendored Phase-1 backend contract and exposes it as
structured, queryable data; derives each template's ``edit_contract`` from
the contract + that template's intent record, so ``edit_contract`` stays a
mechanical, re-derivable *view* rather than a second place semantic decisions
live. See ``contract_loader.py`` (loading), ``intent.py`` (the intent-record
layer), ``derive.py`` (the ``edit_contract`` projection), and ``checks.py``
(the enforcement checks wired into ``tools/validate.py``).
"""
