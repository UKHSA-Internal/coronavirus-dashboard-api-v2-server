Properties {
    $Solution = "apiv2server" # Use existing name from older builds
    $OutputRoot = Join-Path $psake.context.originalDirectory "BuildOutput"
    $TestRoot = Join-Path $psake.context.originalDirectory "test"
    $TestOutputPath = Join-Path $OutputRoot "TestResults"
    
    # Docker Props
    $DockerBuildRoot = Join-Path $psake.context.originalDirectory "src"
    $DockerComposePath = Join-Path $psake.context.originalDirectory "docker-compose.yml"
    $ContainerNameSpace = "app"
    $DockerComposeLogsPath = Join-Path $OutputRoot "containers.log"
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
Task publish -depends login_container_registry, get_container_build_information, push_container_image

Task init {
    Assert ( $null -ne (Get-Command docker -ErrorAction SilentlyContinue) ) "Docker must be installed to build this repository"
    Assert ( $null -ne (Get-Command az -ErrorAction SilentlyContinue) ) "Az CLI required to use this repository"

    # Install dependent PS modules
    "Az.ContainerRegistry", "Az.Accounts" | ForEach-Object {
        $m = Get-Module $_ -ListAvailable
        if (!$m) {
            Find-Module $_ | Install-Module -Force -Scope CurrentUser
            Import-Module $_
        }
    }
    Remove-Item $OutputRoot -ErrorAction SilentlyContinue -Force -Recurse
    New-Item $OutputRoot, $TestOutputPath -Type Directory -ErrorAction Stop | Out-Null
}

Task login_az {
    if ($env:ci_pipeline) {
        if (!(Get-AzContext)) {
            Assert ( $null -ne $env:PHE_ARM_CLIENT_SECRET ) "PHE_ARM_CLIENT_SECRET env var value required"
            Assert ( $null -ne $env:PHE_ARM_CLIENT_ID ) "PHE_ARM_CLIENT_ID env var value required"
            Assert ( $null -ne $env:PHE_ARM_SUBSCRIPTION_ID ) "PHE_ARM_SUBSCRIPTION_ID env var value required"
            Assert ( $null -ne $env:PHE_ARM_TENANT_ID ) "PHE_ARM_TENANT_ID env var value required"
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
    Assert ( $null -ne $env:PHE_CONTAINER_REGISTRY_NAME ) "PHE_CONTAINER_REGISTRY_NAME env var value required"
    Connect-AzContainerRegistry -Name (Get-AzContainerRegistry | Where-Object Name -EQ $env:PHE_CONTAINER_REGISTRY_NAME).Name
}

Task get_container_build_information -depends login_container_registry {
    Assert ( $null -ne $env:PHE_CONTAINER_REGISTRY_NAME ) "PHE_CONTAINER_REGISTRY_NAME env var value required"
    $script:container_info = Get-ContainerPipelineInfo `
        -RegistryName $env:PHE_CONTAINER_REGISTRY_NAME `
        -RegistryType AzureAcr `
        -ContainerNameSpace $ContainerNameSpace `
        -ContainerName $Solution `
        -Version $Version
    $container_info
}

# By default, we don't actually build the app, just plan it to catch any silly errors
# The module will be refactored out of this repo into its own base definition where it will be tested independently from the container logic here
Task build -depends clean, get_container_build_information {
    $env:IMAGE = $container_info.CurrentTag
    Exec { docker-compose build }
}

Task run -depends get_container_build_information {
    Exec {
        $env:IMAGE = $container_info.CurrentTag
        docker-compose -f $DockerComposePath up -d
        docker-compose -f $DockerComposePath ps
    }
}

Task stop {
    try {
        Exec { docker-compose -f $DockerComposePath rm -fs }
    }
    catch {}
}

Task test {
    Import-Module pester -ErrorAction SilentlyContinue
    $test_config = [PesterConfiguration]::new()
    $test_config.Run.Path = $TestRoot
    $test_config.Run.Throw = $true
    $test_config.Output.Verbosity = "Detailed"
    $test_config.TestResult.Enabled = $true
    $test_config.TestResult.OutputPath = $TestOutputPath
    
    $test_config.Run.Container = New-PesterContainer `
        -Path "*.tests.ps1" `
        -Data @{ ServiceUrl = "http://localhost:8080" `
    }
    
    try { 
        Invoke-Pester -Configuration $test_config
    }
    catch {
        docker-compose -f $DockerComposePath logs > $DockerComposeLogsPath
        if ($env:ci_pipeline) {
            Invoke-Task stop
        }
        throw
    }
}

Task clean {
    Get-ChildItem $OutputRoot | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
}

Task push_container_image {
    Exec { docker push $container_info.LatestTag }
    Exec { docker push $container_info.CurrentTag }
}
