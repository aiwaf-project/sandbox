<?php

declare(strict_types=1);

require_once __DIR__ . '/../../../vendor/autoload.php';
require_once __DIR__ . '/../common/proxy_helpers.php';

use AIWAF\AIWAF;
use AIWAF\Adapters\DbAdapter;
use AIWAF\Config;
use AIWAF\RateLimiter;

Config::$knownPaths = ['/wp-json', '/wp-content', '/wp-includes', '/wp-admin'];
Config::$keywordDetectionThreshold = 1;
if (isset($_SERVER['HTTP_X_FORWARDED_FOR'])) {
    $parts = explode(',', (string) $_SERVER['HTTP_X_FORWARDED_FOR']);
    $ip = trim((string) ($parts[0] ?? ''));
    if (filter_var($ip, FILTER_VALIDATE_IP) !== false) {
        $_SERVER['REMOTE_ADDR'] = $ip;
    }
}
$dbPath = (string) (getenv('AIWAF_RATE_LIMIT_DB_PATH') ?: (__DIR__ . '/../../../resources/aiwaf.sqlite'));
$pdo = new PDO('sqlite:' . $dbPath);
RateLimiter::initAdapter(new DbAdapter($pdo));
AIWAF::protect();

$targetBase = (string) getenv('TARGET_BASE_URL');
if ($targetBase !== '') {
    aiwaf_forward_to_target($targetBase);
    return;
}

echo 'AIWAF WordPress sandbox is running.';
