$ErrorActionPreference = 'Stop'

$packageName = 'splitforge'
$url = "https://github.com/aykut/steameditor/releases/download/v$env:CHOCOLATEY_PACKAGE_VERSION/SplitForge_Setup_$env:CHOCOLATEY_PACKAGE_VERSION.exe"
$checksum = 'SHA256_CHECKSUM_PLACEHOLDER'
$checksumType = 'sha256'

$toolsDir = "$(Split-Path -parent $MyInvocation.MyCommand.Definition)"

$packageArgs = @{
  packageName   = $packageName
  fileType      = 'exe'
  url           = $url
  checksum      = $checksum
  checksumType  = $checksumType
  silentArgs    = '/S'
  validExitCodes= @(0)
  softwareName  = 'SplitForge*'
}

Install-ChocolateyPackage @packageArgs

# Create desktop shortcut if not exists
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "SplitForge.lnk"
$targetPath = Join-Path $env:LOCALAPPDATA "SplitForge\SplitForge.exe"

if (Test-Path $targetPath -and !(Test-Path $shortcutPath)) {
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $targetPath
    $shortcut.WorkingDirectory = Split-Path $targetPath
    $shortcut.IconLocation = $targetPath
    $shortcut.Save()
}