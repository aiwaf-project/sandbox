# WordPress Example

## 1. MU-plugin bootstrap

Create `wp-content/mu-plugins/aiwaf-bootstrap.php`:

```php
<?php
/**
 * Plugin Name: AIWAF Bootstrap (MU)
 */

declare(strict_types=1);

use AIWAF\AIWAF;
use AIWAF\Adapters\InMemoryAdapter;
use AIWAF\RateLimiter;

require_once WP_CONTENT_DIR . '/vendor/autoload.php';

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
```

## 2. WP-CLI trainer command

Create `wp-content/mu-plugins/train-aiwaf.php`:

```php
<?php

declare(strict_types=1);

if (!defined('WP_CLI') || !WP_CLI) {
    return;
}

use AIWAF\AIWAF;

WP_CLI::add_command('aiwaf train', static function (array $args, array $assocArgs): void {
    $disableAi = array_key_exists('disable-ai', $assocArgs);
    $forceAi = array_key_exists('force-ai', $assocArgs);

    $waf = new AIWAF();
    $waf->detectAndTrain($disableAi, $forceAi);
    WP_CLI::success('AIWAF training complete: ' . json_encode(AIWAF::getLastTrainingTelemetry()));
});
```

Then run `wp aiwaf train`.
