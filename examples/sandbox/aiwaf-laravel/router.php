<?php

declare(strict_types=1);

require_once __DIR__ . '/../../../vendor/autoload.php';
require_once __DIR__ . '/../common/proxy_helpers.php';

use AIWAF\AIWAF;
use AIWAF\Adapters\DbAdapter;
use AIWAF\Config;
use AIWAF\RateLimiter;

Config::$knownPaths = ["/api", "/sanctum", "/broadcasting", "/up"];
Config::$keywordDetectionThreshold = 2;
$dbPath = (string) (getenv('AIWAF_RATE_LIMIT_DB_PATH') ?: (__DIR__ . '/../../../resources/aiwaf.sqlite'));
$pdo = new PDO('sqlite:' . $dbPath);
RateLimiter::initAdapter(new DbAdapter($pdo));
AIWAF::protect();

$targetBase = (string) getenv('TARGET_BASE_URL');
if ($targetBase !== '') {
    aiwaf_forward_to_target($targetBase);
    return;
}

echo 'AIWAF Laravel sandbox is running.';
