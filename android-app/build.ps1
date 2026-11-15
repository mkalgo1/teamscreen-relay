# TeamScreen Support Android APK Build Script
$ErrorActionPreference = "Stop"

$appDir = $PSScriptRoot
$aapt2 = "C:\Users\DZ_NEXTECH\AppData\Local\Android\Sdk\build-tools\36.0.0\aapt2.exe"
$androidJar = "C:\Users\DZ_NEXTECH\AppData\Local\Android\Sdk\platforms\android-37.0\android.jar"
$javac = "C:\Program Files\Java\jdk-26.0.2\bin\javac.exe"
$d8 = "C:\Users\DZ_NEXTECH\AppData\Local\Android\Sdk\build-tools\36.0.0\d8.bat"
$jar = "C:\Program Files\Java\jdk-26.0.2\bin\jar.exe"
$zipalign = "C:\Users\DZ_NEXTECH\AppData\Local\Android\Sdk\build-tools\36.0.0\zipalign.exe"
$apksigner = "C:\Users\DZ_NEXTECH\AppData\Local\Android\Sdk\build-tools\36.0.0\apksigner.bat"
$keytool = "C:\Program Files\Java\jdk-26.0.2\bin\keytool.exe"

Write-Host ">>> [1/6] Compiling resources with aapt2..." -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path "$appDir\compiled_res" | Out-Null
New-Item -ItemType Directory -Force -Path "$appDir\gen" | Out-Null
New-Item -ItemType Directory -Force -Path "$appDir\bin\classes" | Out-Null

& $aapt2 compile --dir "$appDir\res" -o "$appDir\compiled_res"

Write-Host ">>> [2/6] Linking resources..." -ForegroundColor Cyan
$flatFiles = (Get-ChildItem -Path "$appDir\compiled_res\*.flat").FullName
& $aapt2 link -o "$appDir\bin\base.apk" -I $androidJar --manifest "$appDir\AndroidManifest.xml" --java "$appDir\gen" --auto-add-overlay $flatFiles

Write-Host ">>> [3/6] Compiling Java classes..." -ForegroundColor Cyan
$javaFiles = (Get-ChildItem -Recurse -Path "$appDir\src\*.java", "$appDir\gen\*.java").FullName
& $javac --release 17 -cp $androidJar -d "$appDir\bin\classes" $javaFiles

Write-Host ">>> [4/6] Converting to DEX (d8)..." -ForegroundColor Cyan
$classFiles = (Get-ChildItem -Recurse -Path "$appDir\bin\classes\*.class").FullName
& $d8 --min-api 26 --lib $androidJar --output "$appDir\bin" $classFiles

Write-Host ">>> [5/6] Packaging and zipaligning..." -ForegroundColor Cyan
Push-Location "$appDir\bin"
& $jar -uf base.apk classes.dex
Pop-Location
if (Test-Path "$appDir\bin\aligned.apk") { Remove-Item "$appDir\bin\aligned.apk" -Force }
& $zipalign -v -p 4 "$appDir\bin\base.apk" "$appDir\bin\aligned.apk"

Write-Host ">>> [6/6] Signing APK..." -ForegroundColor Cyan
$keystore = "$appDir\teamscreen.keystore"
if (-not (Test-Path $keystore)) {
    & $keytool -genkeypair -v -keystore $keystore -alias teamscreen -keyalg RSA -keysize 2048 -validity 10000 -storepass "teamscreen123" -keypass "teamscreen123" -dname "CN=TeamScreen, OU=IT, O=Company, L=Algiers, ST=Algiers, C=DZ"
}
& $apksigner sign --ks $keystore --ks-key-alias teamscreen --ks-pass pass:teamscreen123 --key-pass pass:teamscreen123 --out "$appDir\TeamScreenSupport.apk" "$appDir\bin\aligned.apk"

Write-Host ">>> BUILD SUCCESSFUL: $appDir\TeamScreenSupport.apk" -ForegroundColor Green
