<?php
/**
 * Plugin Name: AIWAF Bootstrap (MU)
 * Description: Early AIWAF protection bootstrap for WordPress.
 */

declare(strict_types=1);

use AIWAF\AIWAF;
use AIWAF\Adapters\InMemoryAdapter;
use AIWAF\RateLimiter;

$wpContentDir = defined('WP_CONTENT_DIR') ? (string) constant('WP_CONTENT_DIR') : dirname(__DIR__, 4);
require_once $wpContentDir . '/vendor/autoload.php';

AIWAF::setPathExistsResolver(static function (string $path): bool {
    $candidate = '/' . ltrim((string) strtok($path, '?'), '/');
    $known = ['/wp-json', '/wp-content', '/wp-includes'];

    foreach ($known as $prefix) {
        if ($candidate === $prefix || strpos($candidate, $prefix . '/') === 0) {
            return true;
        }
    }

    return false;
});

RateLimiter::initAdapter(new InMemoryAdapter());
AIWAF::protect();
