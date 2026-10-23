"""Conservative version semantics. Unsupported data returns unknown, never lexical order."""
from __future__ import annotations

from dataclasses import dataclass
import re

_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$")
_PYTHON = re.compile(r"^(?:(\d+)!)?(\d+(?:\.\d+)*)(?:(a|b|rc)(\d+))?(?:\.post(\d+))?(?:\.dev(\d+))?(?:\+([a-z0-9]+(?:\.[a-z0-9]+)*))?$", re.IGNORECASE)


def _python_parts(value):
    if not isinstance(value, str) or len(value) > 160:
        return None
    match = _PYTHON.fullmatch(value)
    if match is None:
        return None
    epoch, release, phase, pre, post, dev, local = match.groups()
    release_parts = tuple(int(v) for v in release.split("."))
    while len(release_parts) > 1 and release_parts[-1] == 0:
        release_parts = release_parts[:-1]
    phase_parts = ({"a": 0, "b": 1, "rc": 2}[phase.lower()], int(pre)) if phase else ((-1, 0) if dev is not None and post is None else (3, 0))
    local_parts = tuple((1, int(part)) if part.isdecimal() else (0, part.lower()) for part in local.split(".")) if local else ()
    return (int(epoch or 0), release_parts, phase_parts, int(post) if post else -1, (0, int(dev)) if dev is not None else (1, 0), local_parts)


@dataclass(frozen=True)
class SemVer:
    major: int
    minor: int
    patch: int
    prerelease: tuple[str, ...] = ()

    @classmethod
    def parse(cls, value: object) -> "SemVer | None":
        if not isinstance(value, str) or len(value) > 160:
            return None
        match = _SEMVER.fullmatch(value)
        if match is None:
            return None
        pre = tuple(match.group(4).split(".")) if match.group(4) else ()
        if any(part.isdecimal() and len(part) > 1 and part.startswith("0") for part in pre):
            return None
        return cls(*(int(match.group(i)) for i in (1, 2, 3)), pre)

    def compare(self, other: "SemVer") -> int:
        left, right = (self.major, self.minor, self.patch), (other.major, other.minor, other.patch)
        if left != right:
            return (left > right) - (left < right)
        if not self.prerelease or not other.prerelease:
            return (not self.prerelease) - (not other.prerelease)
        for left_part, right_part in zip(self.prerelease, other.prerelease):
            if left_part == right_part:
                continue
            if left_part.isdecimal() and right_part.isdecimal():
                return (int(left_part) > int(right_part)) - (int(left_part) < int(right_part))
            if left_part.isdecimal() != right_part.isdecimal():
                return -1 if left_part.isdecimal() else 1
            return (left_part > right_part) - (left_part < right_part)
        return (len(self.prerelease) > len(other.prerelease)) - (len(self.prerelease) < len(other.prerelease))


def normalize_ecosystem(value: object) -> str:
    return {"cargo": "rust", "rust": "rust", "crates.io": "rust", "pypi": "python", "pip": "python",
            "python": "python", "debian": "debian", "deb": "debian", "rpm": "rpm",
            "linux": "linux", "linux kernel": "linux", "semver": "semver"}.get(str(value).lower(), str(value).lower())


def _debian_part(left: str, right: str) -> int:
    # Debian Policy 5.6.12: tilde sorts before everything, then end, letters, others.
    def order(char: str) -> int:
        if char == "~":
            return -1
        if not char:
            return 0
        return ord(char) if char.isalpha() and char.isascii() else ord(char) + 256
    i = j = 0
    while i < len(left) or j < len(right):
        while (i < len(left) and not left[i].isdigit()) or (j < len(right) and not right[j].isdigit()):
            a = left[i] if i < len(left) and not left[i].isdigit() else ""
            b = right[j] if j < len(right) and not right[j].isdigit() else ""
            if order(a) != order(b):
                return (order(a) > order(b)) - (order(a) < order(b))
            i += bool(a)
            j += bool(b)
        start_i, start_j = i, j
        while i < len(left) and left[i].isdigit():
            i += 1
        while j < len(right) and right[j].isdigit():
            j += 1
        a, b = left[start_i:i].lstrip("0"), right[start_j:j].lstrip("0")
        if len(a) != len(b):
            return (len(a) > len(b)) - (len(a) < len(b))
        if a != b:
            return (a > b) - (a < b)
    return 0


def compare_versions(left: object, right: object, ecosystem: str = "rust") -> int | None:
    ecosystem = normalize_ecosystem(ecosystem)
    if ecosystem in {"rust", "semver"}:
        a, b = SemVer.parse(left), SemVer.parse(right)
        return a.compare(b) if a is not None and b is not None else None
    if ecosystem == "python":
        a, b = _python_parts(left), _python_parts(right)
        return (a > b) - (a < b) if a is not None and b is not None else None
    if ecosystem == "debian":
        def parts(value):
            if not isinstance(value, str) or len(value) > 160 or not re.fullmatch(r"(?:\d+:)?[0-9][A-Za-z0-9.+~:-]*", value):
                return None
            epoch, rest = value.split(":", 1) if ":" in value else ("0", value)
            if not epoch.isdecimal():
                return None
            upstream, revision = rest.rsplit("-", 1) if "-" in rest else (rest, "0")
            return int(epoch), upstream, revision
        a, b = parts(left), parts(right)
        if a is None or b is None:
            return None
        return ((a[0] > b[0]) - (a[0] < b[0])) or _debian_part(a[1], b[1]) or _debian_part(a[2], b[2])
    # RPM/Linux vendor versions require their own semantics and provenance.
    return None


def matches_python_requirement(version: str, requirement: str) -> bool | None:
    """Canonical PEP 440 public-version comparisons. Unsupported syntax stays unknown.

    Advisory pre-release policy is not dependency installation policy. Where an
    exclusive bound would special-case a pre/post release of that same version,
    return unknown so that this cannot become a false not-applicable conclusion.
    """
    parsed = _python_parts(version)
    if parsed is None or not isinstance(requirement, str) or len(requirement) > 256:
        return None
    answers = []
    for raw in requirement.split(","):
        match = re.fullmatch(r"\s*(==|!=|>=|<=|>|<|~=)\s*([A-Za-z0-9!.+*]+)\s*", raw)
        if match is None:
            return None
        op, target = match.groups()
        if target.endswith(".*") and op in {"==", "!="}:
            prefix = target[:-2]
            if not re.fullmatch(r"\d+(?:\.\d+)*", prefix):
                return None
            prefix_parts = tuple(int(v) for v in prefix.split("."))
            release = parsed[1] + (0,) * max(0, len(prefix_parts) - len(parsed[1]))
            matched = parsed[0] == 0 and release[:len(prefix_parts)] == prefix_parts
            answers.append(matched if op == "==" else not matched)
            continue
        target_parts = _python_parts(target)
        if target_parts is None or target_parts[-1]:
            return None
        # Specifiers ignore the candidate local label when the bound has none.
        public = (*parsed[:-1], ())
        comparison = (public > target_parts) - (public < target_parts)
        if op in {"<", ">"} and parsed[:2] == target_parts[:2] and (parsed[2] != target_parts[2] or parsed[3] != target_parts[3]):
            return None
        if op == "~=":
            release_text = re.match(r"(?:\d+!)?(\d+(?:\.\d+)+)", target)
            if release_text is None:
                return None
            prefix = tuple(int(v) for v in release_text.group(1).split("."))[:-1]
            release = parsed[1] + (0,) * max(0, len(prefix) - len(parsed[1]))
            answers.append(comparison >= 0 and parsed[0] == target_parts[0] and release[:len(prefix)] == prefix)
        else:
            answers.append({"==": comparison == 0, "!=": comparison != 0, ">=": comparison >= 0, "<=": comparison <= 0, ">": comparison > 0, "<": comparison < 0}[op])
    return all(answers)


def affected_by_osv(version: object, affected: dict, ecosystem: str = "rust") -> bool | None:
    """Evaluate OSV exact versions and supported ranges; unknown range types stay unknown."""
    if not isinstance(affected, dict) or not isinstance(version, str):
        return None
    exact = affected.get("versions", [])
    if not isinstance(exact, list) or not all(isinstance(v, str) for v in exact):
        return None
    if version in exact:
        return True
    ranges = affected.get("ranges", [])
    if not isinstance(ranges, list):
        return None
    unknown = False
    for value in ranges:
        if not isinstance(value, dict) or value.get("type") not in {"SEMVER", "ECOSYSTEM"}:
            unknown = True
            continue
        range_ecosystem = "semver" if value["type"] == "SEMVER" else ecosystem
        events = value.get("events", [])
        if not isinstance(events, list) or not events:
            unknown = True
            continue
        inside = False
        valid = True
        for event in events:
            if not isinstance(event, dict) or len(event) != 1:
                valid = False
                break
            kind, boundary = next(iter(event.items()))
            if kind == "introduced" and boundary == "0":
                inside = True
                continue
            comparison = compare_versions(version, boundary, range_ecosystem)
            if comparison is None:
                valid = False
                break
            if kind == "introduced":
                inside = comparison >= 0
            elif kind in {"fixed", "limit"}:
                if inside and comparison < 0:
                    break
                inside = False
            elif kind == "last_affected":
                if inside and comparison <= 0:
                    break
                inside = False
            else:
                valid = False
                break
        if valid and inside:
            return True
        unknown |= not valid
    if unknown:
        return None
    return False if exact or ranges else None


def matches_cargo_requirement(version: str, requirement: str) -> bool | None:
    """Cargo dependency requirements. This does not prove an installed version."""
    parsed = SemVer.parse(version)
    if parsed is None or not isinstance(requirement, str) or len(requirement) > 256:
        return None
    if "||" in requirement:
        return None
    results = []
    prerelease_allowed = not parsed.prerelease
    for raw in requirement.split(","):
        term = raw.strip()
        match = re.fullmatch(r"(\^|~|>=|<=|>|<|=)?\s*(\d+|\*)(?:\.(\d+|\*))?(?:\.(\d+|\*))?(-[0-9A-Za-z.-]+)?", term)
        if match is None:
            return None
        op, major, minor, patch, pre = match.groups()
        if major == "*":
            if op or minor or patch or pre:
                return None
            results.append(True)
            continue
        count = 1 + (minor is not None and minor != "*") + (patch is not None and patch != "*")
        if minor == "*" and patch is not None or patch == "*" and pre:
            return None
        core = (int(major), int(minor) if minor not in {None, "*"} else 0, int(patch) if patch not in {None, "*"} else 0)
        target = SemVer.parse("%d.%d.%d%s" % (*core, pre or ""))
        if target is None:
            return None
        if target.prerelease and core == (parsed.major, parsed.minor, parsed.patch):
            prerelease_allowed = True
        comp = parsed.compare(target)
        if op in {">=", "<=", ">", "<", "="}:
            if count < 3 and not pre and op in {"=", ">", "<="}:
                upper = SemVer(core[0] + 1, 0, 0) if count == 1 else SemVer(core[0], core[1] + 1, 0)
                end = parsed.compare(upper)
                results.append(comp >= 0 and end < 0 if op == "=" else end >= 0 if op == ">" else end < 0)
            else:
                results.append({">=": comp >= 0, "<=": comp <= 0, ">": comp > 0, "<": comp < 0, "=": comp == 0}[op])
            continue
        if minor == "*" or patch == "*":
            results.append(parsed.major == core[0] and (minor == "*" or parsed.minor == core[1]))
            continue
        if op == "~":
            upper = (core[0] + 1, 0, 0) if count == 1 else (core[0], core[1] + 1, 0)
        elif core[0] > 0 or count == 1:
            upper = (core[0] + 1, 0, 0)
        elif core[1] > 0 or count == 2:
            upper = (0, core[1] + 1, 0)
        else:
            upper = (0, 0, core[2] + 1)
        results.append(comp >= 0 and parsed.compare(SemVer(*upper)) < 0)
    return all(results) and prerelease_allowed
