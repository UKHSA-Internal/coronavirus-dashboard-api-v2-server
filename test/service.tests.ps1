param(
    $ServiceUrl
)

Describe "Service" {
    It "Should return a healthy response on the healthcheck api" {
        (Invoke-RestMethod "$ServiceUrl/api/v2/healthcheck").status | Should -Be "ALIVE"
    }
}