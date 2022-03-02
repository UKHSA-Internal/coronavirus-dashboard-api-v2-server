Properties {
    $Solution = "cw-19-dashboard-api-v2-server"
    $OutputRoot = Join-Path $psake.context.originalDirectory "BuildOutput"
    $TestRoot = Join-Path $psake.context.originalDirectory "test"
    $BuiltPackages = Join-Path $OutputRoot "BuiltPackages"
    $TestOutputPath = Join-Path $OutputRoot "TestResults"
    $SourceRoot = Join-Path $psake.context.originalDirectory "src"
    $TemplateConfigRoot = Join-Path $SourceRoot "config_templates"

    # Docker Props
    # $DockerBuildRoot = Join-Path $psake.context.originalDirectory "src" "container"
    $DockerBuildRoot = Join-Path $psake.context.originalDirectory "src"
    # $DockerComposePath = Join-Path $psake.context.originalDirectory "docker-compose.yml"
    $DockerComposePath = Join-Path $psake.context.originalDirectory "src/docker-compose.yml"
    $ContainerNameSpace = "api"
    $DockerComposeLogsPath = Join-Path $OutputRoot "containers.log"
    $DockerInputVarTemplate = Join-Path $TemplateConfigRoot ".env.tmpl"
    $DockerInputEnvVarFilePath = Join-Path $psake.context.originalDirectory ".env"
}

# TODO: Refac into PS module
Function Get-ContainerPipelineInfo {
    [cmdletbinding()]
    [OutputType([psobject])]
    param(
        [string]
        $RegistryName,

        [ValidateSet("AzureAcr", "AWSAcr", "DockerHub")]
        [string]
        $RegistryType,

        [string]
        $ContainerNameSpace,

        [string]
        $ContainerName,

        [string]
        $Version
    )

    if ($ContainerNameSpace) {
        $_ContainerNameSpace = $ContainerNameSpace + "/"
    }

    $ContainerRepositoryName = ("{0}{1}" -f $_ContainerNameSpace, $ContainerName).ToLower()
    switch ($RegistryType) {
        "AzureAcr" {
            $Registry = Get-AzContainerRegistry | Where-Object Name -EQ $RegistryName
            $RegistryUrl = $Registry.LoginServer
            $RegistryId = $Registry.Id
        }
        default {
            throw "Registry type not supported"
        }
    }

    if ($Registry) {
        $FullyQualifiedContainerRepositoryId = "{0}/{1}" -f $RegistryUrl, $ContainerRepositoryName

        $reference_info = [psobject]@{
            RegistryId     = $RegistryId
            RegistryName   = $Registry.Name
            RepositoryName = $ContainerRepositoryName
            RepositoryUri  = $FullyQualifiedContainerRepositoryId
            CurrentTag     = $FullyQualifiedContainerRepositoryId + ":$Version"
            LatestTag      = $FullyQualifiedContainerRepositoryId + ":latest"
        }

        $reference_info
    }
    else {
        Write-Error "Registry $RegistryName not found"
    }
}

Task compose -depends build, run, test, stop
Task publish -depends get_container_build_information, push_container_image

Task init {
    Assert ( $null -ne (Get-Command docker -ErrorAction SilentlyContinue) ) "Docker must be installed to build this repository"
    Assert ( $null -ne (Get-Command az -ErrorAction SilentlyContinue) ) "Azure CLI must be installed to build this repository"

    # Install dependent PS modules
    "Az.ContainerRegistry", "Az.Accounts" | ForEach-Object {
        $m = Get-Module $_ -ListAvailable
        if (!$m) {
            Find-Module $_ | Install-Module -Force -Scope CurrentUser
            Import-Module $_
        }
    }
    Remove-Item $OutputRoot -ErrorAction SilentlyContinue -Force -Recurse
    New-Item $OutputRoot, $TestOutputPath, $BuiltPackages -Type Directory -ErrorAction Stop | Out-Null
}

Task login_az {
    if ($env:ci_pipeline) {
        if (!(Get-AzContext)) {
            $connect_as_sp = @{
                Credential       = New-Object pscredential `
                    -ArgumentList @($env:PHE_ARM_CLIENT_ID, (ConvertTo-SecureString $env:PHE_ARM_CLIENT_SECRET -AsPlainText -Force))
                Subscription     = $env:PHE_ARM_SUBSCRIPTION_ID
                Tenant           = $env:PHE_ARM_TENANT_ID
                ServicePrincipal = $true
            }
            Connect-AzAccount @connect_as_sp
        }
    }
    else {
        # if (!(Get-AzContext)) {
        if (!(Get-AzContext | Where-Object Tenant -match $env:PHE_ARM_Tenant_ID)) {
            Connect-AzAccount -Subscription $env:PHE_ARM_SUBSCRIPTION_ID
        }
    }
}

Task login_container_registry -depends login_az {
    Connect-AzContainerRegistry -Name (Get-AzContainerRegistry | Where-Object Name -EQ $env:PHE_CONTAINER_REGISTRY_NAME).Name
}

Task get_container_build_information -depends login_container_registry {
    $script:container_info = Get-ContainerPipelineInfo `
        -RegistryName $env:PHE_CONTAINER_REGISTRY_NAME `
        -RegistryType AzureAcr `
        -ContainerNameSpace $ContainerNameSpace `
        -ContainerName $Solution `
        -Version $Version
    $container_info
}

Task set_configuration_defaults {
    # This task configures useful defaults for local development only.
    # Configuration during automated workflows should be defined as env vars within the github workflow files for each env
    if (-not $env:ci_pipeline) {
        # generic config
        # INSTANCE set via tf_provider_setup
        $env:RELEASE_VERSION ??= "0.0.0-Undefined"
    }
}

# By default, we don't actually build the app, just plan it to catch any silly errors
# The module will be refactored out of this repo into its own base definition where it will be tested independently from the container logic here
Task build -depends get_container_build_information {
    Write-Output "Executing $("docker build --pull -t {0} -t {1} {2}" -f $container_info.CurrentTag, $container_info.LatestTag, $DockerBuildRoot)"
    Exec { docker build --pull -t $container_info.CurrentTag -t $container_info.LatestTag $DockerBuildRoot }
    # Exec { docker build -t $container_info.CurrentTag -t $container_info.LatestTag $DockerBuildRoot }
}

Task run {
    Exec {
        # docker-compose -f $DockerComposePath --env-file .env up -d
        docker-compose -f $DockerComposePath up -d
        docker-compose -f $DockerComposePath ps
    }
}

Task stop {
    try {
        Exec { docker-compose -f $DockerComposePath rm -fs}
    }
    catch {}
}

Task test {
    try {
        Start-Sleep -Seconds 3
        $env:QueryApiUrl = "http://localhost:433/"
    }
    catch {
        docker-compose -f $DockerComposePath logs > $DockerComposeLogsPath
        throw
    }
    finally {
        Invoke-Task stop
    }
}

Task push_container_image {
    Exec { docker push $container_info.LatestTag }
    Exec { docker push $container_info.CurrentTag }
}
