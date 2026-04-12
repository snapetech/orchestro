from __future__ import annotations

import ast
import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


@dataclass(slots=True)
class VerificationResult:
    passed: bool
    verifier: str
    errors: list[str]
    warnings: list[str]
    metadata: dict | None = None


class Verifier(ABC):
    name: str

    @abstractmethod
    def verify(self, output: str, *, context: dict | None = None) -> VerificationResult: ...


_CODE_BLOCK_RE = re.compile(r"```(?:\w*)\n(.*?)```", re.DOTALL)


class PythonSyntaxVerifier(Verifier):
    name = "python-syntax"

    def verify(self, output: str, *, context: dict | None = None) -> VerificationResult:
        blocks = _CODE_BLOCK_RE.findall(output)
        if not blocks:
            blocks = [output]
        errors: list[str] = []
        warnings: list[str] = []
        for i, block in enumerate(blocks):
            block = block.strip()
            if not block:
                continue
            try:
                ast.parse(block)
            except SyntaxError as exc:
                label = f"block {i + 1}" if len(blocks) > 1 else "output"
                line_info = f"line {exc.lineno}" if exc.lineno else "unknown line"
                errors.append(f"{label}: {line_info}: {exc.msg}")
        return VerificationResult(
            passed=len(errors) == 0,
            verifier=self.name,
            errors=errors,
            warnings=warnings,
            metadata={"blocks_checked": len(blocks)},
        )


class JsonStructureVerifier(Verifier):
    name = "json-structure"

    def verify(self, output: str, *, context: dict | None = None) -> VerificationResult:
        errors: list[str] = []
        warnings: list[str] = []
        try:
            parsed = json.loads(output)
        except json.JSONDecodeError as exc:
            errors.append(f"invalid JSON: {exc.msg} (line {exc.lineno}, col {exc.colno})")
            return VerificationResult(
                passed=False,
                verifier=self.name,
                errors=errors,
                warnings=warnings,
            )
        expected_keys = (context or {}).get("expected_keys")
        if expected_keys and isinstance(parsed, dict):
            missing = [k for k in expected_keys if k not in parsed]
            if missing:
                errors.append(f"missing keys: {', '.join(missing)}")
        return VerificationResult(
            passed=len(errors) == 0,
            verifier=self.name,
            errors=errors,
            warnings=warnings,
            metadata={"type": type(parsed).__name__},
        )


_SQL_CODE_BLOCK_RE = re.compile(r"```(?:sql)\n(.*?)```", re.DOTALL)

_SQL_KEYWORD_RE = re.compile(
    r"\b(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|TRUNCATE|MERGE)\b",
    re.IGNORECASE,
)

_SQL_DANGEROUS_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bDROP\s+TABLE\b(?!.*\bIF\s+EXISTS\b)", re.IGNORECASE | re.DOTALL), "DROP TABLE without IF EXISTS"),
    (re.compile(r"\bDROP\s+DATABASE\b(?!.*\bIF\s+EXISTS\b)", re.IGNORECASE | re.DOTALL), "DROP DATABASE without IF EXISTS"),
    (re.compile(r"\bDELETE\s+FROM\b(?!.*\bWHERE\b)", re.IGNORECASE | re.DOTALL), "DELETE without WHERE clause"),
    (re.compile(r"\bTRUNCATE\b", re.IGNORECASE), "TRUNCATE statement"),
]

_SQL_SYNTAX_ERROR_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r",\s*\bFROM\b", re.IGNORECASE), "trailing comma before FROM"),
    (re.compile(r",\s*\bWHERE\b", re.IGNORECASE), "trailing comma before WHERE"),
    (re.compile(r",\s*\bGROUP\s+BY\b", re.IGNORECASE), "trailing comma before GROUP BY"),
    (re.compile(r",\s*\bORDER\s+BY\b", re.IGNORECASE), "trailing comma before ORDER BY"),
    (re.compile(r",\s*\bHAVING\b", re.IGNORECASE), "trailing comma before HAVING"),
    (re.compile(r",\s*\bLIMIT\b", re.IGNORECASE), "trailing comma before LIMIT"),
    (re.compile(r"\bSELECT\s*\bFROM\b", re.IGNORECASE), "SELECT with no columns before FROM"),
    (re.compile(r"\bUPDATE\s*\bWHERE\b", re.IGNORECASE), "UPDATE missing SET clause"),
    (re.compile(r"\bINSERT\s+INTO\s+\w+\s*\bSELECT\b(?!.*\bFROM\b)", re.IGNORECASE | re.DOTALL), "INSERT INTO ... SELECT without FROM"),
]


def _check_balanced_parens(sql: str) -> str | None:
    depth = 0
    in_single = False
    in_double = False
    for ch in sql:
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif not in_single and not in_double:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth < 0:
                    return "unmatched closing parenthesis"
    if depth > 0:
        return f"unclosed parenthesis ({depth} still open)"
    return None


def _check_unclosed_quotes(sql: str) -> str | None:
    in_single = False
    in_double = False
    for ch in sql:
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
    if in_single:
        return "unclosed single quote"
    if in_double:
        return "unclosed double quote"
    return None


class SqlParseVerifier(Verifier):
    name = "sql-parse"

    def verify(self, output: str, *, context: dict | None = None) -> VerificationResult:
        blocks = _SQL_CODE_BLOCK_RE.findall(output)
        if not blocks:
            if _SQL_KEYWORD_RE.search(output):
                blocks = [output]
            else:
                return VerificationResult(
                    passed=True,
                    verifier=self.name,
                    errors=[],
                    warnings=[],
                    metadata={"blocks_checked": 0},
                )
        errors: list[str] = []
        warnings: list[str] = []
        for i, block in enumerate(blocks):
            block = block.strip()
            if not block:
                continue
            label = f"block {i + 1}" if len(blocks) > 1 else "output"
            quote_err = _check_unclosed_quotes(block)
            if quote_err:
                errors.append(f"{label}: {quote_err}")
            paren_err = _check_balanced_parens(block)
            if paren_err:
                errors.append(f"{label}: {paren_err}")
            for pattern, msg in _SQL_SYNTAX_ERROR_PATTERNS:
                if pattern.search(block):
                    errors.append(f"{label}: {msg}")
            for pattern, msg in _SQL_DANGEROUS_PATTERNS:
                if pattern.search(block):
                    warnings.append(f"{label}: {msg}")
        return VerificationResult(
            passed=len(errors) == 0,
            verifier=self.name,
            errors=errors,
            warnings=warnings,
            metadata={"blocks_checked": len(blocks)},
        )


_AMBIGUOUS_COMMA_RE = re.compile(r"[\$€£¥]\s*\d+,\d{2}\b(?!\.\d)")
_FINANCIAL_HINT_RE = re.compile(
    r"[\$€£¥]|\b(total|subtotal|sum|balance|net|debit|credit|grand\s+total)\b",
    re.IGNORECASE,
)
AMOUNT_RE = re.compile(
    r"[\$€£¥]\s*-?[\d,]+\.?\d*|\b-?[\d,]+\.\d{2}\b",
    re.IGNORECASE,
)
_SUM_TOTAL_RE = re.compile(
    r"\b(total|subtotal|sum|grand\s+total|net)\b",
    re.IGNORECASE,
)
_DEBIT_LINE_RE = re.compile(r"\bdebit(s)?\b", re.IGNORECASE)
_CREDIT_LINE_RE = re.compile(r"\bcredit(s)?\b", re.IGNORECASE)
_BALANCE_LINE_RE = re.compile(r"\b(balance|net)\b", re.IGNORECASE)


def _parse_amount_token(raw: str) -> Decimal | None:
    s = raw.strip()
    s = re.sub(r"^[\$€£¥]\s*", "", s)
    s = s.replace(" ", "")
    if not s:
        return None
    neg = s.startswith("-")
    if neg:
        s = s[1:]
    if re.search(r",\d{2}$", s) and s.count(",") == 1 and "." not in s:
        s = s.replace(",", ".")
    elif "." in s and "," in s:
        if s.rindex(".") > s.rindex(","):
            s = s.replace(",", "")
        else:
            s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None
    return -d if neg else d


def _amounts_in_line(line: str) -> list[Decimal]:
    out: list[Decimal] = []
    for m in AMOUNT_RE.finditer(line):
        p = _parse_amount_token(m.group(0))
        if p is not None:
            out.append(p)
    return out


def _is_sum_total_line(line: str) -> bool:
    return bool(_SUM_TOTAL_RE.search(line) and _amounts_in_line(line))


def _paragraph_has_ledger_debit_credit(para: list[str]) -> bool:
    has_d = any(_DEBIT_LINE_RE.search(line) for line in para)
    has_c = any(_CREDIT_LINE_RE.search(line) for line in para)
    return has_d and has_c


def _paragraph_has_non_ledger_amounts(para: list[str]) -> bool:
    for line in para:
        if _DEBIT_LINE_RE.search(line) or _CREDIT_LINE_RE.search(line):
            continue
        if _amounts_in_line(line):
            return True
    return False


def _skip_sum_line_in_ledger(line: str, para: list[str]) -> bool:
    if not _paragraph_has_ledger_debit_credit(para):
        return False
    if re.search(r"\b(total|subtotal|sum|grand\s+total)\b", line, re.I):
        return False
    return bool(_BALANCE_LINE_RE.search(line))


def _paragraphs(lines: list[str]) -> list[list[str]]:
    blocks: list[list[str]] = []
    cur: list[str] = []
    for line in lines:
        if line.strip() == "":
            if cur:
                blocks.append(cur)
                cur = []
            continue
        cur.append(line)
    if cur:
        blocks.append(cur)
    return blocks


class BookkeepingVerifier(Verifier):
    name = "bookkeeping"

    def verify(self, output: str, *, context: dict | None = None) -> VerificationResult:
        errors: list[str] = []
        warnings: list[str] = []
        if not _FINANCIAL_HINT_RE.search(output):
            return VerificationResult(
                passed=True,
                verifier=self.name,
                errors=[],
                warnings=[],
                metadata={"skipped": True},
            )
        lines = output.splitlines()
        all_amounts: list[Decimal] = []
        for m in AMOUNT_RE.finditer(output):
            p = _parse_amount_token(m.group(0))
            if p is not None:
                all_amounts.append(p)
        for m in _AMBIGUOUS_COMMA_RE.finditer(output):
            warnings.append(
                f"ambiguous comma placement in {m.group(0)!r} "
                "(verify thousands vs decimal separator)",
            )
        if len(all_amounts) >= 3:
            qvals: dict[Decimal, int] = {}
            for a in all_amounts:
                qa = a.quantize(Decimal("0.01"))
                qvals[qa] = qvals.get(qa, 0) + 1
            for val, n in qvals.items():
                if n >= 3:
                    warnings.append(
                        f"amount {val} appears {n} times (possible copy-paste or duplicate entry)",
                    )
        for a in all_amounts:
            if a >= Decimal("10000") and a % Decimal("1000") == 0:
                warnings.append(
                    f"large round amount {a} may be an estimate rather than a calculated total",
                )
                break
        for pi, para in enumerate(_paragraphs(lines)):
            last_total_idx = -1
            for li, line in enumerate(para):
                if not _is_sum_total_line(line):
                    continue
                if _skip_sum_line_in_ledger(line, para):
                    continue
                if _paragraph_has_ledger_debit_credit(para) and not _paragraph_has_non_ledger_amounts(
                    para,
                ):
                    continue
                amounts = _amounts_in_line(line)
                if not amounts:
                    continue
                declared = amounts[-1]
                window = para[last_total_idx + 1 : li]
                sm = Decimal("0")
                if last_total_idx >= 0:
                    pl = para[last_total_idx]
                    if _is_sum_total_line(pl) and re.search(r"\bsubtotal\b", pl, re.I):
                        pam = _amounts_in_line(pl)
                        if pam:
                            sm += pam[-1]
                mixed_ledger = (
                    _paragraph_has_ledger_debit_credit(para)
                    and _paragraph_has_non_ledger_amounts(para)
                )
                for wl in window:
                    if _is_sum_total_line(wl) or _skip_sum_line_in_ledger(wl, para):
                        continue
                    if mixed_ledger and (
                        _DEBIT_LINE_RE.search(wl) or _CREDIT_LINE_RE.search(wl)
                    ):
                        continue
                    for a in _amounts_in_line(wl):
                        sm += a
                if window or sm != 0:
                    if abs(sm - declared) > Decimal("0.01"):
                        errors.append(
                            f"paragraph {pi + 1} line {li + 1}: "
                            f"total {declared} does not match sum of preceding items ({sm})",
                        )
                last_total_idx = li
            debits = Decimal("0")
            credits = Decimal("0")
            balance_amt: Decimal | None = None
            for line in para:
                amts = _amounts_in_line(line)
                if not amts:
                    continue
                has_d = bool(_DEBIT_LINE_RE.search(line))
                has_c = bool(_CREDIT_LINE_RE.search(line))
                if has_d and not has_c:
                    debits += sum(amts)
                elif has_c and not has_d:
                    credits += sum(amts)
                elif _BALANCE_LINE_RE.search(line) and not has_d and not has_c:
                    balance_amt = amts[-1]
            if (
                debits != 0
                and credits != 0
                and balance_amt is not None
                and abs(debits - credits - balance_amt) > Decimal("0.01")
            ):
                errors.append(
                    f"paragraph {pi + 1}: debits ({debits}) minus credits ({credits}) "
                    f"does not match balance ({balance_amt})",
                )
        return VerificationResult(
            passed=len(errors) == 0,
            verifier=self.name,
            errors=errors,
            warnings=warnings,
            metadata={"amounts_found": len(all_amounts)},
        )


class VerifierRegistry:
    def __init__(self) -> None:
        self._verifiers: dict[str, Verifier] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.register(PythonSyntaxVerifier())
        self.register(JsonStructureVerifier())
        self.register(SqlParseVerifier())
        self.register(BookkeepingVerifier())

    def register(self, verifier: Verifier) -> None:
        self._verifiers[verifier.name] = verifier

    def get(self, name: str) -> Verifier | None:
        return self._verifiers.get(name)

    def list_verifiers(self) -> list[dict]:
        return [
            {"name": v.name, "type": type(v).__name__}
            for v in sorted(self._verifiers.values(), key=lambda v: v.name)
        ]

    def verify_output(
        self,
        output: str,
        verifier_names: list[str],
        context: dict | None = None,
    ) -> list[VerificationResult]:
        results: list[VerificationResult] = []
        for name in verifier_names:
            verifier = self._verifiers.get(name)
            if verifier is None:
                results.append(VerificationResult(
                    passed=False,
                    verifier=name,
                    errors=[f"unknown verifier: {name}"],
                    warnings=[],
                ))
                continue
            results.append(verifier.verify(output, context=context))
        return results
