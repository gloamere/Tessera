[CmdletBinding()]
param(
    [string]$RepositoryRoot,
    [string]$MarketplaceSource,
    [string]$MarketplaceRef,
    [switch]$IncludeLegacyMigration,
    [switch]$KeepTemp
)

$ErrorActionPreference = 'Stop'
if (-not $RepositoryRoot) {
    $RepositoryRoot = Split-Path -Parent $PSScriptRoot
}
$repository = [System.IO.Path]::GetFullPath($RepositoryRoot)
$manifest = Join-Path $repository 'release-manifest.json'
if (-not (Test-Path -LiteralPath $manifest -PathType Leaf)) {
    throw "release-manifest.json was not found under $repository"
}
if (-not $MarketplaceSource) {
    $MarketplaceSource = $repository
}

$release = [System.IO.File]::ReadAllText($manifest) | ConvertFrom-Json
$releaseTag = $release.distribution.tag
if (-not $releaseTag) {
    throw 'release-manifest.json does not declare distribution.tag.'
}
$script:ExpectedVersions = @{}
foreach ($plugin in $release.plugins) {
    $script:ExpectedVersions[$plugin.id] = $plugin.version
}
if ($script:ExpectedVersions.Count -ne 2) {
    throw 'The lifecycle test expects exactly two release plugins.'
}

$codexCommand = Get-Command codex.cmd -ErrorAction SilentlyContinue
if (-not $codexCommand) {
    $codexCommand = Get-Command codex -ErrorAction Stop
}
$script:CodexExecutable = $codexCommand.Source

function Invoke-CodexRaw {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,
        [switch]$AllowFailure
    )

    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $lines = @(
        & $script:CodexExecutable @Arguments 2>&1 |
            ForEach-Object { $_.ToString() }
    )
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousPreference
    $text = $lines -join [Environment]::NewLine
    if ($exitCode -ne 0 -and -not $AllowFailure) {
        throw "codex $($Arguments -join ' ') failed with ${exitCode}: $text"
    }
    return [pscustomobject]@{
        ExitCode = $exitCode
        Text = $text
    }
}

function Invoke-CodexJson {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $result = Invoke-CodexRaw -Arguments $Arguments
    $objectStart = $result.Text.IndexOf('{')
    $arrayStart = $result.Text.IndexOf('[')
    $jsonStart = if ($objectStart -lt 0) {
        $arrayStart
    }
    elseif ($arrayStart -lt 0) {
        $objectStart
    }
    else {
        [Math]::Min($objectStart, $arrayStart)
    }
    $jsonText = if ($jsonStart -ge 0) {
        $result.Text.Substring($jsonStart)
    }
    else {
        $result.Text
    }
    try {
        return $jsonText | ConvertFrom-Json
    }
    catch {
        throw "codex $($Arguments -join ' ') did not return valid JSON: $($result.Text)"
    }
}

function Get-GloamerePlugins {
    param([string[]]$Prefix = @())

    $arguments = @($Prefix) + @('plugin', 'list', '--json')
    $catalog = Invoke-CodexJson -Arguments $arguments
    return @(
        $catalog.installed |
            Where-Object { $_.marketplaceName -eq 'gloamere' }
    )
}

function Assert-GloamereIdentity {
    param(
        [object[]]$Plugins,
        [hashtable]$ExpectedVersions = $script:ExpectedVersions
    )

    if ($Plugins.Count -ne $ExpectedVersions.Count) {
        throw "Expected two installed Gloamere plugins, found $($Plugins.Count)."
    }
    foreach ($plugin in $Plugins) {
        $pluginName = $plugin.pluginId -replace '@gloamere$', ''
        if (-not $ExpectedVersions.ContainsKey($pluginName)) {
            throw "Unexpected plugin identity: $($plugin.pluginId)"
        }
        if ($plugin.version -ne $ExpectedVersions[$pluginName]) {
            throw "Unexpected $($plugin.pluginId) version: $($plugin.version)"
        }
        if ($plugin.installed -ne $true -or $plugin.enabled -ne $true) {
            throw "$($plugin.pluginId) was not installed and enabled."
        }
    }
}

function Set-IsolatedPluginEnabled {
    param(
        [Parameter(Mandatory = $true)]
        [bool]$Enabled
    )

    $configPath = Join-Path $env:CODEX_HOME 'config.toml'
    $text = [System.IO.File]::ReadAllText($configPath)
    $pattern = (
        '(?m)(^\[plugins\."gloamere-eval@gloamere"\]\r?\n' +
        'enabled\s*=\s*)(true|false)(\s*$)'
    )
    $replacement = '${1}' + $Enabled.ToString().ToLowerInvariant() + '${3}'
    $updated = [regex]::Replace($text, $pattern, $replacement)
    if ($updated -eq $text) {
        throw 'Could not locate the isolated Eval enabled state in config.toml.'
    }
    [System.IO.File]::WriteAllText(
        $configPath,
        $updated,
        [System.Text.UTF8Encoding]::new($false)
    )
}

function Set-SourcePluginVersions {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SourceRoot,
        [Parameter(Mandatory = $true)]
        [hashtable]$Versions
    )

    foreach ($pluginName in $Versions.Keys) {
        $pluginManifest = Join-Path (
            Join-Path $SourceRoot "plugins\$pluginName"
        ) '.codex-plugin\plugin.json'
        $text = [System.IO.File]::ReadAllText($pluginManifest)
        $versionPattern = '("version"\s*:\s*")[^"]+(")'
        $versionRegex = [regex]::new($versionPattern)
        $replacement = '${1}' + $Versions[$pluginName] + '${2}'
        $rendered = $versionRegex.Replace($text, $replacement, 1)
        if ($rendered -eq $text) {
            throw "Could not update the version in $pluginManifest"
        }
        # 只替换版本并统一 LF，避免 Windows PowerShell 重排或截断临时 manifest。
        $rendered = $rendered.Replace("`r`n", "`n")
        [System.IO.File]::WriteAllText(
            $pluginManifest,
            $rendered + "`n",
            [System.Text.UTF8Encoding]::new($false)
        )
    }
}

function Invoke-Git {
    param(
        [Parameter(Mandatory = $true)]
        [string]$WorkingTree,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $lines = @(
        & $script:GitExecutable -C $WorkingTree @Arguments 2>&1 |
            ForEach-Object { $_.ToString() }
    )
    if ($LASTEXITCODE -ne 0) {
        throw "git $($Arguments -join ' ') failed: $($lines -join [Environment]::NewLine)"
    }
}

$tempBase = [System.IO.Path]::GetFullPath(
    [System.IO.Path]::GetTempPath()
).TrimEnd(
    [System.IO.Path]::DirectorySeparatorChar,
    [System.IO.Path]::AltDirectorySeparatorChar
) + [System.IO.Path]::DirectorySeparatorChar
$testHome = Join-Path (
    [System.IO.Path]::GetTempPath()
) ("gloamere-lifecycle-" + [guid]::NewGuid().ToString('N'))
[void](New-Item -ItemType Directory -Path $testHome)
$testHome = [System.IO.Path]::GetFullPath($testHome)
$testLeaf = [System.IO.Path]::GetFileName($testHome)
if (
    -not $testHome.StartsWith(
        $tempBase,
        [System.StringComparison]::OrdinalIgnoreCase
    ) -or
    -not $testLeaf.StartsWith(
        'gloamere-lifecycle-',
        [System.StringComparison]::Ordinal
    )
) {
    throw "Refusing to use unsafe lifecycle test path: $testHome"
}

$previousCodexHome = $env:CODEX_HOME
$env:CODEX_HOME = $testHome
$httpServer = $null

try {
    $marketplaceSourceForTest = $MarketplaceSource
    $marketplaceRefForTest = $MarketplaceRef
    $initialExpectedVersions = $script:ExpectedVersions
    $localUpgradeSource = $null
    if (Test-Path -LiteralPath $MarketplaceSource -PathType Container) {
        $gitCommand = Get-Command git -ErrorAction Stop
        $script:GitExecutable = $gitCommand.Source
        $localUpgradeSource = Join-Path $testHome 'upgrade-marketplace'
        [void](New-Item -ItemType Directory -Path $localUpgradeSource)
        Copy-Item -LiteralPath (
            Join-Path $repository '.agents'
        ) -Destination $localUpgradeSource -Recurse -Force
        Copy-Item -LiteralPath (
            Join-Path $repository 'plugins'
        ) -Destination $localUpgradeSource -Recurse -Force
        # 根因是临时仓库遗漏换行策略，Windows Git 的 CRLF 警告会被 PowerShell 5.1 当成异常。
        # 复制真实仓库属性，使生命周期测试与发布源使用相同的字节身份规则。
        Copy-Item -LiteralPath (Join-Path $repository '.gitattributes') -Destination $localUpgradeSource -Force

        $initialExpectedVersions = @{
            'gloamere-eval' = '1.0.0-beta.0'
            'gloamere-workflows' = '1.0.0-beta.0'
        }
        Set-SourcePluginVersions `
            -SourceRoot $localUpgradeSource `
            -Versions $initialExpectedVersions
        Invoke-Git -WorkingTree $localUpgradeSource -Arguments @(
            'init', '--initial-branch', 'main'
        )
        Invoke-Git -WorkingTree $localUpgradeSource -Arguments @(
            'config', 'user.name', 'Gloamere Lifecycle Test'
        )
        Invoke-Git -WorkingTree $localUpgradeSource -Arguments @(
            'config', 'user.email', 'lifecycle-test@gloamere.invalid'
        )
        Invoke-Git -WorkingTree $localUpgradeSource -Arguments @(
            'add', '--all'
        )
        Invoke-Git -WorkingTree $localUpgradeSource -Arguments @(
            'commit', '-m', 'test: seed pre-release marketplace'
        )
        Invoke-Git -WorkingTree $localUpgradeSource -Arguments @(
            'update-server-info'
        )

        # Codex treats filesystem paths as immutable local snapshots, so serve
        # the temporary Git repository over dumb HTTP to exercise a real
        # marketplace refresh without writing to any external remote.
        $listener = [System.Net.Sockets.TcpListener]::new(
            [System.Net.IPAddress]::Loopback,
            0
        )
        $listener.Start()
        $port = $listener.LocalEndpoint.Port
        $listener.Stop()
        $pythonCommand = Get-Command python -ErrorAction Stop
        $httpServer = Start-Process `
            -FilePath $pythonCommand.Source `
            -ArgumentList @(
                '-m',
                'http.server',
                $port,
                '--bind',
                '127.0.0.1',
                '--directory',
                $testHome
            ) `
            -RedirectStandardOutput (Join-Path $testHome 'http.stdout.log') `
            -RedirectStandardError (Join-Path $testHome 'http.stderr.log') `
            -WindowStyle Hidden `
            -PassThru
        $serverReady = $false
        for ($attempt = 0; $attempt -lt 50; $attempt++) {
            try {
                Invoke-WebRequest `
                    -Uri "http://127.0.0.1:$port/" `
                    -UseBasicParsing `
                    -TimeoutSec 1 | Out-Null
                $serverReady = $true
                break
            }
            catch {
                Start-Sleep -Milliseconds 100
            }
        }
        if (-not $serverReady) {
            throw 'The temporary Git HTTP server did not become ready.'
        }
        $marketplaceSourceForTest = (
            "http://127.0.0.1:$port/upgrade-marketplace/.git"
        )
        $marketplaceRefForTest = 'main'
    }

    $marketplaceArguments = @(
        'plugin', 'marketplace', 'add', $marketplaceSourceForTest
    )
    if (
        $marketplaceRefForTest -and
        -not (Test-Path -LiteralPath $marketplaceSourceForTest)
    ) {
        $marketplaceArguments += @('--ref', $marketplaceRefForTest)
    }
    Invoke-CodexRaw -Arguments $marketplaceArguments | Out-Null
    Invoke-CodexRaw -Arguments @(
        'plugin', 'add', 'gloamere-eval@gloamere', '--json'
    ) | Out-Null
    Invoke-CodexRaw -Arguments @(
        'plugin', 'add', 'gloamere-workflows@gloamere', '--json'
    ) | Out-Null
    Assert-GloamereIdentity `
        -Plugins (Get-GloamerePlugins) `
        -ExpectedVersions $initialExpectedVersions

    # Reinstall must be idempotent so the pinned installer is safe to rerun.
    Invoke-CodexRaw -Arguments @(
        'plugin', 'add', 'gloamere-eval@gloamere', '--json'
    ) | Out-Null
    Invoke-CodexRaw -Arguments @(
        'plugin', 'add', 'gloamere-workflows@gloamere', '--json'
    ) | Out-Null
    Assert-GloamereIdentity `
        -Plugins (Get-GloamerePlugins) `
        -ExpectedVersions $initialExpectedVersions

    if ($localUpgradeSource) {
        Set-SourcePluginVersions `
            -SourceRoot $localUpgradeSource `
            -Versions $script:ExpectedVersions
        Invoke-Git -WorkingTree $localUpgradeSource -Arguments @(
            'add', '--all'
        )
        Invoke-Git -WorkingTree $localUpgradeSource -Arguments @(
            'commit', '-m', 'test: publish current plugin versions'
        )
        Invoke-Git -WorkingTree $localUpgradeSource -Arguments @(
            'update-server-info'
        )
    }
    Invoke-CodexRaw -Arguments @(
        'plugin', 'marketplace', 'upgrade', 'gloamere', '--json'
    ) | Out-Null
    Invoke-CodexRaw -Arguments @(
        'plugin', 'add', 'gloamere-eval@gloamere', '--json'
    ) | Out-Null
    Invoke-CodexRaw -Arguments @(
        'plugin', 'add', 'gloamere-workflows@gloamere', '--json'
    ) | Out-Null
    Assert-GloamereIdentity -Plugins (Get-GloamerePlugins)
    $upgradeResult = 'passed'

    # The current CLI exposes lifecycle add/remove but enable/disable is a
    # plugin-manager state; mutate only the isolated test config to exercise it.
    Set-IsolatedPluginEnabled -Enabled $false
    $disabled = Get-GloamerePlugins |
        Where-Object { $_.pluginId -eq 'gloamere-eval@gloamere' }
    if ($disabled.enabled -ne $false) {
        throw 'The Eval disabled state was not reflected by Codex.'
    }
    Set-IsolatedPluginEnabled -Enabled $true
    $enabled = Get-GloamerePlugins |
        Where-Object { $_.pluginId -eq 'gloamere-eval@gloamere' }
    if ($enabled.enabled -ne $true) {
        throw 'The Eval enabled state was not reflected by Codex.'
    }

    Invoke-CodexRaw -Arguments @(
        'plugin', 'remove', 'gloamere-workflows@gloamere', '--json'
    ) | Out-Null
    Invoke-CodexRaw -Arguments @(
        'plugin', 'remove', 'gloamere-eval@gloamere', '--json'
    ) | Out-Null
    if ((Get-GloamerePlugins).Count -ne 0) {
        throw 'Plugins remained installed after removal.'
    }
    Invoke-CodexRaw -Arguments @(
        'plugin', 'marketplace', 'remove', 'gloamere', '--json'
    ) | Out-Null

    $legacyPreserved = $null
    if ($IncludeLegacyMigration) {
        Invoke-CodexRaw -Arguments @(
            'plugin', 'marketplace', 'add', 'gloamere/codex-plugins',
            '--ref', 'c19f22f'
        ) | Out-Null
        Invoke-CodexRaw -Arguments @(
            'plugin', 'add', 'tessera-core@tessera', '--json'
        ) | Out-Null

        $migrationBlocked = $false
        $migrationError = $null
        try {
            & (Join-Path $repository 'install.ps1') `
                -Source $repository `
                -Ref $releaseTag `
                -All
        }
        catch {
            $migrationError = $_.Exception.Message
            $migrationBlocked = (
                $migrationError -like '*Legacy plugins must be migrated*'
            )
        }
        if (-not $migrationBlocked) {
            throw (
                'The installer did not stop on a legacy plugin identity. ' +
                "Actual error: ${migrationError}"
            )
        }
        if ((Get-GloamerePlugins).Count -ne 0) {
            throw 'The blocked migration changed the Gloamere installation state.'
        }
        $catalog = Invoke-CodexJson -Arguments @('plugin', 'list', '--json')
        $legacyPreserved = @(
            $catalog.installed |
                Where-Object { $_.pluginId -eq 'tessera-core@tessera' }
        ).Count -eq 1
        if (-not $legacyPreserved) {
            throw 'The detect-only migration unexpectedly removed the legacy plugin.'
        }

        Invoke-CodexRaw -Arguments @(
            'plugin', 'remove', 'tessera-core@tessera', '--json'
        ) | Out-Null
        Invoke-CodexRaw -Arguments @(
            'plugin', 'marketplace', 'remove', 'tessera', '--json'
        ) | Out-Null
        & (Join-Path $repository 'install.ps1') `
            -Source $repository `
            -Ref $releaseTag `
            -All
        Assert-GloamereIdentity -Plugins (Get-GloamerePlugins)

        Invoke-CodexRaw -Arguments @(
            'plugin', 'remove', 'gloamere-workflows@gloamere', '--json'
        ) | Out-Null
        Invoke-CodexRaw -Arguments @(
            'plugin', 'remove', 'gloamere-eval@gloamere', '--json'
        ) | Out-Null
        Invoke-CodexRaw -Arguments @(
            'plugin', 'marketplace', 'remove', 'gloamere', '--json'
        ) | Out-Null
    }

    [pscustomobject]@{
        codex_home = $testHome
        first_install = 'passed'
        repeat_install = 'passed'
        upgrade = $upgradeResult
        disable_enable = 'passed'
        uninstall = 'passed'
        legacy_detect_only = $legacyPreserved
    } | ConvertTo-Json
}
finally {
    $env:CODEX_HOME = $previousCodexHome
    if ($httpServer -and -not $httpServer.HasExited) {
        Stop-Process -Id $httpServer.Id -Force
        $httpServer.WaitForExit()
    }
    if (-not $KeepTemp -and (Test-Path -LiteralPath $testHome)) {
        # The verified target is a unique child of the system temporary folder.
        Remove-Item -LiteralPath $testHome -Recurse -Force
    }
}
