"""Static local metadata queries. No network probes, private contents or changes."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import base64
import ipaddress
import re
import time
import sys

from .runner import Runner
from .bounded_json import BoundedJSONError, loads
from .progress import Progress, invoke_with_progress
from .contract import (SECTION_IDS, STATUSES, FIELDS, LIMITS, MAX_ERRORS,
                       clean_errors, evidence, error_from_exception)

COMMON = r'''
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false)
$script:Errors=New-Object System.Collections.Generic.List[object]
$script:ErrorCount=0
function Add-Evidence($stage,$reason,$type,$hr,$native,$operation,$status,$providerCode=$null,$category=$null) {
 $script:ErrorCount++
 if($script:Errors.Count -lt 64){$script:Errors.Add([ordered]@{stage=$stage;reason_code=$reason;exception_type=$type;hresult=$hr;win32_error=$native;operation=$operation;status=$status;provider_code=$providerCode;category=$category})}
}
function Missing-Field($operation) {
 Add-Evidence 'field' 'missing_metadata' 'MissingMetadata' $null $null $operation 'unknown'
}
function Read-Status($record,$stage=$script:ReadStage,$operation=$script:ReadOperation) {
 $ex=$record.Exception
 $status='error';$reason='query_failed';$type='UnknownError';$hr=$null;$native=$null
 $providerCode=$null;$category=[string]$record.CategoryInfo.Category
 while($null -ne $ex) {
  $type=$ex.GetType().FullName;$hr=$ex.HResult
  if($ex -is [System.ComponentModel.Win32Exception]){$native=$ex.NativeErrorCode}
  elseif($ex.PSObject.Properties.Name -contains 'NativeErrorCode') {
   $providerCode=[string]$ex.NativeErrorCode
   if($providerCode -eq 'AccessDenied'){$status='denied';$reason='provider_access_denied';break}
  }
  if(($ex -is [UnauthorizedAccessException]) -or ($ex.HResult -eq -2147024891)) {$status='denied';$reason='access_denied';break}
  if($ex -is [System.Management.Automation.CommandNotFoundException]) {$status='not_applicable';$stage='launch';$reason='cmdlet_unavailable';break}
  if($ex.PSObject.Properties.Name -contains 'StatusCode') {
   if([string]$ex.StatusCode -eq 'AccessDenied') {$status='denied';$reason='provider_access_denied';break}
   if([string]$ex.StatusCode -in @('InvalidNamespace','InvalidClass','NotSupported')) {$status='not_applicable';$reason='provider_unavailable';break}
  }
  $ex=$ex.InnerException
 }
 if($status -eq 'error' -and [string]$record.CategoryInfo.Category -eq 'PermissionDenied'){$status='denied';$reason='permission_denied_category'}
 if($status -eq 'error' -and [string]$record.CategoryInfo.Category -eq 'SecurityError'){$status='denied';$reason='security_error_category'}
 Add-Evidence $stage $reason $type $hr $native $operation $status $providerCode $category
 return $status
}
function Write-Result($rows,[bool]$truncated=$false) {
 $all=@($rows.ToArray())
 $failed=@($all | Where-Object { $_.status -ne 'ok' -and -not ($_.kind -eq 'registry_missing' -and $_.status -eq 'not_applicable') })
 $good=@($all | Where-Object { $_.status -eq 'ok' })
 $status='ok'
 if($failed.Count -gt 0) {
  $status='partial';$unique=@($failed | ForEach-Object {$_.status} | Select-Object -Unique)
  if($good.Count -eq 0 -and $unique.Count -eq 1) { $status=[string]$unique[0] }
 }
 if($truncated -and $status -eq 'ok') {$status='partial'}
  [ordered]@{status=$status;rows=$all;truncated=$truncated;errors=@($script:Errors.ToArray());error_count=$script:ErrorCount;errors_truncated=($script:ErrorCount -gt 64)} | ConvertTo-Json -Depth 5 -Compress
}
function Test-LocalFixedPath([string]$path) {
 if([string]::IsNullOrWhiteSpace($path) -or $path -notmatch '^[A-Za-z]:\\' -or $path.StartsWith('\\')) {return $false}
 $drive=[IO.Path]::GetPathRoot($path)
 $info=New-Object IO.DriveInfo($drive)
 if($info.DriveType -ne [IO.DriveType]::Fixed) {return $false}
 $current=$drive
 foreach($part in @($null)+@($path.Substring($drive.Length).Split('\') | Where-Object {$_})) {
  if($null -ne $part) {$current=[IO.Path]::Combine($current,$part)}
  $attributes=[IO.File]::GetAttributes($current)
  if(($attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {return $false}
 }
 return $true
}
'''

BODY = {
"defender": r'''
$rows=New-Object System.Collections.Generic.List[object]
try {
 $s=Get-MpComputerStatus -ErrorAction Stop
 $script:ReadStage='field'
 foreach($name in @('AMServiceEnabled','AntivirusEnabled','RealTimeProtectionEnabled','BehaviorMonitorEnabled','IsTamperProtected','AntivirusSignatureVersion','AntivirusSignatureLastUpdated')) {
  $value=$null;$status='unknown'
  try {if($s.PSObject.Properties.Name -contains $name) {$value=$s.$name;if($null -ne $value){$status='ok'}}}
  catch {$status=Read-Status $_ 'field' ('Defender.'+$name)}
  if($status -eq 'unknown'){Missing-Field ('Defender.'+$name)}
  if($value -is [datetime]) {$value=$value.ToUniversalTime().ToString('o')}
  $rows.Add([ordered]@{item=$name;value=$value;status=$status})
 }
} catch {$rows.Add([ordered]@{item='defender_status';value=$null;status=(Read-Status $_)})}
Write-Result $rows
''',
"listeners": r'''
$rows=New-Object System.Collections.Generic.List[object]
$truncated=$false
try {
 $items=@(Get-NetTCPConnection -State Listen -ErrorAction Stop | Select-Object -First 1001)
 $script:ReadStage='field'
 if($items.Count -gt 1000){$truncated=$true}
 foreach($item in @($items | Select-Object -First 1000)) {$rows.Add([ordered]@{protocol='TCP';address=[string]$item.LocalAddress;port=[int]$item.LocalPort;pid=[int]$item.OwningProcess;status='ok'})}
} catch {if($_.FullyQualifiedErrorId -notlike 'CmdletizationQuery_NotFound_State,*'){$rows.Add([ordered]@{protocol='TCP';status=(Read-Status $_)})}}
try {
 $script:ReadStage='provider'
 $items=@(Get-NetUDPEndpoint -ErrorAction Stop | Select-Object -First 1001)
 $script:ReadStage='field'
 if($items.Count -gt 1000){$truncated=$true}
 foreach($item in @($items | Select-Object -First 1000)) {$rows.Add([ordered]@{protocol='UDP';address=[string]$item.LocalAddress;port=[int]$item.LocalPort;pid=[int]$item.OwningProcess;status='ok'})}
} catch {if($_.FullyQualifiedErrorId -notlike 'CmdletizationQuery_NotFound,*'){$rows.Add([ordered]@{protocol='UDP';status=(Read-Status $_)})}}
Write-Result $rows $truncated
''',
"processes": r'''
$rows=New-Object System.Collections.Generic.List[object]
$truncated=$false
try {
 $items=@(Get-CimInstance -ClassName Win32_Process -Property ProcessId,Name,ExecutablePath,CreationDate -OperationTimeoutSec 8 -ErrorAction Stop | Select-Object -First 2001)
 $script:ReadStage='field'
 if($items.Count -gt 2000){$truncated=$true}
 foreach($item in @($items | Select-Object -First 2000)) {
  $path=[string]$item.ExecutablePath;$pathStatus='ok';$created=$null
  if([string]::IsNullOrWhiteSpace($path)){$pathStatus='unknown';Missing-Field 'Process.ExecutablePath'}
  if($null -ne $item.CreationDate){$created=$item.CreationDate.ToUniversalTime().ToString('o')}
  else {Missing-Field 'Process.CreationDate'}
  $rows.Add([ordered]@{pid=[int]$item.ProcessId;name=[string]$item.Name;path=$path;path_status=$pathStatus;created_at=$created;status=$pathStatus})
 }
} catch {$rows.Add([ordered]@{status=(Read-Status $_);path_status=(Read-Status $_)})}
Write-Result $rows $truncated
''',
"startup": r'''
$rows=New-Object System.Collections.Generic.List[object]
$truncated=$false
$paths=@('Software\Microsoft\Windows\CurrentVersion\Run','Software\Microsoft\Windows\CurrentVersion\RunOnce')
foreach($hive in @([Microsoft.Win32.RegistryHive]::CurrentUser,[Microsoft.Win32.RegistryHive]::LocalMachine)) {
 foreach($view in @([Microsoft.Win32.RegistryView]::Registry32,[Microsoft.Win32.RegistryView]::Registry64)) {
  foreach($path in $paths) {
   $base=$null;$key=$null;$source=[string]$hive+'\'+$path
   try {
    $base=[Microsoft.Win32.RegistryKey]::OpenBaseKey($hive,$view);$key=$base.OpenSubKey($path,$false)
    if($null -eq $key){$rows.Add([ordered]@{source=$source;registry_view=[string]$view;name='(key absent)';kind='registry_missing';status='not_applicable'})}
    else {
     $names=@($key.GetValueNames())
     if($names.Count -eq 0){$rows.Add([ordered]@{source=$source;registry_view=[string]$view;name='(empty)';kind='registry_empty';status='ok'})}
     foreach($name in @($names | Select-Object -First 1000)){$rows.Add([ordered]@{source=$source;registry_view=[string]$view;name=[string]$name;kind='registry';status='ok'})}
     if($names.Count -gt 1000){$truncated=$true}
    }
   } catch {$rows.Add([ordered]@{source=$source;registry_view=[string]$view;name=$null;kind='registry';status=(Read-Status $_ 'object' 'Startup.RegistryNames')})}
   finally {if($null -ne $key){$key.Dispose()};if($null -ne $base){$base.Dispose()}}
  }
 }
}
foreach($folderName in @('Startup','CommonStartup')) {
 try {
  $folder=[Environment]::GetFolderPath([Environment+SpecialFolder]$folderName,[Environment+SpecialFolderOption]::DoNotVerify)
  if(-not (Test-LocalFixedPath $folder)){$rows.Add([ordered]@{source=$folderName;name=$null;kind='folder_skipped';status='unknown'});continue}
  $items=@(Get-ChildItem -LiteralPath $folder -Force -ErrorAction Stop | Select-Object -First 1001)
  if($items.Count -gt 1000){$truncated=$true}
  if($items.Count -eq 0){$rows.Add([ordered]@{source=$folderName;name='(empty)';kind='folder_empty';status='ok'})}
  foreach($item in @($items | Select-Object -First 1000)){$rows.Add([ordered]@{source=$folderName;name=[string]$item.Name;kind='folder';status='ok'})}
 } catch {$rows.Add([ordered]@{source=$folderName;name=$null;kind='folder';status=(Read-Status $_ 'object' 'Startup.DirectoryNames')})}
}
Write-Result $rows $truncated
''',
"services": r'''
$rows=New-Object System.Collections.Generic.List[object]
$truncated=$false
try {
 $items=@(Get-CimInstance -ClassName Win32_Service -Property Name,State,StartMode -OperationTimeoutSec 8 -ErrorAction Stop | Select-Object -First 501)
 $script:ReadStage='field'
 if($items.Count -gt 500){$truncated=$true}
 foreach($item in @($items | Select-Object -First 500)){$rows.Add([ordered]@{name=[string]$item.Name;state=[string]$item.State;start_mode=[string]$item.StartMode;status='ok'})}
} catch {$rows.Add([ordered]@{status=(Read-Status $_)})}
Write-Result $rows $truncated
''',
"tasks": r'''
$rows=New-Object System.Collections.Generic.List[object]
$truncated=$false
try {
 $items=@(Get-ScheduledTask -ErrorAction Stop | Select-Object -First 301)
 $script:ReadStage='field'
 if($items.Count -gt 300){$truncated=$true}
 foreach($item in @($items | Select-Object -First 300)){$rows.Add([ordered]@{name=[string]$item.TaskName;task_path=[string]$item.TaskPath;state=[string]$item.State;status='ok'})}
} catch {$rows.Add([ordered]@{status=(Read-Status $_)})}
Write-Result $rows $truncated
''',
"versions": r'''
$rows=New-Object System.Collections.Generic.List[object]
$script:ReadStage='object'
$path=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('__PYTHON_RUNTIME_B64__'))
try {
 if(-not (Test-LocalFixedPath $path)){$rows.Add([ordered]@{product='python_runtime';path=$path;version=$null;status='unknown'})}
 else {$v=[Diagnostics.FileVersionInfo]::GetVersionInfo($path).ProductVersion;$status='ok';if([string]::IsNullOrWhiteSpace($v)){$status='unknown'};$rows.Add([ordered]@{product='python_runtime';path=$path;version=$v;status=$status})}
} catch {$status=Read-Status $_;if($_.Exception -is [IO.FileNotFoundException] -or $_.Exception -is [IO.DirectoryNotFoundException]){$status='not_applicable'};$rows.Add([ordered]@{product='python_runtime';path=$path;version=$null;status=$status})}
Write-Result $rows
''',
}
SCRIPTS = {name: COMMON + "\n$script:ReadStage='provider';$script:ReadOperation='" + name + "'\n" + body.replace('__PYTHON_RUNTIME_B64__', base64.b64encode(sys.executable.encode('utf-8')).decode('ascii'))
           for name, body in BODY.items()}


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def redact(value):
    if not isinstance(value, str):
        return value
    value = re.sub(r"[\x00-\x1f\x7f]", " ", value)
    value = re.sub(r"(?i)[a-z]:[\\/]Users[\\/][^\\/\"<>|]+", "%USER_HOME%", value)
    value = re.sub(r"(?i)/(?:Users|home)/[^/\"<>|]+", "%USER_HOME%", value)
    return value[:2048]


def classify_address(address):
    try:
        parsed = ipaddress.ip_address(str(address).split("%", 1)[0])
        if isinstance(parsed, ipaddress.IPv6Address) and parsed.ipv4_mapped:
            parsed = parsed.ipv4_mapped
        if parsed.is_unspecified:
            return "all_interfaces"
        if parsed.is_loopback:
            return "localhost"
        if parsed.is_link_local:
            return "link_local"
        networks = ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16") if parsed.version == 4 else ("fc00::/7",)
        if any(parsed in ipaddress.ip_network(net) for net in networks):
            return "lan"
        return "global" if parsed.is_global else "other_reserved"
    except (ValueError, TypeError):
        return "unknown"


def optional_absence(section_id, row):
    return section_id == "startup" and row.get("kind") == "registry_missing" and row.get("status") == "not_applicable"


def process_reference(pid, created_at):
    """Canonical PID plus creation instant shared by process and listener rows."""
    if type(pid) is not int or not isinstance(created_at, str):
        return None, None
    try:
        stamp = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            return None, None
        created = stamp.astimezone(timezone.utc).isoformat(timespec="microseconds")
    except ValueError:
        return None, None
    key = str(pid) + "\0" + created
    return created, "proc-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


class PowerShellBackend:
    name = "powershell"

    def __init__(self, runner, timeout=15):
        self.runner, self.timeout = runner, timeout

    def collect(self, section_id, cancel=None, progress=None):
        raw = invoke_with_progress(self.runner.run, SCRIPTS[section_id], timeout=self.timeout, cancel=cancel,
                                   progress=progress, source_id=section_id)
        if not isinstance(raw, dict):
            raise ValueError("invalid_runner_output")
        if raw.get("status") == "ok":
            data = raw.get("data")
            try:
                data = loads(data) if isinstance(data, str) else data
            except BoundedJSONError as error:
                return {"status": "error", "rows": [], "truncated": False, "process": raw.get("process", {}),
                        "errors": [evidence("provider", error.reason, exception_type="BoundedJSONError", status="error")]}
            data["process"] = raw.get("process", {})
            return data
        state = raw.get("status") if raw.get("status") in STATUSES else "unknown"
        errors = clean_errors(raw.get("errors")) or [evidence("provider", "runner_reason_unavailable", status=state)]
        return {"status": state, "rows": [], "errors": errors, "truncated": False, "process": raw.get("process", {})}


class WindowsCollectors:
    def __init__(self, runner=None, *, native=None, backend=None, evidence_sink=None, timeout=15):
        # An explicitly injected legacy runner remains a PowerShell fixture seam.
        self.backend = backend or ("powershell" if runner is not None else "auto")
        if self.backend not in ("auto", "native", "powershell"):
            raise ValueError("unsupported_backend")
        if type(timeout) not in (int, float) or not 0 < timeout <= 60:
            raise ValueError("invalid_collector_timeout")
        self.runner = runner or Runner(evidence_sink=evidence_sink)
        self.evidence_sink = evidence_sink
        self.powershell = PowerShellBackend(self.runner, timeout)
        if native is None:
            from .worker import NativeWorker
            native = NativeWorker(evidence_sink=evidence_sink, timeout=timeout, runner=self.runner)
        self.native = native

    def collect(self, section_id, cancel=None, progress=None):
        if section_id not in SCRIPTS:
            raise ValueError("unsupported_section")
        started = time.monotonic()
        result = {"id": section_id, "status": "unknown", "rows": [], "observed_at": utc_now(), "elapsed_ms": 0,
                  "coverage": {"status": "unknown", "scope": "local_metadata_only", "truncated": False,
                               "row_limit": LIMITS[section_id], "contract_version": "2.0", "errors": [], "attempts": []}}
        try:
            names = ["powershell"] if self.backend == "powershell" else ["native"]
            data = None
            while names:
                name = names.pop(0)
                before = time.monotonic()
                observer = Progress(progress, section_id, name)
                observer.emit("launch")
                try:
                    data = invoke_with_progress(
                        (self.native if name == "native" else self.powershell).collect,
                        section_id, cancel=cancel, progress=observer.forward if progress is not None else None)
                finally:
                    observer.emit("completed")
                if not isinstance(data, dict) or data.get("status") not in STATUSES or not isinstance(data.get("rows"), list):
                    raise ValueError("invalid_backend_output")
                errors = clean_errors(data.get("errors"))
                if data["status"] not in ("ok",) and not errors:
                    errors = [evidence("provider", "backend_reason_unavailable", status=data["status"])]
                # Inspect only the existing bounded prefix. One malformed
                # object must not erase independently usable sibling rows, or
                # masquerade as an unavailable API that merits fallback.
                invalid_rows = sum(not isinstance(row, dict) for row in data["rows"][:LIMITS[section_id]])
                reported_errors = data.get("error_count", 0)
                error_count = max(len(errors), reported_errors) if type(reported_errors) is int else len(errors)
                errors_truncated = data.get("errors_truncated") is True
                if invalid_rows:
                    row_error = evidence("object", "invalid_collector_row", exception_type="ContractError",
                                         operation=section_id + ".row", status="error")
                    # Retain the contract cause even when the provider has
                    # already filled the evidence budget. Remaining causes are
                    # counted, never copied from hostile row text or repr().
                    errors_truncated = errors_truncated or len(errors) + invalid_rows > MAX_ERRORS
                    errors = ([row_error] + errors + [row_error] * (min(invalid_rows, MAX_ERRORS) - 1))[:MAX_ERRORS]
                    error_count += invalid_rows
                attempt = {"backend": name, "status": data["status"], "errors": errors,
                           "elapsed_ms": int((time.monotonic() - before) * 1000)}
                if invalid_rows:
                    attempt.update(status="error", source_status=data["status"], invalid_row_count=invalid_rows,
                                   error_count=error_count, errors_truncated=errors_truncated)
                result["coverage"]["attempts"].append(attempt)
                result["coverage"]["backend"] = name
                # Same ordinary token only. Denials, partial data and pending operations are not retried.
                if (not invalid_rows and self.backend == "auto" and name == "native" and data["status"] == "not_applicable"
                        and len(data["rows"]) <= LIMITS[section_id]
                        and any(e["reason_code"] == "api_unavailable" for e in errors)
                        and not any(isinstance(r, dict) and r.get("status") in ("ok", "partial") for r in data["rows"][:LIMITS[section_id]])):
                    names.append("powershell")
            result["status"] = data["status"]
            result["coverage"]["process"] = process_metadata(data.get("process"))
            result["coverage"]["errors"] = errors
            result["coverage"]["error_count"] = error_count
            result["coverage"]["errors_truncated"] = errors_truncated
            result["coverage"]["checks"] = clean_checks(data.get("checks"))
            rows = data["rows"]
            truncated = data.get("truncated") is True or len(rows) > LIMITS[section_id]
            for row in rows[:LIMITS[section_id]]:
                if not isinstance(row, dict):
                    continue
                safe = {key: redact(row[key]) for key in FIELDS[section_id] if key in row and isinstance(row[key], (str, int, float, bool, type(None)))}
                if safe.get("status") not in STATUSES:
                    safe["status"] = "unknown"
                if section_id == "listeners":
                    safe["scope"] = classify_address(safe.get("address"))
                    if safe["status"] == "ok" and (safe["scope"] == "unknown" or type(safe.get("port")) is not int or not 0 <= safe["port"] <= 65535 or safe.get("protocol") not in ("TCP", "UDP")):
                        safe["status"] = "unknown"
                    # Only this collection's identity proof may bind the PID.
                    # Missing fallback metadata stays an explicit field gap.
                    identity_status = safe.get("process_identity_status")
                    identity_status = identity_status if identity_status in STATUSES else "unknown"
                    created, reference = process_reference(safe.get("pid"), safe.get("created_at"))
                    if identity_status != "ok" or created is None:
                        created, reference = None, None
                        if identity_status == "ok":
                            identity_status = "unknown"
                    safe.update(created_at=created, process_instance_ref=reference, process_identity_status=identity_status)
                elif section_id == "processes":
                    if not safe.get("path"):
                        if safe.get("path_status") not in ("denied", "not_applicable", "error"):
                            safe["path_status"] = "unknown"
                        if safe["status"] == "ok":
                            safe["status"] = "unknown"
                    created, reference = process_reference(safe.get("pid"), safe.get("created_at"))
                    safe.update(created_at=created, process_instance_ref=reference)
                    if reference is None:
                        if safe["status"] == "ok":
                            safe["status"] = "unknown"
                result["rows"].append(safe)
            if invalid_rows:
                usable = any(row["status"] in ("ok", "partial")
                             and any(value is not None for key, value in row.items() if key != "status")
                             for row in result["rows"])
                result["status"] = "partial" if usable else "error"
                result["coverage"].update(invalid_row_count=invalid_rows, reason="invalid_collector_row")
                attempt["status"] = result["status"]
            if result["status"] == "ok" and (truncated or errors or any(r["status"] != "ok" and not optional_absence(section_id, r) for r in result["rows"])):
                result["status"] = "partial"
            result["coverage"]["truncated"] = truncated
            if section_id == "listeners":
                total = len(result["rows"])
                bound = sum(row.get("process_instance_ref") is not None for row in result["rows"])
                result["coverage"]["process_identity_status"] = "ok" if bound == total else "partial" if bound else "unknown"
                result["coverage"]["process_identity_missing_count"] = total-bound
                if bound < total:
                    result["coverage"]["process_identity_reason"] = "listener_process_identity_unavailable"
        except (ValueError, TypeError, KeyError, UnicodeError):
            result["status"] = "error"
            result["rows"] = []
            result["coverage"]["reason"] = "invalid_collector_output"
            result["coverage"]["errors"] = [evidence("provider", "invalid_collector_output", exception_type="ContractError", status="error")]
        except Exception as error:
            result["status"] = "error"
            result["rows"] = []
            result["coverage"]["reason"] = "collector_failed_without_raw_error"
            result["coverage"]["errors"] = [error_from_exception(error, "provider", section_id)]
            if self.evidence_sink is not None:
                import traceback
                self.evidence_sink({"kind": "collector_exception", "section": section_id,
                                    "exception_type": type(error).__name__, "exception_text": str(error)[:8192],
                                    "traceback": traceback.format_exc(limit=12)[:16384]})
        result["coverage"]["status"] = result["status"]
        result["coverage"]["row_count"] = len(result["rows"])
        result["coverage"]["usable_row_count"] = sum(
            row["status"] in ("ok", "partial") and any(value is not None for key, value in row.items() if key != "status")
            for row in result["rows"])
        result["coverage"]["error_count"] = max(
            len(result["coverage"]["errors"]), result["coverage"].get("error_count", 0))
        if result["coverage"]["errors"] and "reason" not in result["coverage"]:
            result["coverage"]["reason"] = result["coverage"]["errors"][0]["reason_code"]
        result["elapsed_ms"] = int((time.monotonic() - started) * 1000)
        return result


def clean_checks(values):
    result = []
    for item in values[:64] if isinstance(values, list) else []:
        if (isinstance(item, dict) and isinstance(item.get("operation"), str)
                and re.fullmatch(r"[A-Za-z][A-Za-z0-9_.]{0,95}", item["operation"])
                and item.get("status") in STATUSES and type(item.get("count")) is int and 0 <= item["count"] <= 2**31-1):
            result.append({"operation": item["operation"], "status": item["status"], "count": item["count"]})
    return result


def coverage_metadata(section):
    """Safe coverage propagation into health/status and typed diagnostic results."""
    source = section.get("coverage", {})
    if not isinstance(source, dict):
        source = {}
    result = {"errors": clean_errors(source.get("errors")), "checks": clean_checks(source.get("checks")),
              "truncated": source.get("truncated") is True}
    if source.get("process"):
        result["process"] = process_metadata(source["process"])
    for key in ("error_count", "row_limit", "row_count", "usable_row_count", "invalid_row_count", "process_identity_missing_count"):
        value = source.get(key)
        if type(value) is int and 0 <= value <= 2**31-1:
            result[key] = value
    result["errors_truncated"] = source.get("errors_truncated") is True
    if source.get("process_identity_status") in STATUSES:
        result["process_identity_status"] = source["process_identity_status"]
    if source.get("process_identity_reason") == "listener_process_identity_unavailable":
        result["process_identity_reason"] = source["process_identity_reason"]
    if source.get("backend") in ("native", "powershell"):
        result["backend"] = source["backend"]
    reason = source.get("reason")
    if isinstance(reason, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,95}", reason):
        result["reason"] = reason
    attempts = source.get("attempts", [])
    result["attempts"] = [{"backend": a["backend"], "status": a["status"], "errors": clean_errors(a.get("errors")),
                           **({"source_status": a["source_status"]} if a.get("source_status") in STATUSES else {}),
                           **{key: a[key] for key in ("invalid_row_count", "error_count")
                              if type(a.get(key)) is int and 0 <= a[key] <= 2**31-1},
                           **({"errors_truncated": a["errors_truncated"]} if type(a.get("errors_truncated")) is bool else {}),
                           **({"elapsed_ms": a["elapsed_ms"]} if type(a.get("elapsed_ms")) is int and 0 <= a["elapsed_ms"] <= 2**31-1 else {})}
                          for a in (attempts[:2] if isinstance(attempts, list) else []) if isinstance(a, dict)
                          and a.get("backend") in ("native", "powershell") and a.get("status") in STATUSES]
    return result


def process_metadata(value):
    if not isinstance(value, dict):
        return {}
    result = {key: value[key] for key in ("managed", "child_exited", "forcibly_terminated", "output_limit_exceeded") if type(value.get(key)) is bool}
    if isinstance(value.get("job_name"), str) and re.fullmatch(r"(?:Local|Global)\\EventGuard-[a-f0-9]{32}", value["job_name"]):
        result["job_name"] = value["job_name"]
    for key in ("pid", "remaining_owned_processes", "exit_code", "output_limit_bytes", "output_bytes_observed"):
        if type(value.get(key)) is int and 0 <= value[key] <= 2**32-1:
            result[key] = value[key]
    for key in ("reason", "shutdown_requested_reason"):
        if value.get(key) in {"timeout", "cancelled", "output_limit", "owner_exception", "descendants_remaining", "test_teardown", "launch_failure", "natural_exit", "fixture_or_non_windows"}:
            result[key] = value[key]
    if isinstance(value.get("created_at"), str) and len(value["created_at"]) <= 64:
        try:
            stamp = datetime.fromisoformat(value["created_at"])
            if stamp.tzinfo is not None:
                result["created_at"] = stamp.astimezone(timezone.utc).isoformat(timespec="microseconds")
        except ValueError:
            pass
    return result
