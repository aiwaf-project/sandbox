<?php
declare(strict_types=1);

use AIWAF\Adapters\RedisAdapter;
use AIWAF\RateLimiter;

function aiwaf_init_redis_rate_limit(): void
{
    $url = parse_url((string) (getenv('AIWAF_REDIS_URL') ?: 'redis://redis:6379/0'));
    if ($url === false || ($url['scheme'] ?? '') !== 'redis') {
        throw new RuntimeException('AIWAF_REDIS_URL must be a redis:// URL');
    }
    $redis = new Redis();
    $redis->connect($url['host'] ?? 'redis', (int) ($url['port'] ?? 6379), 2.0);
    $redis->setOption(Redis::OPT_READ_TIMEOUT, 2.0);
    if (isset($url['pass'])) {
        $credentials = isset($url['user'])
            ? [rawurldecode($url['user']), rawurldecode($url['pass'])]
            : rawurldecode($url['pass']);
        $redis->auth($credentials);
    }
    $redis->select((int) trim($url['path'] ?? '/0', '/'));
    $redis->setOption(Redis::OPT_PREFIX, (string) (getenv('AIWAF_RATE_CACHE_KEY_PREFIX') ?: 'sandbox:php:'));
    RateLimiter::initAdapter(new RedisAdapter($redis));
}
