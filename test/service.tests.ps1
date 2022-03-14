param(
    $ServiceUrl
)

Describe "Service" {
    It "Should return a 200 when healthy" {
        (Invoke-WebRequest "$ServiceUrl/api/v2/healthcheck").StatusCode | Should -Be 200
    }
}