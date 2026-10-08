<?php

declare(strict_types=1);

require_once __DIR__ . '/../../vendor/autoload.php';
require_once __DIR__ . '/../common/proxy_helpers.php';

use AIWAF\AIWAF;
use AIWAF\Config;

Config::$knownPaths = ['/_profiler', '/_wdt', '/api', '/assets'];
Config::$keywordDetectionThreshold = 1;
if (isset($_SERVER['HTTP_X_FORWARDED_FOR'])) {
    $parts = explode(',', (string) $_SERVER['HTTP_X_FORWARDED_FOR']);
    $ip = trim((string) ($parts[0] ?? ''));
    if (filter_var($ip, FILTER_VALIDATE_IP) !== false) {
        $_SERVER['REMOTE_ADDR'] = $ip;
    }
}
require_once __DIR__ . '/../common/rate_limit.php';
aiwaf_init_redis_rate_limit();
AIWAF::protect();

$targetBase = (string) getenv('TARGET_BASE_URL');
if ($targetBase !== '') {
    aiwaf_forward_to_target($targetBase);
    return;
}

echo 'AIWAF Symfony sandbox is running.';
