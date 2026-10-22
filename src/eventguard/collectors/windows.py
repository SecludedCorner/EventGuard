"""Static local metadata queries. No network probes, private contents or changes."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import re
import time

from .runner import Runner

SECTION_IDS = ("defender", "listeners", "processes", "startup", "services", "tasks", "versions")
STATUSES = frozenset({"ok", "partial", "denied", "unknown", "not_applicable", "error", "timeout", "cancelled", "busy", "not_requested"})
FIELDS = {
    "defender": {"item", "value", "status"},
    "listeners": {"protocol", "address", "port", "pid", "scope", "status"},
    "processes": {"pid", "name", "path", "path_status", "created_at", "process_instance_ref", "status"},
    "startup": {"source", "name", "registry_view", "kind", "status"},
    "services": {"name", "state", "start_mode", "status"},
    "tasks": {"name", "task_path", "state", "status"},
    "versions": {"product", "version", "path", "status"},
}
LIMITS = {"defender": 20, "listeners": 1000, "processes": 2000, "startup": 1000, "services": 500, "tasks": 300, "versions": 10}

COMMON = r'''
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding($false)
function Read-Status($record) {
 $ex=$record.Exception
 while($null -ne $ex) {
  if(($ex -is [UnauthorizedAccessException]) -or ($ex.HResult -eq -2147024891)) { return 'denied' }
  if($ex -is [System.Management.Automation.CommandNotFoundException]) { return 'not_applicable' }
  if($ex.PSObject.Properties.Name -contains 'StatusCode') {
   if([string]$ex.StatusCode -eq 'AccessDenied') { return 'denied' }
   if([string]$ex.StatusCode -in @('InvalidNamespace','InvalidClass','NotSupported')) { return 'not_applicable' }
  }
  $ex=$ex.InnerException
 }
 if([string]$record.CategoryInfo.Category -in @('PermissionDenied','SecurityError')) { return 'denied' }
 return 'error'
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
 [ordered]@{status=$status;rows=$all;truncated=$truncated} | ConvertTo-Json -Depth 5 -Compress
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
 foreach($name in @('AMServiceEnabled','AntivirusEnabled','RealTimeProtectionEnabled','BehaviorMonitorEnabled','IsTamperProtected','AntivirusSignatureVersion','AntivirusSignatureLastUpdated')) {
  $value=$null;$status='unknown'
  if($s.PSObject.Properties.Name -contains $name) {$value=$s.$name;if($null -ne $value){$status='ok'}}
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
 if($items.Count -gt 1000){$truncated=$true}
 foreach($item in @($items | Select-Object -First 1000)) {$rows.Add([ordered]@{protocol='TCP';address=[string]$item.LocalAddress;port=[int]$item.LocalPort;pid=[int]$item.OwningProcess;status='ok'})}
} catch {if($_.FullyQualifiedErrorId -notlike 'CmdletizationQuery_NotFound_State,*'){$rows.Add([ordered]@{protocol='TCP';status=(Read-Status $_)})}}
try {
 $items=@(Get-NetUDPEndpoint -ErrorAction Stop | Select-Object -First 1001)
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
 if($items.Count -gt 2000){$truncated=$true}
 foreach($item in @($items | Select-Object -First 2000)) {
  $path=[string]$item.ExecutablePath;$pathStatus='ok';$created=$null
  if([string]::IsNullOrWhiteSpace($path)){$pathStatus='unknown'}
  if($null -ne $item.CreationDate){$created=$item.CreationDate.ToUniversalTime().ToString('o')}
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
   } catch {$rows.Add([ordered]@{source=$source;registry_view=[string]$view;name=$null;kind='registry';status=(Read-Status $_)})}
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
 } catch {$rows.Add([ordered]@{source=$folderName;name=$null;kind='folder';status=(Read-Status $_)})}
}
Write-Result $rows $truncated
''',
"services": r'''
$rows=New-Object System.Collections.Generic.List[object]
$truncated=$false
try {
 $items=@(Get-CimInstance -ClassName Win32_Service -Property Name,State,StartMode -OperationTimeoutSec 8 -ErrorAction Stop | Select-Object -First 501)
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
 if($items.Count -gt 300){$truncated=$true}
 foreach($item in @($items | Select-Object -First 300)){$rows.Add([ordered]@{name=[string]$item.TaskName;task_path=[string]$item.TaskPath;state=[string]$item.State;status='ok'})}
} catch {$rows.Add([ordered]@{status=(Read-Status $_)})}
Write-Result $rows $truncated
''',
"versions": r'''
$rows=New-Object System.Collections.Generic.List[object]
$path='C:\Python313\python.exe'
try {
 if(-not (Test-LocalFixedPath $path)){$rows.Add([ordered]@{product='python_runtime';path=$path;version=$null;status='unknown'})}
 else {$v=[Diagnostics.FileVersionInfo]::GetVersionInfo($path).ProductVersion;$status='ok';if([string]::IsNullOrWhiteSpace($v)){$status='unknown'};$rows.Add([ordered]@{product='python_runtime';path=$path;version=$v;status=$status})}
} catch {$status=Read-Status $_;if($_.Exception -is [IO.FileNotFoundException] -or $_.Exception -is [IO.DirectoryNotFoundException]){$status='not_applicable'};$rows.Add([ordered]@{product='python_runtime';path=$path;version=$null;status=$status})}
Write-Result $rows
''',
}
SCRIPTS = {name: COMMON + body for name, body in BODY.items()}


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


class WindowsCollectors:
    def __init__(self, runner=None):
        self.runner = runner or Runner()

    def collect(self, section_id, cancel=None):
        if section_id not in SCRIPTS:
            raise ValueError("unsupported_section")
        started = time.monotonic()
        result = {"id": section_id, "status": "unknown", "rows": [], "observed_at": utc_now(), "elapsed_ms": 0,
                  "coverage": {"status": "unknown", "scope": "local_metadata_only", "truncated": False, "row_limit": LIMITS[section_id]}}
        try:
            raw = self.runner.run(SCRIPTS[section_id], timeout=15, cancel=cancel)
            if not isinstance(raw, dict):
                raise ValueError()
            state = raw.get("status", "unknown")
            if state != "ok":
                result["status"] = state if state in STATUSES else "unknown"
            else:
                data = raw.get("data")
                if isinstance(data, str):
                    data = json.loads(data)
                if not isinstance(data, dict) or data.get("status") not in STATUSES or not isinstance(data.get("rows"), list):
                    raise ValueError()
                result["status"] = data["status"]
                rows = data["rows"]
                truncated = data.get("truncated") is True or len(rows) > LIMITS[section_id]
                for row in rows[:LIMITS[section_id]]:
                    if not isinstance(row, dict):
                        raise ValueError()
                    safe = {key: redact(row[key]) for key in FIELDS[section_id] if key in row and isinstance(row[key], (str, int, float, bool, type(None)))}
                    if safe.get("status") not in STATUSES:
                        safe["status"] = "unknown"
                    if section_id == "listeners":
                        safe["scope"] = classify_address(safe.get("address"))
                        if safe["status"] == "ok" and (safe["scope"] == "unknown" or type(safe.get("port")) is not int or not 0 <= safe["port"] <= 65535 or safe.get("protocol") not in ("TCP", "UDP")):
                            safe["status"] = "unknown"
                    elif section_id == "processes":
                        if not safe.get("path"):
                            safe["path_status"] = "unknown"
                            if safe["status"] == "ok":
                                safe["status"] = "unknown"
                        if type(safe.get("pid")) is int and isinstance(safe.get("created_at"), str) and safe["created_at"]:
                            key = str(safe["pid"]) + "\0" + safe["created_at"]
                            safe["process_instance_ref"] = "proc-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
                        else:
                            safe["process_instance_ref"] = None
                            if safe["status"] == "ok":
                                safe["status"] = "unknown"
                    result["rows"].append(safe)
                if result["status"] == "ok" and (truncated or any(r["status"] != "ok" and not optional_absence(section_id, r) for r in result["rows"])):
                    result["status"] = "partial"
                result["coverage"]["truncated"] = truncated
        except (ValueError, TypeError, KeyError, UnicodeError):
            result["status"] = "error"
            result["rows"] = []
            result["coverage"]["reason"] = "invalid_collector_output"
        except Exception:
            result["status"] = "error"
            result["rows"] = []
            result["coverage"]["reason"] = "collector_failed_without_raw_error"
        result["coverage"]["status"] = result["status"]
        result["elapsed_ms"] = int((time.monotonic() - started) * 1000)
        return result
