---
Title: "Windows System Administration"
Author: "IGRIS Knowledge Base"
Reference: "internal"
ContentType: ["markdown"]
Created: 2026-09-13
Processed: true
tags: ["source", "windows", "os"]
---

# Windows System Administration

## PowerShell Scripting Patterns

### Error Handling
```powershell
try {
    $result = Get-Content -Path "C:\data\file.txt" -ErrorAction Stop
} catch [System.IO.FileNotFoundException] {
    Write-Warning "File not found: $_"
} catch {
    Write-Error "Unexpected error: $_"
} finally {
    Write-Host "Cleanup here"
}
```

### Pipeline Processing
```powershell
Get-Process | 
    Where-Object { $_.CPU -gt 10 } |
    Sort-Object CPU -Descending |
    Select-Object -First 10 Name, CPU, WorkingSet |
    Export-Csv -Path "top_processes.csv" -NoTypeInformation
```

### Function Best Practices
```powershell
function Get-SystemInfo {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)]
        [string]$ComputerName,
        
        [Parameter()]
        [ValidateSet("Quick", "Full")]
        [string]$Detail = "Quick"
    )
    
    begin {
        Write-Verbose "Starting system info collection for $ComputerName"
    }
    process {
        $os = Get-CimInstance -ClassName Win32_OperatingSystem -ComputerName $ComputerName
        $cpu = Get-CimInstance -ClassName Win32_Processor -ComputerName $ComputerName
        
        [PSCustomObject]@{
            ComputerName = $ComputerName
            OS = $os.Caption
            CPU = $cpu.Name
            RAM_GB = [math]::Round($os.TotalVisibleMemorySize / 1MB, 2)
        }
    }
    end {
        Write-Verbose "Collection complete"
    }
}
```

## Windows Registry Operations

### Read Registry
```powershell
$value = Get-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion" -Name "ProgramFilesDir"
```

### Write Registry
```powershell
New-ItemProperty -Path "HKLM:\SOFTWARE\MyApp" -Name "InstallPath" -Value "C:\MyApp" -PropertyType String -Force
```

## Service Management

```powershell
# List services
Get-Service | Where-Object {$_.Status -eq "Running"} | Format-Table Name, Status, DisplayName

# Restart service
Restart-Service -Name "Spooler" -Force

# Check service dependency
Get-Service -Name "Spooler" -RequiredServices
```

## Event Log Analysis

```powershell
# Recent errors
Get-WinEvent -FilterHashtable @{
    LogName = 'Application'
    Level = 2  # Error
    StartTime = (Get-Date).AddDays(-7)
} | Select-Object -First 20 TimeCreated, Message

# Export to CSV
Get-WinEvent -FilterHashtable @{LogName='System'; Level=2; StartTime=(Get-Date).AddDays(-1)} |
    Export-Csv -Path "errors.csv" -NoTypeInformation
```

## WMI Queries

```powershell
# System info
Get-CimInstance -ClassName Win32_ComputerSystem | Select-Object Name, Manufacturer, TotalPhysicalMemory

# Disk space
Get-CimInstance -ClassName Win32_LogicalDisk -Filter "DriveType=3" |
    Select-Object DeviceID, @{N='Size_GB';E={[math]::Round($_.Size/1GB,2)}}, @{N='Free_GB';E={[math]::Round($_.FreeSpace/1GB,2)}}

# Network adapters
Get-CimInstance -ClassName Win32_NetworkAdapterConfiguration | Where-Object {$_.IPEnabled} |
    Select-Object Description, IPAddress, IPSubnet
```

## Scheduled Tasks

```powershell
# Create task
$action = New-ScheduledTaskAction -Execute "PowerShell.exe" -Argument "-File C:\Scripts\backup.ps1"
$trigger = New-ScheduledTaskTrigger -Daily -At "2:00AM"
Register-ScheduledTask -TaskName "DailyBackup" -Action $action -Trigger $trigger -User "SYSTEM" -RunLevel Highest

# List tasks
Get-ScheduledTask | Where-Object {$_.State -eq "Ready"} | Format-Table TaskName, NextRunTime
```
