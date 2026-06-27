param(
    [string]$Model = "",
    [string[]]$Models = @(),
    [int]$Runs = 1,
    [int]$MaxConsecutiveErrors = 3,
    [switch]$DryRunOnly
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogDir = Join-Path $Root "logs\clean_core_v2_$Stamp"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$MasterLog = Join-Path $LogDir "clean_core_v2_master.log"

function Write-Log {
    param([string]$Message)
    $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Message"
    Write-Host $line
    Add-Content -Path $MasterLog -Value $line
}

$Configs = @(
    "configs\clean_core\clean_core_threshold_boundary_v2.json",
    "configs\clean_core\clean_core_floor_gradient_v2.json",
    "configs\clean_core\clean_core_mechanism_split_v2.json",
    "configs\clean_core\clean_core_schema_only_v2.json",
    "configs\clean_core\clean_core_rule_location_v2.json"
)

if ($Models.Count -eq 0) {
    if ([string]::IsNullOrWhiteSpace($Model)) {
        $Models = @("qwen3-8b", "llama3-8b", "gemma4-12b")
    } else {
        $Models = @($Model)
    }
}

$ExpandedModels = @()
foreach ($item in $Models) {
    foreach ($part in ($item -split ',')) {
        $clean = $part.Trim()
        if (-not [string]::IsNullOrWhiteSpace($clean)) {
            $ExpandedModels += $clean
        }
    }
}
$Models = $ExpandedModels

function Get-SafeName {
    param([string]$Value)
    return ($Value -replace '[^A-Za-z0-9_-]', '_')
}

function Format-Elapsed {
    param([TimeSpan]$Elapsed)
    return "{0:00}:{1:00}:{2:00}" -f [int]$Elapsed.TotalHours, $Elapsed.Minutes, $Elapsed.Seconds
}

Write-Log "Starting clean core v2 pilot"
Write-Log "Models=$($Models -join ',') Runs=$Runs MaxConsecutiveErrors=$MaxConsecutiveErrors DryRunOnly=$DryRunOnly"
Write-Log "Log directory: $LogDir"

$failed = @()
foreach ($CurrentModel in $Models) {
    $SafeModel = Get-SafeName $CurrentModel
    Write-Log "MODEL BEGIN $CurrentModel"

    foreach ($Config in $Configs) {
        $Name = [System.IO.Path]::GetFileNameWithoutExtension($Config)
        $ConfigLog = Join-Path $LogDir "$SafeModel`__$Name.log"
        Write-Log "BEGIN model=$CurrentModel config=$Config"
        $BatchStopwatch = [System.Diagnostics.Stopwatch]::StartNew()

        $Args = @("src\clean_layer2.py", "--config", $Config, "--model", $CurrentModel, "--runs", "$Runs", "--examples", "0", "--max-consecutive-errors", "$MaxConsecutiveErrors")
        if ($DryRunOnly) {
            $Args += "--dry-run"
        }

        & python @Args 2>&1 | Tee-Object -FilePath $ConfigLog
        $code = $LASTEXITCODE
        $BatchStopwatch.Stop()
        $Elapsed = Format-Elapsed $BatchStopwatch.Elapsed
        if ($code -ne 0) {
            Write-Log "FAILED model=$CurrentModel config=$Config exit_code=$code elapsed=$Elapsed"
            $failed += "$CurrentModel::$Config"
            break
        }
        Write-Log "DONE model=$CurrentModel config=$Config elapsed=$Elapsed"
    }

    Write-Log "MODEL DONE $CurrentModel"
    if ($failed.Count -gt 0) {
        break
    }
}

if ($failed.Count -gt 0) {
    Write-Log "Clean core stopped after failure: $($failed -join ', ')"
    exit 1
}

Write-Log "Clean core v2 pilot completed"
exit 0

