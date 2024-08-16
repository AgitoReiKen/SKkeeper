# Variables
$name = "ShKeeper"
$version = "v2.0"
$folder = "ShKeeper"
$releaseDir = "release"

if (-not (Test-Path -Path "./$releaseDir")) {
    New-Item -Path "./$releaseDir" -ItemType Directory
}

New-Item -Path "./$releaseDir/$folder" -ItemType Directory

Copy-Item -Path "__init__.py" -Destination "./$releaseDir/$folder"

Compress-Archive -Update -Path "./$releaseDir/$folder" -DestinationPath "./$releaseDir/${name}_${version}.zip"

Remove-Item -Path "./$releaseDir/$folder" -Recurse