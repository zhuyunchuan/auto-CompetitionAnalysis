$apiUrl = "https://www.hikvision.com/content/hikvision/en/products/IP-Products/Network-Cameras/pro-series/jcr:content/root/responsivegrid/search_list.json"
$outFile = "D:\work\auto-CompetitionAnalysis\results\pro_api_raw.json"

Write-Host "=== 抓取 Hikvision Pro 系列子系列名称 ==="
Write-Host "API: $apiUrl"
Write-Host ""

try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls13
    [Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }
    
    $headers = @{
        "Accept" = "application/json, text/plain, */*"
        "Accept-Language" = "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7"
        "Accept-Encoding" = "gzip, deflate, br"
        "User-Agent" = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        "Referer" = "https://www.hikvision.com/en/products/IP-Products/Network-Cameras/pro-series/"
        "Cache-Control" = "no-cache"
    }
    
    $response = Invoke-WebRequest -Uri $apiUrl -Method Get -Headers $headers -TimeoutSec 60 -UseBasicParsing
    $content = $response.Content
    
    $outDir = Split-Path $outFile -Parent
    if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Path $outDir -Force | Out-Null }
    
    [System.IO.File]::WriteAllText($outFile, $content, [System.Text.Encoding]::UTF8)
    Write-Host "SUCCESS: 数据已保存到 $outFile"
    Write-Host "文件大小: $((Get-Item $outFile).Length) bytes"
    Write-Host "前500字符:"
    Write-Host $content.Substring(0, [Math]::Min(500, $content.Length))
} catch {
    Write-Host "ERROR: $_"
    Write-Host "详细: $($_.Exception.Message)"
    Write-Host "堆栈: $($_.ScriptStackTrace)"
    exit 1
}
